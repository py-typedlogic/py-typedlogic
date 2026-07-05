"""
Function for performing transformation and manipulation of Sentences and Theories.
"""
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Collection, Dict, Iterable, List, Mapping, Optional, Set, Tuple, Type, Union

from typedlogic import (
    BooleanSentence,
    Forall,
    Implies,
    NegationAsFailure,
    Sentence,
    SentenceGroup,
    Term,
    Theory,
    Variable,
)
from typedlogic.builtins import NAME_TO_INFIX_OP, NUMERIC_BUILTINS
from typedlogic.datamodel import (
    And,
    CardinalityConstraint,
    ExactlyOne,
    Exists,
    Extension,
    Iff,
    Implied,
    Not,
    NotInProfileError,
    Or,
    QuantifiedSentence,
    SentenceGroupType,
    Xor,
)
from typedlogic.utils.detect_stratified_negation import analyze_datalog_program

logger = logging.getLogger(__name__)

# predicates with fixed interpretations that can never be (re)defined by rules
_BUILTIN_PREDICATES = set(NAME_TO_INFIX_OP) | set(NUMERIC_BUILTINS)


def sentences_from_predicate_hierarchy(theory: Theory) -> List[Sentence]:
    """
    Generate subclass implication sentences from predicate parent declarations.

    For each predicate definition with parents, a ``Forall ... child -> parent`` implication
    is generated. Parent arguments are matched to child arguments by name, so each parent
    argument name must also be an argument of the child (as with Python class inheritance);
    otherwise the implication head would contain an unbound variable and a ValueError is raised.

    :param theory: The theory whose predicate definitions are examined
    :return: New implication sentences (excluding any already present in the theory)
    """
    new_sentences: List[Sentence] = []
    if not theory.predicate_definitions:
        raise ValueError("Theory must have predicate definitions")
    for pd in theory.predicate_definitions:
        if pd.parents:
            for parent in pd.parents:
                if parent not in theory.predicate_definition_map:
                    raise ValueError(f"Unknown parent predicate '{parent}' for predicate '{pd.predicate}'")
                parent_pred = theory.predicate_definition_map[parent]
                missing = [arg for arg in parent_pred.arguments if arg not in pd.arguments]
                if missing:
                    raise ValueError(
                        f"Cannot generate implication {pd.predicate} -> {parent}: "
                        f"parent argument(s) {missing} not present in child arguments {list(pd.arguments)}"
                    )
                # bindings = {arg: Variable(arg, domain=typ) for arg, typ in pd.arguments.items()}
                vars = [Variable(arg, domain=typ) for arg, typ in pd.arguments.items()]
                args = [Variable(arg) for arg in pd.arguments]
                parent_args = [Variable(arg) for arg in parent_pred.arguments]
                impl = Implies(
                    antecedent=Term(pd.predicate, *args),
                    consequent=Term(parent, *parent_args),
                )
                qs = Forall(vars, impl)
                if qs not in theory.sentences:
                    new_sentences.append(qs)

    return new_sentences


def implies_from_parents(theory: Theory) -> Theory:
    """
    Generate implications from parent classes.

    In the data model, PredicateDefinition can be linked to any number
    of parent classes. This function generates implications for each.

        >>> from typedlogic import PredicateDefinition, Theory, SentenceGroup
        >>> theory = Theory(
        ...     name="test",
        ...     predicate_definitions=[
        ...         PredicateDefinition(
        ...             predicate="Person",
        ...             arguments={"name": "str"},
        ...             parents=["Thing"],
        ...         ),
        ...         PredicateDefinition(
        ...             predicate="Thing",
        ...             arguments={"name": "str"},
        ...             parents=[],
        ...         ),
        ...     ],
        ...     sentence_groups=[]
        ... )
        >>> theory2 = implies_from_parents(theory)
        >>> new_sentences = theory2.sentence_groups[0].sentences
        >>> new_sentences
        [Forall([name: str] : Implies(Person(?name), Thing(?name)))]

    :param theory: The theory to generate implications for
    :return: A new theory with implications
    """
    new_sentences = sentences_from_predicate_hierarchy(theory)
    new_sg = SentenceGroup(name="Inferred", sentences=new_sentences)
    sgs = (theory.sentence_groups or []) + [new_sg]
    return Theory(
        name=theory.name,
        predicate_definitions=theory.predicate_definitions,
        sentence_groups=sgs,
    )


def disjunction_as_list(sentence: Sentence) -> List[Sentence]:
    if isinstance(sentence, Or):
        return list(sentence.operands)
    return [sentence]


def conjunction_as_list(sentence: Sentence) -> List[Sentence]:
    if isinstance(sentence, And):
        return list(sentence.operands)
    return [sentence]


def _variables_in_order(sentence: Sentence) -> List[Variable]:
    """
    Collect variables from a sentence, preserving first occurrence by name.

    :param sentence: the sentence to inspect
    :return: variables in first-seen order
    """
    seen: Set[str] = set()
    variables: List[Variable] = []

    def collect(value: Any) -> None:
        if isinstance(value, Variable):
            if value.name not in seen:
                seen.add(value.name)
                variables.append(value)
            return
        if isinstance(value, Term):
            for arg in value.values:
                collect(arg)
            return
        if isinstance(value, QuantifiedSentence):
            for variable in value.variables:
                collect(variable)
            collect(value.sentence)
            return
        if isinstance(value, BooleanSentence):
            for operand in value.operands:
                collect(operand)
            return
        if isinstance(value, CardinalityConstraint):
            collect(value.template)
            collect(value.conditions)

    collect(sentence)
    return variables


@dataclass
class PrologConfig:
    """
    Configuration for Prolog output.
    """

    use_lowercase_vars: Optional[bool] = False
    use_uppercase_predicates: Optional[bool] = False
    disjunctive_datalog: Optional[bool] = False
    existentials_to_constraints: Optional[bool] = False
    operator_map: Optional[Mapping[str, str]] = None
    negation_symbol: str = field(default=r"\+")
    negation_as_failure_symbol: str = field(default=r"\+")
    assume_negation_as_failure: bool = False
    double_quote_strings: bool = False
    double_quote_floats: bool = False
    include_parens_for_zero_args: bool = False
    allow_function_terms: bool = True
    allow_nesting: bool = True
    null_term: str = "null(_)"
    allow_skolem_terms: bool = False
    allow_ungrounded_vars_in_head: bool = False


def _render_asp_variable(v: Variable, config: PrologConfig) -> str:
    """Render a variable name the same way :func:`as_prolog` renders variable arguments."""
    v_name = v.name
    if not config.use_lowercase_vars:
        match = re.match(r"(_+)(.*)", v_name)
        if match:
            prefix, suffix = match.groups()
            v_name = f"{prefix}{suffix.capitalize()}"
        else:
            v_name = v_name.capitalize()
    return v_name


def _cardinality_head_to_asp(
    cc: "CardinalityConstraint",
    antecedent: Sentence,
    body_vars: Collection[str],
    config: "PrologConfig",
    depth: int,
) -> str:
    """
    Compile a head-position :class:`CardinalityConstraint` to ASP integrity constraints.

    A rule ``Body -> CardinalityConstraint(template, conditions, min, max)`` is rendered as
    one integrity constraint per bound: it is violated (making the program unsatisfiable)
    when, for some binding of the body variables, the number of distinct counted variables
    satisfying ``template`` and ``conditions`` falls outside ``[min, max]``. This is a
    satisfiability check, in contrast to the generative choice-rule reading of a bare
    ``min {..} max :- body`` clause.

        >>> x = Variable("X")
        >>> y = Variable("Y")
        >>> thing = Term("Thing", x)
        >>> hp = Term("HasPart", x, y)
        >>> part = Term("Part", y)
        >>> rule = thing >> CardinalityConstraint(hp, part, 1, 2)
        >>> print(as_prolog(rule))
        :- thing(X), #count { Y : haspart(X, Y), part(Y) } < 1.
        :- thing(X), #count { Y : haspart(X, Y), part(Y) } > 2.

    :param cc: the cardinality constraint appearing in the rule head
    :param antecedent: the rule body
    :param body_vars: variable names already bound by the body (the global variables)
    :param config: prolog rendering configuration
    :param depth: current rendering depth
    :return: newline-separated integrity constraints (possibly empty if fully unbounded)
    """
    template = cc.template
    conditions = cc.conditions
    assert template is not None, f"Cardinality constraint has no template: {cc}"
    body = as_prolog(antecedent, config, depth + 1)
    elems = [as_prolog(template, config, depth + 1)]
    if conditions is not None and conditions != template:
        elems.append(as_prolog(conditions, config, depth + 1))
    counted = cc.counted_variables(bound=body_vars)
    if not counted:
        raise NotInProfileError(f"Cardinality constraint has no counted variables (all are bound by the body): {cc}")
    key = ", ".join(_render_asp_variable(v, config) for v in counted)
    agg = "#count { " + key + " : " + ", ".join(elems) + " }"
    prefix = "" if body == "true" else f"{body}, "
    lines = []
    if cc.minimum_number is not None and cc.minimum_number > 0:
        lines.append(f":- {prefix}{agg} < {cc.minimum_number}.")
    if cc.maximum_number is not None:
        lines.append(f":- {prefix}{agg} > {cc.maximum_number}.")
    return "\n".join(lines)


def _prolog_quote_atom(value: str) -> str:
    r"""
    Render a string value as a quoted Prolog atom, escaping backslashes, quotes, and newlines.

        >>> _prolog_quote_atom("Fred")
        "'Fred'"
        >>> print(_prolog_quote_atom("O'Brien"))
        'O\'Brien'

    :param value: the string value
    :return: a quoted Prolog atom
    """
    escaped = value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    return f"'{escaped}'"


def _grounded_variable_names(sentence: Sentence) -> Set[str]:
    """
    Collect names of variables guaranteed to be bound when a rule body succeeds.

    Variables in conjuncts (including inside nested function terms) are bound;
    for a disjunction only variables bound in every branch are guaranteed;
    variables appearing only under negation are never bound.

        >>> from typedlogic import Term, Variable, And, Or, Not
        >>> X = Variable("x")
        >>> Y = Variable("y")
        >>> sorted(_grounded_variable_names(And(Term("A", X), Term("B", Y))))
        ['x', 'y']
        >>> sorted(_grounded_variable_names(Or(Term("A", X), Term("B", X, Y))))
        ['x']
        >>> sorted(_grounded_variable_names(And(Term("A", Term("f", X)), Not(Term("B", Y)))))
        ['x']

    :param sentence: a rule body (or part of one)
    :return: names of variables bound in all successful evaluations of the body
    """
    if isinstance(sentence, Exists):
        return _grounded_variable_names(sentence.sentence)
    if isinstance(sentence, Term):
        names: Set[str] = set()
        for v in sentence.bindings.values():
            if isinstance(v, Variable):
                names.add(v.name)
            elif isinstance(v, Term):
                names |= _grounded_variable_names(v)
        return names
    if isinstance(sentence, And):
        names = set()
        for op in sentence.operands:
            names |= _grounded_variable_names(op)
        return names
    if isinstance(sentence, Or):
        if not sentence.operands:
            return set()
        return set.intersection(*[_grounded_variable_names(op) for op in sentence.operands])
    # Not, NegationAsFailure, and anything else provide no grounding guarantees
    return set()


def _validate_counterexample_head_grounded(body: Sentence, head: Term, sentence: Sentence) -> None:
    """Reject counterexample transforms whose head variables are not grounded by the body."""
    grounded_variable_names = _grounded_variable_names(body)
    head_variable_names = {variable.name for variable in _variables_in_order(head)}
    ungrounded_head_variables = sorted(head_variable_names - grounded_variable_names)
    if ungrounded_head_variables:
        names = ", ".join(ungrounded_head_variables)
        raise NotInProfileError(f"Head variable(s) {names} are not grounded by body {sentence}")


def counterexample_sentence(sentence: Sentence, predicate: str = "counterexample") -> Sentence:
    """
    Convert a universally quantified implication into a counterexample rule.

    A sentence of the form ``forall V | body -> head`` becomes the Datalog-style
    rule ``counterexample(V_grounded) :- body, not head``. If the rule derives no
    counterexamples, the original universal implication holds for the current model(s).

        >>> from typedlogic import Forall, Term, Variable
        >>> X = Variable("x")
        >>> rule = counterexample_sentence(Forall([X], Term("P", X) >> Term("Q", X)))
        >>> print(as_prolog(rule, PrologConfig(negation_as_failure_symbol="not", allow_nesting=False)))
        counterexample(X) :- p(X), not q(X).

    The implication head must be an atomic term whose variables are grounded by the body.

    :param sentence: a universal implication, or an implication with free variables
    :param predicate: predicate name to use for generated counterexample atoms
    :return: a rule deriving counterexample witnesses
    """
    variables: Optional[List[Variable]] = None
    if isinstance(sentence, Forall):
        variables = sentence.variables
        sentence = sentence.sentence
    if isinstance(sentence, Implied):
        sentence = Implies(sentence.antecedent, sentence.consequent)
    if not isinstance(sentence, Implies):
        raise NotInProfileError(f"Counterexample transform requires an implication, got {sentence}")
    if variables is None:
        variables = _variables_in_order(sentence)

    body = sentence.antecedent
    head = sentence.consequent
    if not isinstance(head, Term):
        raise NotInProfileError(f"Counterexample transform requires an atomic implication head, got {head}")

    _validate_counterexample_head_grounded(body, head, sentence)

    used_variable_names = {variable.name for variable in _variables_in_order(And(body, head))}
    grounded_variable_names = _grounded_variable_names(body)
    counterexample_variables = [
        variable
        for variable in variables
        if variable.name in used_variable_names and variable.name in grounded_variable_names
    ]
    counterexample_body = And(*conjunction_as_list(body), NegationAsFailure(head))
    return Implies(counterexample_body, Term(predicate, *counterexample_variables))


def counterexample_proof_sentences(sentence: Sentence, predicate: str = "counterexample") -> List[Sentence]:
    """
    Build ground proof-check sentences for a universally quantified implication.

    This is useful for Datalog-style solvers that treat absent facts as false. Rather
    than checking the implication only against the current facts, it replaces quantified
    variables with fresh constants, asserts the positive antecedent atoms as assumptions,
    and derives ``predicate`` when the consequent is not derivable.

        >>> from typedlogic import Forall, Term, Variable
        >>> X = Variable("x")
        >>> sentences = counterexample_proof_sentences(Forall([X], Term("P", X) >> Term("Q", X)))
        >>> print(as_prolog(sentences, PrologConfig(negation_as_failure_symbol="not", allow_nesting=False)))
        p("__counterexample_x").
        counterexample :- not q("__counterexample_x").

    :param sentence: a universal implication, or an implication with free variables
    :param predicate: predicate name to use for generated counterexample atoms
    :return: assumption facts plus a counterexample query rule
    """
    variables: Optional[List[Variable]] = None
    if isinstance(sentence, Forall):
        variables = sentence.variables
        sentence = sentence.sentence
    if isinstance(sentence, Implied):
        sentence = Implies(sentence.antecedent, sentence.consequent)
    if not isinstance(sentence, Implies):
        raise NotInProfileError(f"Counterexample proof transform requires an implication, got {sentence}")
    if variables is None:
        variables = _variables_in_order(sentence)

    head = sentence.consequent
    if not isinstance(head, Term) or head.predicate in NAME_TO_INFIX_OP:
        raise NotInProfileError(f"Counterexample proof transform requires an atomic implication head, got {head}")
    _validate_counterexample_head_grounded(sentence.antecedent, head, sentence)

    constants = {variable.name: f"__{predicate}_{variable.name}" for variable in variables}
    grounded_body = replace_constants(sentence.antecedent, constants)
    grounded_head = replace_constants(head, constants)

    assumptions: List[Sentence] = []
    counterexample_conditions: List[Sentence] = []
    for conjunct in conjunction_as_list(grounded_body):
        if isinstance(conjunct, Term) and conjunct.predicate not in NAME_TO_INFIX_OP:
            assumptions.append(Implies(And(), conjunct))
            continue
        if isinstance(conjunct, (Not, NegationAsFailure)):
            counterexample_conditions.append(conjunct)
            continue
        raise NotInProfileError(f"Unsupported antecedent in counterexample proof transform: {conjunct}")

    counterexample_conditions.append(NegationAsFailure(grounded_head))
    counterexample_body: Sentence
    if len(counterexample_conditions) == 1:
        counterexample_body = counterexample_conditions[0]
    else:
        counterexample_body = And(*counterexample_conditions)
    return assumptions + [Implies(counterexample_body, Term(predicate))]


def as_prolog(
    sentence: Union[Sentence, List[Sentence]],
    config: Optional[PrologConfig] = None,
    depth=0,
    translate=False,
    strict=True,
    anon_vars: Optional[Set[str]] = None,
) -> str:
    """
    Convert a sentence to Prolog syntax.

        >>> from typedlogic import Term, Variable, Forall
        >>> X = Variable("x", "str")
        >>> Y = Variable("y", "str")
        >>> A = Term("A", X, Y)
        >>> B = Term("B", X, Y, "foo", 5)
        >>> as_prolog(A)
        'a(X, Y)'

        >>> as_prolog(Forall([X], A))
        'a(X, Y)'

        >>> C = Term("C")
        >>> D = Term("D")
        >>> E = Term("E")
        >>> print(as_prolog(Implies(C, D)))
        d :- c.

        >>> print(as_prolog(Implies(C & E, D)))
        d :- c, e.

        >>> print(as_prolog(Implies(And(D, E), C)))
        c :- d, e.

        >>> print(as_prolog(Implies(Or(D, E), C)))
        c :- (d; e).

        >>> config = PrologConfig(disjunctive_datalog=True)
        >>> print(as_prolog(Implies(And(E), C | D), config, depth=1))
        c; d :- e.

        >>> config.negation_symbol = '!'
        >>> as_prolog(~A, config, depth=1)
        '! (a(X, Y))'

        >>> print(as_prolog(Term('lt', X, 5)))
        X < 5

        >>> print(as_prolog(Term('eq', X, 5)))
        X == 5

        >>> print(as_prolog(Implies(And(C, Exists([X], Term("A", X))), D)))
        d :- c, a(X).

        >>> print(as_prolog(Implies(Term("A", X, Y), Term("B", X, Y))))
        b(X, Y) :- a(X, Y).

        >>> print(as_prolog(Implies(Term("A", X), Term("A", X, Y)), config=PrologConfig(allow_ungrounded_vars_in_head=True)))
        a(X, _Y) :- a(X).

    Default is to use single quotes for atoms

        >>> print(as_prolog(Term("p", "a")))
        p('a')

        >>> print(as_prolog(Term("p", "A")))
        p('A')

    Some prolog syntaxes (e.g. problog) use double quotes for strings:

        >>> print(as_prolog(Term("p", "A"), config=PrologConfig(double_quote_strings=True)))
        p("A")

    Disjunctive datalog allows disjunctions in the head of implications:

        >>> print(as_prolog(C >> (D | E), config=PrologConfig(disjunctive_datalog=True)))
        d; e :- c.

        >>> print(as_prolog(~C >> D, config=PrologConfig(disjunctive_datalog=True)))
        d :- \+ (c).

        Experimental: cardinality constraints:

        >>> x = Variable("X")
        >>> y = Variable("Y")
        >>> thing = Term("Thing", x)
        >>> hp = Term("HasPart", x, y)
        >>> wing = Term("Wing", y)
        >>> cc = CardinalityConstraint(hp, wing, 0, 0)
        >>> rule = And(thing, cc) >> Term("Wingless", x)
        >>> print(as_prolog(rule))
        wingless(X) :- thing(X), (0 <= {haspart(X, Y) : wing(Y)} <= 0).

    :param sentence: the sentence to render
    :param config:
    :param depth:
    :param translate:
    :param strict:
    :return:
    """
    if not strict:
        try:
            return as_prolog(sentence, config, depth=depth, translate=translate, strict=True)
        except NotInProfileError:
            return ""
    if isinstance(sentence, list):
        return "\n".join(as_prolog(s, config, depth=depth) for s in sentence)
    if not config:
        config = PrologConfig()

    def _paren(s: str) -> str:
        if config.allow_nesting:
            return f"({s})"
        return s

    if config.existentials_to_constraints:
        sentence = existentials_to_constraints(sentence)

    if translate:
        rules = to_horn_rules(sentence, allow_disjunctions_in_head=config.disjunctive_datalog)
        return "\n".join(as_prolog(s, config, depth=depth) for s in rules)
    if isinstance(sentence, Forall):
        sentence = sentence.sentence
    if isinstance(sentence, Extension):
        sentence = sentence.to_model_object()
    if depth == 0 and not isinstance(sentence, (Implies, Term)):
        raise NotInProfileError(f"Top level sentence must be an implication or term {sentence}, got {type(sentence)}")
    if isinstance(sentence, Exists) and depth > 0:
        sentence = sentence.sentence
    if isinstance(sentence, And):
        if not sentence.operands:
            return "true"
        return f"{', '.join(as_prolog(op, config, depth+1) for op in sentence.operands)}"
    if isinstance(sentence, Or):
        if not sentence.operands:
            return "fail"
        return _paren(f"{'; '.join(as_prolog(op, config, depth+1) for op in sentence.operands)}")
    if isinstance(sentence, (Not, NegationAsFailure)):
        negated_clause = _paren(as_prolog(sentence.negated, config, depth + 1))
        neg_symbol = config.negation_symbol if isinstance(sentence, Not) else config.negation_as_failure_symbol
        return f"{neg_symbol} {negated_clause}"
    if isinstance(sentence, CardinalityConstraint):
        # Body-position (aggregate) rendering; assumes clingo syntax.
        template = sentence.template
        conditions = sentence.conditions
        assert template is not None and conditions is not None, f"Incomplete cardinality constraint: {sentence}"
        template_pro = as_prolog(template, config, depth + 1)
        conditions_pro = as_prolog(conditions, config, depth + 1)
        inner = "{" + template_pro + " : " + conditions_pro + "}"
        if sentence.minimum_number is not None:
            inner = f"{sentence.minimum_number} <= {inner}"
        if sentence.maximum_number is not None:
            inner += f" <= {sentence.maximum_number}"
        return _paren(inner)
    if isinstance(sentence, Term):
        if not config.allow_skolem_terms:
            for t in sentence.values:
                if isinstance(t, Term) and t.predicate.startswith("sk__"):
                    raise NotInProfileError(f"Skolem term not supported: {sentence}")
        vals = list(sentence.bindings.values())

        def _render_arg(v: Any) -> str:
            if v is None:
                if depth > 0:
                    return "_"
                else:
                    return config.null_term
            if isinstance(v, Variable):
                v_name = v.name
                is_anon = anon_vars and v_name in anon_vars
                if not config.use_lowercase_vars:
                    import re
                    # check for match of /(_+)(.*)/
                    match = re.match(r"(_+)(.*)", v_name)
                    if match:
                        prefix, suffix = match.groups()
                        v_name = f"{prefix}{suffix.capitalize()}"
                    else:
                        v_name = v_name.capitalize()
                if is_anon:
                    v_name = f"_{v_name}"
                return v_name
            if isinstance(v, Term):
                if not config.allow_function_terms:
                    raise ValueError(f"Nested term not supported: {v}")
                return as_prolog(v, config, depth + 1, anon_vars=anon_vars)
            if config.double_quote_floats:
                if isinstance(v, float):
                    return json.dumps(str(v))
            if config.double_quote_strings:
                return json.dumps(v)
            if isinstance(v, str):
                return _prolog_quote_atom(v)
            return repr(v)

        p = sentence.predicate
        operator_map = {k: v for k, v in NAME_TO_INFIX_OP.items()}
        if config.operator_map:
            operator_map.update(config.operator_map)
        if p in operator_map:
            p = operator_map[p]
            if len(vals) == 2:
                return f"{_render_arg(vals[0])} {p} {_render_arg(vals[1])}"
            elif len(vals) == 1:
                return f"{p} {_render_arg(vals[0])}"
            else:
                raise ValueError(f"Operator {p} only supports 1 or 2 arguments")
        else:
            if config.use_uppercase_predicates:
                p = p.capitalize()
            if config.use_uppercase_predicates is False:
                p = p.lower()
            if not vals and not config.include_parens_for_zero_args:
                return p
            else:
                return f"{p}({', '.join([_render_arg(v) for v in vals])})"
    if not isinstance(sentence, Implies):
        raise NotInProfileError(f"Unsupported sentence {sentence}")
    # assumption: generation a (head :- body) implication
    if isinstance(sentence.consequent, Or) and len(sentence.consequent.operands) > 1:
        if not config.disjunctive_datalog:
            raise NotInProfileError(f"Disjunctions on LHS not allowed {sentence}")
    if isinstance(sentence.consequent, And):
        raise NotInProfileError(
            f"Conjunctions on LHS not allowed {sentence}\n" "Transform using simplify_prolog_transform first"
        )
    # check for unbound variables
    body_vars = _grounded_variable_names(sentence.antecedent)
    if isinstance(sentence.consequent, CardinalityConstraint):
        # A cardinality constraint in the head is compiled to ASP integrity
        # constraints (min/max bounds on a #count aggregate), rather than to a
        # generative choice rule. This gives it satisfiability-check semantics.
        return _cardinality_head_to_asp(sentence.consequent, sentence.antecedent, body_vars, config, depth)
    anon_vars = set()
    for head_term in disjunction_as_list(sentence.consequent):
        if isinstance(head_term, Not):
            continue
        if not isinstance(head_term, Term):
            raise NotInProfileError(f"Head must be a term, got: {type(head_term)} in {sentence}")
        # note: only direct variable arguments are checked; variables nested inside
        # function terms are permitted in heads (e.g. facts like p(f(X)).)
        head_vars = head_term.variable_names
        for v in head_vars:
            if v not in body_vars:
                if not config.allow_ungrounded_vars_in_head:
                    raise NotInProfileError(f"Variable {v} in head not in body {sentence}")
                anon_vars.add(v)


    head = as_prolog(sentence.consequent, config, depth + 1, anon_vars=anon_vars)
    body = as_prolog(sentence.antecedent, config, depth + 1)
    if head.startswith("(") and head.endswith(")"):
        head = head[1:-1]
    if head == "fail":
        return f":- {body}."
    if body == "true":
        return f"{head}."
    return f"{head} :- {body}."


def simple_prolog_transform(sentence: Sentence, strict=False) -> List[Sentence]:
    """
    Transform a sentence to a list of sentences suitable for Prolog.

    The resulting sentences will all be quantified Body -> Head implications,
    where Body is a conjunction

        >>> from typedlogic import Term, Variable, Forall
        >>> A = Term("A")
        >>> B = Term("B")
        >>> C = Term("C")
        >>> simple_prolog_transform(A >> B)
        [Forall([] : Implies(And(A), B))]

        >>> simple_prolog_transform(Iff(A, B))
        [Forall([] : Implies(And(B), A)), Forall([] : Implies(And(A), B))]

        >>> for s in simple_prolog_transform(Iff(A, B)):
        ...     print(as_prolog(s))
        a :- b.
        b :- a.

        >>> for s in simple_prolog_transform((And(A) & And(B)) >> C):
        ...     print(as_prolog(s))
        c :- a, b.

        >>> for s in simple_prolog_transform((Or(A,B)) >> C):
        ...     print(as_prolog(s))
        c :- b.
        c :- a.

        >>> for s in simple_prolog_transform(C >> (A & B)):
        ...     print(as_prolog(s))
        b :- c.
        a :- c.




    :param sentence:
    :param strict:
    :return:
    """

    def not_in_profile(s: Sentence) -> None:
        if strict:
            raise NotInProfileError(f"Unsupported sentence {s}")

    sentence = transform_sentence(sentence, reduce_singleton)
    sentence = transform_sentence(sentence, eliminate_iff)
    if not isinstance(sentence, Forall):
        sentence = Forall([], sentence)
    # sentence = transform_sentence(sentence, eliminate_implies)
    outer = sentence
    sentence = sentence.sentence
    if isinstance(sentence, And):
        # expand And to multiple sentences
        sentences = [op for op in sentence.operands]
    else:
        sentences = [sentence]
    new_sentences: List[Sentence] = []
    while sentences:
        sentence = sentences.pop()
        if isinstance(sentence, Term):
            new_sentences.append(sentence)
            continue
        if isinstance(sentence, Implied):
            sentences.append(Implies(sentence.operands[1], sentence.operands[0]))
            continue
        if isinstance(sentence, Iff):
            sentences.append(Implies(sentence.left, sentence.right))
            sentences.append(Implies(sentence.right, sentence.left))
            continue
        if not isinstance(sentence, Implies):
            not_in_profile(sentence)
            continue
        body = sentence.antecedent
        head = sentence.consequent
        if isinstance(head, And):
            sentences.extend([Implies(body, op) for op in head.operands])
            continue
        if not isinstance(head, Term):
            not_in_profile(sentence)
            continue
        if isinstance(body, Or):
            sentences.extend([Implies(op, head) for op in body.operands])
            continue
        if isinstance(body, Term):
            body = And(body)
        if not isinstance(body, And):
            # note: does not check members of And
            not_in_profile(sentence)
            continue
        new_sentences.append(Implies(body, head))
    return [Forall(outer.variables, s) for s in new_sentences]


def as_fol(sentence, config: Optional[PrologConfig] = None) -> str:
    """
    Convert a sentence to first order logic syntax.

    >>> from typedlogic import Term, Variable, Forall
    >>> X = Variable("x", "str")
    >>> Y = Variable("y", "str")
    >>> A = Term("A", X)
    >>> B = Term("B", X)
    >>> print(as_fol(Forall([X], A >> B)))
    ∀[x:str]. A(x) → B(x)
    >>> print(as_fol(Forall([X], Iff(A, B))))
    ∀[x:str]. A(x) ↔ B(x)
    >>> print(as_fol(Exists([X], A & B)))
    ∃[x:str]. A(x) ∧ B(x)
    >>> print(as_fol(A|B))
    (A(x) ∨ B(x))

    :param sentence:
    :param config:
    :return:
    """
    if not config:
        config = PrologConfig(use_lowercase_vars=True, use_uppercase_predicates=None)
    if isinstance(sentence, (Exists, Forall)):
        qsym = "∀" if isinstance(sentence, Forall) else "∃"
        arg_exprs = [f"{v.name}:{v.domain}" if v.domain else v.name for v in sentence.variables]
        args = " ".join(arg_exprs)
        return f"{qsym}[{args}]. {as_fol(sentence.sentence, config)}"
    if isinstance(sentence, And):
        return f"{' ∧ '.join(as_fol(op, config) for op in sentence.operands)}"
    if isinstance(sentence, Or):
        return f"({' ∨ '.join(as_fol(op, config) for op in sentence.operands)})"
    if isinstance(sentence, Not):
        return f"¬{as_fol(sentence.negated, config)}"
    if isinstance(sentence, Implies):
        return f"{as_fol(sentence.antecedent, config)} → {as_fol(sentence.consequent, config)}"
    if isinstance(sentence, Implied):
        return f"{as_fol(sentence.operands[1], config)} ← {as_fol(sentence.operands[0], config)}"
    if isinstance(sentence, Iff):
        return f"{as_fol(sentence.left, config)} ↔ {as_fol(sentence.right, config)}"
    if isinstance(sentence, Term):
        vals = list(sentence.bindings.values())

        def _render_arg(v: Any) -> str:
            if isinstance(v, Variable):
                if config.use_lowercase_vars:
                    return v.name
                return v.name.capitalize()
            if isinstance(v, Term):
                return as_fol(v, config)
            if config.double_quote_strings:
                return json.dumps(v)
            else:
                return repr(v)

        p = sentence.predicate
        operator_map = {k: v for k, v in NAME_TO_INFIX_OP.items()}
        if config.operator_map:
            operator_map.update(config.operator_map)
        if p in operator_map:
            p = operator_map[p]
            if len(vals) == 2:
                return f"{_render_arg(vals[0])} {p} {_render_arg(vals[1])}"
            elif len(vals) == 1:
                return f"{p} {_render_arg(vals[0])}"
            else:
                raise ValueError(f"Operator {p} only supports 1 or 2 arguments")
        else:
            if config.use_uppercase_predicates:
                p = p.capitalize()
            if config.use_uppercase_predicates is False:
                p = p.lower()
            if not vals and not config.include_parens_for_zero_args:
                return p
            else:
                return f"{p}({', '.join([_render_arg(v) for v in vals])})"
    return ""


def as_tptp(sentence: Sentence, config: Optional[PrologConfig] = None, depth=0) -> str:
    """
    Convert a sentence to TPTP syntax.

    :param sentence: The sentence to convert
    :param config: Configuration options (optional)
    :param depth: Current depth in the sentence structure (used for indentation)
    :return: TPTP representation of the sentence

    Examples
    --------
    >>> from typedlogic import Term, Variable, Forall, Exists, And, Or, Not, Implies
    >>> X = Variable("X", "str")
    >>> Y = Variable("Y", "str")
    >>> P = Term("P", X)
    >>> Q = Term("Q", X, Y)
    >>> R = Term("R", Y)
    >>> print(as_tptp(Forall([X], Implies(P, Q))))
    ! [X] : (p(X) => q(X, Y))
    >>> print(as_tptp(Exists([X, Y], And(P, Q))))
    ? [X, Y] : (p(X) & q(X, Y))
    >>> print(as_tptp(Or(P, Not(R))))
    (p(X) | ~r(Y))

    """
    if not config:
        config = PrologConfig(use_lowercase_vars=False, use_uppercase_predicates=False)

    def format_var(v: Variable) -> str:
        return v.name if config.use_lowercase_vars else v.name.capitalize()

    def format_predicate(p: str) -> str:
        return p.lower() if config.use_uppercase_predicates is False else p

    if isinstance(sentence, (Forall, Exists)):
        quantifier = "!" if isinstance(sentence, Forall) else "?"
        vars = ", ".join(format_var(v) for v in sentence.variables)
        return f"{quantifier} [{vars}] : {as_tptp(sentence.sentence, config, depth)}"

    elif isinstance(sentence, And):
        return f"({' & '.join(as_tptp(op, config, depth + 1) for op in sentence.operands)})"

    elif isinstance(sentence, Or):
        return f"({' | '.join(as_tptp(op, config, depth + 1) for op in sentence.operands)})"

    elif isinstance(sentence, Not):
        return f"~{as_tptp(sentence.negated, config, depth + 1)}"

    elif isinstance(sentence, Implies):
        return (
            f"({as_tptp(sentence.antecedent, config, depth + 1)} => {as_tptp(sentence.consequent, config, depth + 1)})"
        )

    elif isinstance(sentence, Iff):
        return f"({as_tptp(sentence.left, config, depth + 1)} <=> {as_tptp(sentence.right, config, depth + 1)})"

    elif isinstance(sentence, Term):
        predicate = format_predicate(sentence.predicate)
        args = ", ".join(format_var(v) if isinstance(v, Variable) else repr(v) for v in sentence.bindings.values())
        return f"{predicate}({args})"

    else:
        raise ValueError(f"Unsupported sentence type: {type(sentence)}")


def tptp_problem(theory: Theory, conjecture: Optional[Sentence] = None) -> str:
    """
    Generate a complete TPTP problem from a theory and an optional conjecture.

    :param theory: The theory containing axioms
    :param conjecture: An optional conjecture to prove
    :return: TPTP representation of the problem

    Example:
    -------
    >>> from typedlogic import Theory, PredicateDefinition, Term, Variable, Forall, Implies
    >>> X = Variable("X", "str")
    >>> Y = Variable("Y", "str")
    >>> theory = Theory(
    ...     name="example",
    ...     predicate_definitions=[
    ...         PredicateDefinition("P", {"x": "str"}),
    ...         PredicateDefinition("Q", {"x": "str", "y": "str"}),
    ...     ],
    ...     sentence_groups=[
    ...         SentenceGroup("axioms", sentences=[
    ...             Forall([X], Implies(Term("P", X), Term("Q", X, Y)))
    ...         ])
    ...     ]
    ... )
    >>> conjecture = Forall([X, Y], Implies(Term("P", X), Term("Q", X, Y)))
    >>> print(tptp_problem(theory, conjecture))
    % Problem: example
    fof(axiom1, axiom, ! [X] : (p(X) => q(X, Y))).
    fof(conjecture, conjecture, ! [X, Y] : (p(X) => q(X, Y))).

    """
    lines = [f"% Problem: {theory.name}"]

    for i, sentence in enumerate(theory.sentences, 1):
        if contains_negation_as_failure(sentence):
            logger.warning(
                f"Skipping sentence with negation-as-failure (unsupported in TPTP FOF): {sentence}. "
                "The theory is weakened by this omission; consider "
                "typedlogic.transformations.clark_completion for a classical rendering."
            )
            continue
        lines.append(f"fof(axiom{i}, axiom, {as_tptp(sentence)}).")

    if conjecture:
        lines.append(f"fof(conjecture, conjecture, {as_tptp(conjecture)}).")

    return "\n".join(lines)


def as_prover9(sentence: Sentence, config: Optional[PrologConfig] = None, depth=0) -> str:
    """
    Convert a sentence to Prover9 syntax.

    :param sentence: The sentence to convert
    :param config: Configuration options (optional)
    :param depth: Current depth in the sentence structure (used for indentation)
    :return: Prover9 representation of the sentence

    Examples
    --------
    >>> from typedlogic import Term, Variable, Forall, Exists, And, Or, Not, Implies
    >>> X = Variable("X", "str")
    >>> Y = Variable("Y", "str")
    >>> P = Term("P", X)
    >>> Q = Term("Q", X, Y)
    >>> R = Term("R", Y)
    >>> print(as_prover9(Forall([X], Implies(P, Q))))
    all x ((P(x) -> Q(x, y)))
    >>> print(as_prover9(Exists([X, Y], And(P, Q))))
    exists x y ((P(x) & Q(x, y)))
    >>> print(as_prover9(Or(P, Not(R))))
    (P(x) | - ( R(y) ))
    >>> print(as_prover9(Term("S", "hello")))
    S(s_hello)

    """
    if not config:
        config = PrologConfig(use_lowercase_vars=True, use_uppercase_predicates=False)

    def format_var(v: Variable) -> str:
        return v.name.lower()

    def format_predicate(p: str) -> str:
        return p.upper() if config.use_uppercase_predicates else p

    def format_value(v: Any) -> str:
        if isinstance(v, str):
            # Convert string to a valid Prover9 constant
            return f"s_{v.replace(' ', '_')}"
        elif isinstance(v, int):
            return str(v)
        elif isinstance(v, float):
            # Prover9 doesn't support floats directly, so we convert to a fraction
            from fractions import Fraction

            frac = Fraction(v).limit_denominator()
            return f"rational({frac.numerator},{frac.denominator})"
        elif v is None:
            return "null"
        else:
            return str(v)

    if isinstance(sentence, (Forall, Exists)):
        quantifier = "all" if isinstance(sentence, Forall) else "exists"
        vars = " ".join(format_var(v) for v in sentence.variables)
        return f"{quantifier} {vars} ({as_prover9(sentence.sentence, config, depth)})"

    elif isinstance(sentence, And):
        if not sentence.operands:
            return "true"
        return f"({' & '.join(as_prover9(op, config, depth + 1) for op in sentence.operands)})"

    elif isinstance(sentence, Xor):
        return as_prover9(expand_xor(sentence), config, depth)

    elif isinstance(sentence, ExactlyOne):
        return as_prover9(expand_exactly_one(sentence), config, depth)

    elif isinstance(sentence, Or):
        if not sentence.operands:
            return "false"
        return f"({' | '.join(as_prover9(op, config, depth + 1) for op in sentence.operands)})"

    elif isinstance(sentence, Not):
        return f"- ( {as_prover9(sentence.negated, config, depth + 1)} )"

    elif isinstance(sentence, Implies):
        return f"({as_prover9(sentence.antecedent, config, depth + 1)} -> {as_prover9(sentence.consequent, config, depth + 1)})"

    elif isinstance(sentence, Implied):
        return f"({as_prover9(sentence.consequent, config, depth + 1)} <- {as_prover9(sentence.antecedent, config, depth + 1)})"

    elif isinstance(sentence, Iff):
        return f"({as_prover9(sentence.left, config, depth + 1)} <-> {as_prover9(sentence.right, config, depth + 1)})"

    elif isinstance(sentence, Term):
        predicate = format_predicate(sentence.predicate)
        if not sentence.bindings:
            return predicate
        args = ", ".join(
            format_var(v) if isinstance(v, Variable) else format_value(v) for v in sentence.bindings.values()
        )
        return f"{predicate}({args})"

    else:
        raise ValueError(f"Unsupported sentence type: {type(sentence)}")


def prover9_problem(theory: Theory, conjecture: Optional[Sentence] = None) -> str:
    """
    Generate a complete Prover9 problem from a theory and an optional conjecture.

    :param theory: The theory containing axioms
    :param conjecture: An optional conjecture to prove
    :return: Prover9 representation of the problem

    Example:
    -------
    >>> from typedlogic import Theory, PredicateDefinition, Term, Variable, Forall, Implies
    >>> X = Variable("X", "str")
    >>> Y = Variable("Y", "str")
    >>> theory = Theory(
    ...     name="example",
    ...     predicate_definitions=[
    ...         PredicateDefinition("P", {"x": "str"}),
    ...         PredicateDefinition("Q", {"x": "str", "y": "str"}),
    ...     ],
    ...     sentence_groups=[
    ...         SentenceGroup("axioms", sentences=[
    ...             Forall([X], Implies(Term("P", X), Term("Q", X, Y)))
    ...         ])
    ...     ]
    ... )
    >>> conjecture = Forall([X, Y], Implies(Term("P", X), Term("Q", X, Y)))
    >>> print(prover9_problem(theory, conjecture))
    formulas(assumptions).
        all x ((P(x) -> Q(x, y))).
    end_of_list.
    <BLANKLINE>
    formulas(goals).
        all x y ((P(x) -> Q(x, y))).
    end_of_list.

    """
    lines = []

    # Assumptions (axioms)
    lines.append("formulas(assumptions).")
    for sentence in theory.sentences:
        if contains_negation_as_failure(sentence):
            # Negation-as-failure has no classical reading; skipping the sentence keeps the
            # rest of a mixed theory usable (weakened) instead of failing whole-theory.
            logger.warning(
                f"Skipping sentence with negation-as-failure (unsupported by Prover9): {sentence}. "
                "The theory is weakened by this omission; consider "
                "typedlogic.transformations.clark_completion for a classical rendering."
            )
            continue
        lines.append(f"    {as_prover9(sentence)}.")
    lines.append("end_of_list.")
    lines.append("")

    # Goals (conjecture)
    if conjecture:
        lines.append("formulas(goals).")
        lines.append(f"    {as_prover9(conjecture)}.")
        lines.append("end_of_list.")

    return "\n".join(lines)


def transform_sentence_chained(sentence: Sentence, rules: Iterable[Callable[[Sentence], Sentence]]) -> Sentence:
    """
    Transform a sentence using a chain of rules.

        >>> from typedlogic import And, Or, Variable, Term, Forall
        >>> A = Term("A")
        >>> B = Term("B")
        >>> C = Term("C")
        >>> D = Term("D")
        >>> sentence = A | (B & C)
        >>> negate_conjunctions = lambda s: Or(*[~op for op in s.operands]) if isinstance(s, And) else s
        >>> reduce_singletons = lambda s: s.operands[0] if isinstance(s, And) and len(s.operands) == 1 else s
        >>> transform_sentence_chained(sentence, [negate_conjunctions, reduce_singletons])
        Or(A, Or(Not(B), Not(C)))

    :param sentence:
    :param rules:
    :return:
    """
    for rule in rules:
        sentence = transform_sentence(sentence, rule)
    return sentence


def transform_sentence(
    sentence: Sentence, rule: Callable[[Sentence], Sentence], varmap: Optional[Dict[str, Variable]] = None
) -> Sentence:
    """
    Transform a sentence recursively using a rule.

        >>> from typedlogic import And, Or, Variable, Term, Forall
        >>> A = Term("A")
        >>> B = Term("B")
        >>> C = Term("C")
        >>> D = Term("D")
        >>> sentence = A | (B & (C | ~D))
        >>> assert transform_sentence(sentence, lambda s: s) == sentence

        >>> def negate_conjunctions(sentence: Sentence) -> Optional[Sentence]:
        ...     if isinstance(sentence, And):
        ...         return Or(*[~op for op in sentence.operands])
        ...     return None
        >>> transform_sentence(B & C, negate_conjunctions)
        Or(Not(B), Not(C))
        >>> transform_sentence(A | (B & C), negate_conjunctions)
        Or(A, Or(Not(B), Not(C)))

    :param sentence:
    :param rule:
    :param varmap:
    :return:
    """
    varmap = varmap or {}
    new_sentence = rule(sentence)
    if new_sentence:
        if sentence != new_sentence:
            sentence = transform_sentence(new_sentence, rule, varmap)
        else:
            sentence = new_sentence
    if isinstance(sentence, QuantifiedSentence):
        return type(sentence)(sentence.variables, transform_sentence(sentence.sentence, rule, varmap))
    elif isinstance(sentence, BooleanSentence):
        return type(sentence)(*[transform_sentence(op, rule, varmap) for op in sentence.operands])
    elif isinstance(sentence, (Term, CardinalityConstraint)):
        return sentence
    elif isinstance(sentence, Extension):
        return sentence.to_model_object()
    else:
        raise ValueError(f"Unknown sentence type {type(sentence)} // {sentence}")


def replace_constants(sentence: Sentence, constant_map: Dict[str, Any]) -> Sentence:
    """
    Replace constants in a sentence with new values.

        >>> from typedlogic import And, Or, Variable, Term, Forall
        >>> X = Variable("X", "str")
        >>> Y = Variable("Y", "str")
        >>> Z = Variable("Z", "str")
        >>> A = Term("A", X)
        >>> B = Term("B", Y)
        >>> C = Term("C", Z)
        >>> constant_map = {"X": "foo", "Y": "bar", "Z": "baz"}
        >>> replace_constants(A & B, constant_map)
        And(A(foo), B(bar))


    :param sentence:
    :param constant_map:
    :return:
    """
    if isinstance(sentence, QuantifiedSentence):
        return type(sentence)(sentence.variables, replace_constants(sentence.sentence, constant_map))
    elif isinstance(sentence, BooleanSentence):
        return type(sentence)(*[replace_constants(op, constant_map) for op in sentence.operands])
    elif isinstance(sentence, Term):

        def _repl(v: Any) -> Any:
            if isinstance(v, Variable):
                if v.name in constant_map:
                    return constant_map[v.name]
            if isinstance(v, Term):
                return replace_constants(v, constant_map)
            return v

        return Term(sentence.predicate, {k: _repl(v) for k, v in sentence.bindings.items()})
    else:
        raise ValueError(f"Unknown sentence type {sentence}")


def reduce_singleton(sentence: Sentence) -> Sentence:
    """
    Reduce singleton conjunctions and disjunctions in a sentence.

        >>> from typedlogic import And, Or, Variable, Term, Forall
        >>> A = Term("A")
        >>> B = Term("B")
        >>> C = Term("C")
        >>> D = Term("D")
        >>> sentence = And(A, B)
        >>> reduce_singleton(sentence)
        And(A, B)
        >>> reduce_singleton(And(A))
        A
        >>> reduce_singleton(Or(A))
        A
        >>> transform_sentence(And(A, Or(B), C), reduce_singleton)
        And(A, B, C)
        >>> transform_sentence(And(And(A)), reduce_singleton)
        A
        >>> transform_sentence(And(A, Or(Or(B)), And(Or(And(C)))), reduce_singleton)
        And(A, B, C)

    :param sentence:
    :return:
    """
    if isinstance(sentence, And) and len(sentence.operands) == 1:
        return sentence.operands[0]
    if isinstance(sentence, Or) and len(sentence.operands) == 1:
        return sentence.operands[0]
    return sentence


def map_variables(sentence: Sentence, varmap: Dict[str, Variable]) -> Sentence:
    """
    Map variables in a sentence using a variable map.

        >>> from typedlogic import And, Or, Variable, Term, Forall
        >>> X1 = Variable("X1", "str")
        >>> Y1 = Variable("Y1", "str")
        >>> X2 = Variable("X2", "str")
        >>> Y2 = Variable("Y2", "str")
        >>> A = Term("A", X1)
        >>> B = Term("B", Y1)
        >>> varmap = {"X1": X2, "Y1": Y2}
        >>> map_variables(A & B, varmap)
        And(A(?X2), B(?Y2))

    :param sentence:
    :param varmap:
    :return:
    """
    def rewire(s: Sentence) -> Sentence:
        if isinstance(s, Term):
            new_bindings = {k: varmap.get(v.name, v) if isinstance(v, Variable) else v for k, v in s.bindings.items()}
            return Term(s.predicate, new_bindings)
        if isinstance(s, (Exists, Forall)):
            new_vars = [varmap.get(v.name, v) for v in s.variables]
            return type(s)(new_vars, map_variables(s.sentence, varmap))
        return s
    return transform_sentence(sentence, rewire)

def anonymize_existential(sentence: Exists) -> Exists:
    """
    Anonymize the variables in an existential quantifier.

    This replaces the variable names with a generic name to avoid conflicts.

        >>> from typedlogic import Exists, Variable, Term
        >>> X = Variable("X", "str")
        >>> A = Term("A", X)
        >>> exists_sentence = Exists([X], A)
        >>> anonymize_existential(exists_sentence)
        Exists(_X: str : A(?_X))

    :param sentence: The existential sentence to anonymize.
    :return: An anonymized existential sentence.
    """
    vmap = {v.name: Variable(f"_{v.name}", v.domain) for v in sentence.variables}
    mapped = map_variables(sentence, vmap)
    if not isinstance(mapped, Exists):
        raise ValueError(f"Expected an Exists sentence, got {type(mapped)}")
    return mapped


def simplify(sentence: Sentence) -> Sentence:
    """
    Simplify a sentence by reducing nested conjunctions and disjunctions.

    >>> from typedlogic import And, Or, Variable, Term, Forall
    >>> A = Term("A")
    >>> B = Term("B")
    >>> C = Term("C")
    >>> D = Term("D")
    >>> simplify(And(A, And(B, And(C, D))))
    And(A, B, C, D)
    >>> simplify(And(And(A)))
    A

    :param sentence:
    :return:
    """
    if isinstance(sentence, (And, Or)):
        operands = [simplify(op) for op in sentence.operands]
        if len(operands) == 1:
            return simplify(operands[0])
        op_type = type(sentence)
        new_operands: List[Sentence] = []
        for op in operands:
            if isinstance(op, op_type):
                if not isinstance(op, (And, Or)):
                    raise AssertionError
                new_operands.extend(op.operands)
            else:
                new_operands.append(op)
        sentence = op_type(*new_operands)
    if isinstance(sentence, (Exists, Forall)):
        typ = type(sentence)
        qs = sentence.sentence
        if typ == type(qs):
            if not isinstance(qs, (Exists, Forall)):
                raise AssertionError
            return typ(sentence.variables + qs.variables, simplify(qs.sentence))
    if isinstance(sentence, Not):
        negated = simplify(sentence.negated)
        if isinstance(negated, Not):
            return negated.negated
        return Not(negated)
    return sentence


def distribute_and_over_or(sentence: Sentence) -> Sentence:
    """
    Distribute AND over OR in a sentence.

    A ∨ (B1 ∧ B2 ∧ ... ∧ Bn) ≡ (A ∨ B1) ∧ (A ∨ B2) ∧ ... ∧ (A ∨ Bn)

        >>> from typedlogic import And, Or, Variable, Term, Forall
        >>> A = Term("A")
        >>> B = Term("B")
        >>> C = Term("C")
        >>> D = Term("D")
        >>> distribute_and_over_or(A | (B & C))
        And(Or(B, A), Or(C, A))
        >>> distribute_and_over_or((A & B) | (C & D))
        And(Or(C, A), Or(D, A), Or(C, B), Or(D, B))

        >>> distribute_and_over_or(A | And(B, C, D))
        And(Or(B, A), Or(C, A), Or(D, A))

        >>> distribute_and_over_or(A | B)
        Or(A, B)

    :param sentence:
    :return:
    """
    if not isinstance(sentence, Or):
        return sentence
    sentence = _distribute_sentence(sentence, And, Or)
    # sentence = transform_sentence(sentence, reduce_singleton)
    return sentence


def _distribute_sentence(sentence: Sentence, op1: Type[BooleanSentence], op2: Type[BooleanSentence]) -> Sentence:
    # adapted from sympy
    dfunc = lambda t: _distribute_sentence(*t)
    sentence = simplify(sentence)
    tups: List[Tuple[Union[Sentence, Type[Sentence]], ...]]

    if isinstance(sentence, op2):
        for arg in sentence.operands:
            if isinstance(arg, op1):
                conj = arg
                break
        else:
            return sentence
        rest = op2(*[a for a in sentence.operands if a is not conj])
        tups = [(op2(c, rest), op1, op2) for c in conj.operands]
        if not tups:
            raise ValueError("Expected at least one operand")
        mapped = list(map(dfunc, tups))
        return simplify(op1(*mapped))
    elif isinstance(sentence, op1):
        tups = [(x, op1, op2) for x in sentence.operands]
        if not tups:
            raise ValueError("Expected at least one operand")
        mapped = list(map(dfunc, tups))
        if len(mapped) == 1:
            return mapped[0]
        else:
            return simplify(op1(*mapped))
    else:
        return sentence


def flatten_nested_conjunctions_and_disjunctions(sentence: Sentence) -> Sentence:
    """
    Flatten nested conjunctions and disjunctions in a sentence.

    Replace (A ∧ B) ∧ C with A ∧ B ∧ C
    Replace (A ∨ B) ∨ C with A ∨ B ∨ C

        >>> from typedlogic import And, Or, Variable, Term, Forall
        >>> X = Variable("X", "str")
        >>> Y = Variable("Y", "str")
        >>> Z = Variable("Z", "str")
        >>> sentence = And(And(Term("Q", X), Term("R", Y)), Term("S", Z))
        >>> flatten_nested_conjunctions_and_disjunctions(sentence)
        And(Q(?X), R(?Y), S(?Z))

    Note: does not recurse, use :ref:`transform_sentence` to apply to all sub-sentences.

    :param sentence:
    :return:
    """
    if isinstance(sentence, (And, Or)):
        # new_ops = []
        new_ops: List[Sentence] = []
        for op in sentence.operands:
            if isinstance(op, type(sentence)):
                if not isinstance(sentence, BooleanSentence):
                    raise AssertionError(f"Expected {sentence} to be a BooleanSentence, got {type(sentence)}")
                if isinstance(op, BooleanSentence):
                    new_ops.extend(op.operands)
            else:
                new_ops.append(op)
        return type(sentence)(*new_ops)
    return sentence


def skolemize(
    sentence: Sentence,
    universal_vars: Optional[List[Variable]] = None,
    substitution_map: Optional[Dict[str, Term]] = None,
) -> Sentence:
    """
    Skolemize a sentence.

    Examples
    --------
        >>> from typedlogic import And, Or, Variable, Term, Forall, Exists
        >>> X = Variable("X", "str")
        >>> Y = Variable("Y", "str")
        >>> Z = Variable("Z", "str")
        >>> # no universal quantifiers
        >>> skolemize(Exists([X], Term("P", X)))
        P(sk__1)
        >>> skolemize(Forall([X], Exists([Y], Term("P", X, Y))))
        Forall([X: str] : P(?X, sk__1(?X)))
        >>> skolemize(Forall([X], Exists([Y, Z], Term("P", X, Y, Z))))
        Forall([X: str] : P(?X, sk__1(?X), sk__2(?X)))
        >>> skolemize(Forall([X], And(Exists([Y, Z], Term("P", X, Y, Z)), Exists([Y], Term("Q", X, Y)))))
        Forall([X: str] : And(P(?X, sk__1(?X), sk__2(?X)), Q(?X, sk__3(?X))))


    :param sentence:
    :param universal_vars:
    :param substitution_map:
    :return:

    """
    if substitution_map is None:
        substitution_map = {}
    if not universal_vars:
        universal_vars = []
    if isinstance(sentence, Forall):
        return Forall(
            sentence.variables, skolemize(sentence.sentence, universal_vars + sentence.variables, substitution_map)
        )
    if isinstance(sentence, Exists):
        vars_to_skolemize = [v for v in sentence.variables if v not in universal_vars]
        n = len(substitution_map)
        for v in vars_to_skolemize:
            n += 1
            skolem_term = Term(f"sk__{n}", *universal_vars)
            substitution_map[v.name] = skolem_term
        return skolemize(sentence.sentence, universal_vars, substitution_map)
    if isinstance(sentence, BooleanSentence):
        return type(sentence)(*[skolemize(op, universal_vars, substitution_map) for op in sentence.operands])
    elif isinstance(sentence, Term):
        return Term(
            sentence.predicate,
            {
                k: substitution_map[v.name] if isinstance(v, Variable) and v.name in substitution_map else v
                for k, v in sentence.bindings.items()
            },
        )
    else:
        raise ValueError(f"Unknown sentence type {type(sentence)} // {sentence}")


def to_cnf(sentence: Sentence, skip_skolemization=False) -> Sentence:
    """
    Convert a sentence to conjunctive normal form.

    Examples
    --------
        >>> from typedlogic.profiles import SortedLogic
        >>> from typedlogic import And, Or, Variable, Term, Forall
        >>> X = Variable("X", "str")
        >>> Y = Variable("Y", "str")
        >>> Z = Variable("Z", "str")
        >>> P = Term("P")
        >>> Q = Term("Q")
        >>> R = Term("R")
        >>> S = Term("S")
        >>> T = Term("T")
        >>> to_cnf(P)
        P
        >>> to_cnf(P & Q)
        And(P, Q)
        >>> to_cnf(P | Q)
        Or(P, Q)
        >>> to_cnf(P >> Q)
        Or(Not(P), Q)
        >>> to_cnf(~(P | Q) | R)
        And(Or(Not(P), R), Or(Not(Q), R))
        >>> to_cnf((P & Q) >> R)
        Or(Not(P), Not(Q), R)
        >>> to_cnf(((P & Q) | (R & S)))
        And(Or(R, P), Or(S, P), Or(R, Q), Or(S, Q))
        >>> to_cnf((P | Q) & (R | S))
        And(Or(P, Q), Or(R, S))
        >>> sentence = Or(And(Term("Q", X), Term("R", Y)), Term("S", Z))
        >>> to_cnf(sentence)
        And(Or(Q(?X), S(?Z)), Or(R(?Y), S(?Z)))
        >>> to_cnf(P >> (Q | R))
        Or(Not(P), Q, R)

    :param sentence:
    :param skip_skolemization:
    :return:

    """
    # Eliminate XORs
    sentence = transform_sentence_chained(sentence, [expand_xor, expand_exactly_one])
    # Eliminate implications and equivalences
    sentence = eliminate_all_implications_recursive(sentence)
    # Move negations inward
    sentence = transform_sentence_chained(sentence, [apply_demorgans, apply_quantifier_negation])
    # Standardize variables - TODO
    # Skolemize
    if not skip_skolemization:
        sentence = skolemize(sentence)
    # def raise_if_exists(s: Sentence) -> Sentence:
    #    if isinstance(s, Exists):
    #        raise NotInProfileError("Exists not allowed in CNF")
    #    return s

    # transform_sentence(sentence, raise_if_exists)
    # Drop universal quantifiers
    sentence = transform_sentence(sentence, lambda s: s.sentence if isinstance(s, Forall) else s)
    # Distribute OR over AND
    sentence = transform_sentence(sentence, distribute_and_over_or)
    return sentence


def to_cnf_lol(sentence: Sentence, **kwargs) -> List[List[Sentence]]:
    """
    Convert a sentence to a list of lists of sentences in conjunctive normal form.

    Examples
    --------
        >>> from typedlogic import And, Or, Variable, Term, Forall
        >>> X = Variable("X", "str")
        >>> Y = Variable("Y", "str")
        >>> Z = Variable("Z", "str")
        >>> sentence = Or(And(Term("Q", X), Term("R", Y)), Term("S", Z))
        >>> to_cnf_lol(sentence)
        [[Q(?X), S(?Z)], [R(?Y), S(?Z)]]

        >>> to_cnf_lol(Term("P"))
        [[P]]

        >>> to_cnf_lol(Or(Term("P"), Term("Q")))
        [[P, Q]]
        >>> to_cnf_lol(And(Term("P"), Term("Q")))
        [[P], [Q]]

        >>> to_cnf_lol(Exists([X], Term("Q", X)))
        [[Q(sk__1)]]

        >>> to_cnf_lol(Exists([X], Term("Q", X)), skip_skolemization=True)
        [[Exists(X: str : Q(?X))]]

    :param sentence:
    :param kwargs:
    :return:

    """
    sentence = to_cnf(sentence, **kwargs)
    sentence = simplify(sentence)
    if not isinstance(sentence, And):
        sentence = And(sentence)
    return [list(op.operands) if isinstance(op, Or) else [op] for op in sentence.operands]


def existentials_to_constraints(sentence: Sentence) -> Sentence:
    """
    Unwinds existentials into constraints

    Examples:

        >>> from typedlogic import And, Or, Variable, Term, Forall
        >>> X = Variable("X", "str")
        >>> Y = Variable("Y", "str")
        >>> Z = Variable("Z", "str")
        >>> existentials_to_constraints(Implies(Term("Q", X), Exists([Y], Term("R", X, Y))))
        Implies(And(Q(?X), NegationAsFailure(R(?X, ?_Y))), Or())


    :param sentence:
    :return:
    """
    if isinstance(sentence, And):
        return And(*[existentials_to_constraints(op) for op in sentence.operands])
    if isinstance(sentence, Or):
        return Or(*[existentials_to_constraints(op) for op in sentence.operands])
    if isinstance(sentence, Forall):
        return Forall(
            sentence.variables, existentials_to_constraints(sentence.sentence)
        )
    if isinstance(sentence, Iff):
        return And(
            existentials_to_constraints(Implies(sentence.left, sentence.right)),
            existentials_to_constraints(Implies(sentence.right, sentence.left)),
        )
    if isinstance(sentence, Implied):
        return Implies(existentials_to_constraints(sentence.antecedent),
                       existentials_to_constraints(sentence.consequent))
    if isinstance(sentence, Implies):
        consequent = sentence.consequent
        if isinstance(consequent, Exists):
            consequent = And(consequent)
        if isinstance(consequent, And):
            existentials = [anonymize_existential(op) for op in consequent.operands if isinstance(op, Exists)]
            if existentials:
                remains = [op for op in consequent.operands if not isinstance(op, Exists)]
                # TODO: rename_variables to anonymize
                constraints = [Implies(And(sentence.antecedent, NegationAsFailure(x.sentence)), Or()) for x in existentials]
                # Return the modified implication
                if remains:
                    rewritten = And(Implies(sentence.antecedent, And(*remains)),
                                   *constraints)
                else:
                    rewritten = And(*constraints)
                return simplify(rewritten)
    return sentence

def to_horn_rules(sentence: Sentence, allow_disjunctions_in_head=False, allow_goal_clauses=None) -> List[Sentence]:
    """
    Convert a sentence to a list of Horn rules.

    Examples
    --------
        >>> from typedlogic import And, Or, Variable, Term, Forall
        >>> X = Variable("X", "str")
        >>> Y = Variable("Y", "str")
        >>> Z = Variable("Z", "str")
        >>> P = Term("P")
        >>> Q = Term("Q")
        >>> R = Term("R")
        >>> S = Term("S")
        >>> print(as_prolog(to_horn_rules(R >> (Q & P))))
        q :- r.
        p :- r.
        >>> print(as_prolog(to_horn_rules((R >> Q) & (R >> P))))
        q :- r.
        p :- r.
        >>> print(as_prolog(to_horn_rules((R & S) >> P)))
        p :- r, s.

        >>> print(as_prolog(to_horn_rules(Not(P), allow_goal_clauses=True)))
        :- p.

        Goal clauses (integrity constraints) are only emitted when `allow_goal_clauses`
        is set; otherwise they are (silently) dropped, weakening the program:

        >>> to_horn_rules(Not(P))
        []

        >>> print(as_prolog(to_horn_rules(~P >> Q)))
        q :- \+ (p).

        >>> print(to_horn_rules(~P >> Q, allow_disjunctions_in_head=False, allow_goal_clauses=True))
        [Implies(And(Not(P)), Q)]

        >>> print(to_horn_rules(~P >> Q, allow_disjunctions_in_head=True, allow_goal_clauses=True))
        [Implies(And(), Or(P, Q))]

    :param sentence:
    :param allow_disjunctions_in_head:
    :return:

    """
    if allow_goal_clauses is None:
        allow_goal_clauses = allow_disjunctions_in_head
    sentence = transform_sentence(sentence, lambda s: s.to_model_object() if isinstance(s, Extension) else s)
    sentence = simplify(sentence)
    # TODO: check if already in horn profile
    cnf_lol = to_cnf_lol(sentence, skip_skolemization=True)
    rules: List[Sentence] = []
    for dnf_sentence in cnf_lol:
        # separate into positive and negative literals
        positive = []  # head
        negative = []  # body
        for lit in dnf_sentence:
            if isinstance(lit, Not):
                negative.append(lit.negated)
            else:
                positive.append(lit)
        if not positive and not negative:
            # The empty clause, consisting of no literals (which is equivalent to false) is a goal clause
            if allow_goal_clauses:
                rules.append(Implies(And(), Or()))
            continue
        # a horn clause is a disjunction of literals with at most one positive literal.
        if len(positive) > 1 and not allow_disjunctions_in_head:
            # not a horn clause (and not disjunctive datalog).
            # we could potentially generate multiple rules here, but this could
            # lead to stratified negation issues. We choose the last to be order preserving
            pos = positive[-1]
            other_pos = positive[:-1]
            anded = negative + [Not(other) for other in other_pos]
            rules.append(Implies(And(*anded), pos))
            # TODO: uncomment this to generate multiple rules
            # for pos in positive:
            #    other_pos = [p for p in positive if p != pos]
            #    anded = negative + [Not(other) for other in other_pos]
            #    rules.append(Implies(And(*anded), pos))
            continue
        # a unit clause is a disjunction of literals with no negative literals
        body = And(*negative) if len(negative) != 1 else negative[0]
        if not positive and allow_goal_clauses:
            # A Horn clause without a positive literal is a goal clause.
            # Or() == False
            rules.append(Implies(body, Or()))
        if len(positive) == 1:
            head = positive[0]
            rules.append(Implies(body, head))
        if len(positive) > 1:
            # we must be in disjunctive datalog at this point
            head = Or(*positive)
            rules.append(Implies(body, head))
    return rules


def expand_xor(sentence: Sentence) -> Sentence:
    """
    Expand XOR in a sentence.

    Replace A ⊕ B with (A ∨ B) ∧ ¬(A ∧ B)

        >>> from typedlogic import And, Or, Variable, Term, Forall
        >>> P = Term("P")
        >>> Q = Term("Q")
        >>> expand_xor(P ^ Q)
        And(Or(P, Q), Not(And(P, Q)))

    :param sentence:
    :return:
    """
    if not isinstance(sentence, Xor):
        return sentence
    # expand XOR to an OR plus an AND, where len(operands) may be > 2
    operands = sentence.operands
    if len(operands) == 1:
        return operands[0]
    return And(Or(*operands), Not(And(*operands)))


def expand_exactly_one(sentence: Sentence) -> Sentence:
    """
    Expand ExactlyOne in a sentence.

    Replace ExactlyOne(A, B, ...) with a disjunction where each disjunct asserts
    one operand and negates the rest.

        >>> from typedlogic import And, Or, Term
        >>> P = Term("P")
        >>> Q = Term("Q")
        >>> R = Term("R")
        >>> expand_exactly_one(ExactlyOne(P, Q))
        And(Or(P, Q), Not(And(P, Q)))
        >>> expand_exactly_one(ExactlyOne(P, Q, R))
        Or(And(P, Not(Or(Q, R))), And(Q, Not(Or(P, R))), And(R, Not(Or(P, Q))))

    :param sentence:
    :return:
    """
    if not isinstance(sentence, ExactlyOne):
        return sentence
    # expand XOR to an OR plus an AND, where len(operands) may be > 2
    operands = sentence.operands
    if len(operands) == 1:
        return operands[0]
    if len(operands) == 2:
        return And(Or(*operands), Not(And(*operands)))
    return Or(*[And(op, Not(Or(*[op2 for op2 in operands if op2 != op]))) for op in operands])


def eliminate_all_implications_recursive(sentence: Sentence) -> Sentence:
    """
    Replace A → B with ¬A ∨ B
    Replace A ↔ B with (A → B) ∧ (B → A), then apply the above rule

    Replace A ↔ B with (A → B) ∧ (B → A)

        >>> from typedlogic import Iff, Variable, Term, Forall
        >>> P = Term("P")
        >>> Q = Term("Q")
        >>> R = Term("R")
        >>> print(eliminate_all_implications_recursive(P >> Q))
        (~P) | (Q)
        >>> print(eliminate_all_implications_recursive(Iff(P, Q)))
        ((~P) | (Q)) & ((~Q) | (P))
        >>> print(eliminate_all_implications_recursive(P & ( Q >> R)))
        (P) & ((~Q) | (R))

    :param sentence:
    :return:
    """

    def eliminate_implies(sentence: Sentence) -> Sentence:
        if isinstance(sentence, Implies):
            return Or(Not(sentence.antecedent), sentence.consequent)
        return sentence

    def eliminate_implied(sentence: Sentence) -> Sentence:
        if isinstance(sentence, Implied):
            return Implies(sentence.antecedent, sentence.consequent)
        return sentence

    def eliminate_iff(sentence: Sentence) -> Sentence:
        if isinstance(sentence, Iff):
            return And(
                Implies(sentence.left, sentence.right),
                Implies(sentence.right, sentence.left),
            )
        return sentence

    return transform_sentence_chained(sentence, [eliminate_iff, eliminate_implied, eliminate_implies])


def eliminate_iff(sentence: Sentence) -> Sentence:
    """
    Eliminate iff from a sentence.

    Replace A ↔ B with (A → B) ∧ (B → A)

        >>> from typedlogic import Iff, Variable, Term, Forall
        >>> X = Variable("X", "str")
        >>> Y = Variable("Y", "str")
        >>> sentence = Iff(Term("Q", X), Term("R", Y))
        >>> eliminate_iff(sentence)
        And(Implies(Q(?X), R(?Y)), Implies(R(?Y), Q(?X)))

        >>> sentence = Forall([X], Iff(Term("Q", X), Term("R", Y)))
        >>> eliminate_iff(sentence)
        Forall([X: str] : Iff(Q(?X), R(?Y)))

    Note: does not recurse, use :ref:`transform_sentence` to apply to all sub-sentences.

    :param sentence:
    :return:
    """
    if not isinstance(sentence, Iff):
        return sentence
    return And(
        Implies(sentence.left, sentence.right),
        Implies(sentence.right, sentence.left),
    )


def eliminate_implied(sentence: Sentence) -> Sentence:
    """
    Eliminate implied from a sentence.

    This simply reverses the direction of the implication.

        >>> from typedlogic import Implied, Variable, Term, Forall
        >>> X = Variable("X", "str")
        >>> Y = Variable("Y", "str")
        >>> sentence = Implied(Term("Q", X), Term("R", Y))
        >>> eliminate_implied(sentence)
        Implies(R(?Y), Q(?X))

    Note: does not recurse, use :ref:`transform_sentence` to apply to all sub-sentences.

    :param sentence:
    :return:
    """
    if not isinstance(sentence, Implied):
        return sentence
    return Implies(sentence.operands[1], sentence.operands[0])


def eliminate_implies(sentence: Sentence) -> Sentence:
    """
    Eliminate implies from a sentence in translation to CNF

    Replace A → B with ¬A ∨ B

        >>> from typedlogic import Implies, Variable, Term, Forall
        >>> X = Variable("X", "str")
        >>> Y = Variable("Y", "str")
        >>> sentence = Implies(Term("Q", X), Term("R", Y))
        >>> eliminate_implies(sentence)
        Or(Not(Q(?X)), R(?Y))

    Note: does not recurse, use :ref:`transform_sentence` to apply to all sub-sentences.
    """
    if not isinstance(sentence, Implies):
        return sentence
    return Or(Not(sentence.operands[0]), sentence.operands[1])


def apply_demorgans(sentence: Sentence) -> Sentence:
    """
    Apply De Morgan's laws to a sentence.

    Replace ¬(A ∧ B) with ¬A ∨ ¬B
    Replace ¬(A ∨ B) with ¬A ∧ ¬B

        >>> from typedlogic import And, Or, Not, Variable, Term, Forall
        >>> X = Variable("X", "str")
        >>> Y = Variable("Y", "str")
        >>> sentence = Not(And(Term("Q", X), Term("R", Y)))
        >>> apply_demorgans(sentence)
        Or(Not(Q(?X)), Not(R(?Y)))

    Note: does not recurse, use :ref:`transform_sentence` to apply to all sub-sentences.

    :param sentence:
    :return:
    """
    if not isinstance(sentence, Not):
        return sentence
    negated = sentence.negated
    if isinstance(negated, And):
        return Or(*[Not(op) for op in negated.operands])
    if isinstance(negated, Or):
        return And(*[Not(op) for op in negated.operands])
    return sentence


def apply_quantifier_negation(sentence: Sentence) -> Sentence:
    """
    Apply negation of quantifiers to a sentence.

    Replace ¬∀x P(x) with ∃x ¬P(x)
    Replace ¬∃x P(x) with ∀x ¬P(x)

        >>> from typedlogic import Forall, Variable, Term
        >>> X = Variable("X", "str")
        >>> sentence = Not(Forall([X], Term("P", X)))
        >>> apply_quantifier_negation(sentence)
        Exists(X: str : Not(P(?X)))

    :param sentence:
    :return:
    """
    if not isinstance(sentence, Not):
        return sentence
    negated = sentence.negated
    if isinstance(negated, Forall):
        return Exists(negated.variables, Not(negated.sentence))
    if isinstance(negated, Exists):
        return Forall(negated.variables, Not(negated.sentence))
    return sentence


def force_stratification(horn_rules: List[Sentence]) -> List[Sentence]:
    """
    Force stratification of a list of horn rules.

    If the program is not stratified, remove a rule using negation that causes the issue
    and recurse.

    Note that this will weaken the program, but it will be stratified.

        >>> from typedlogic import Implies, Variable, Term, Forall
        >>> P = Term("P")
        >>> Q = Term("Q")
        >>> R = Term("R")
        >>> sentence = Iff(P&Q, R)
        >>> rules = to_horn_rules(sentence)
        >>> force_stratification(rules)
        [Implies(And(P, Q), R), Implies(R, P), Implies(R, Q)]
        >>> sentence = And(Iff(P|Q, R), Iff(P, ~Q))
        >>> rules = to_horn_rules(sentence)
        >>> rules
        [Implies(P, R), Implies(Q, R), Implies(And(R, Not(P)), Q), Implies(And(Not(Q)), P)]
        >>> force_stratification(rules)
        [Implies(P, R), Implies(Q, R), Implies(And(R, Not(P)), Q)]

    :param horn_rules:
    :return:
    """
    pmap: Dict[str, List[Tuple[str, bool]]] = defaultdict(list)
    edge_to_rules = defaultdict(list)
    for i, rule in enumerate(horn_rules):
        if isinstance(rule, Implies):
            head = rule.consequent
            if not isinstance(head, Term):
                continue
            pred = head.predicate
            body = rule.antecedent
            if isinstance(body, And):
                terms = list(body.operands)
            else:
                terms = [body]
            for term in terms:
                negated = False
                if isinstance(term, Not):
                    term = term.negated
                    negated = True
                if not isinstance(term, Term):
                    continue
                pmap[pred].append((term.predicate, negated))
                if negated:
                    edge_to_rules[(pred, term.predicate)].append(i)
    is_stratified, edge, _ = analyze_datalog_program(list(pmap.items()))
    if not is_stratified:
        if not edge:
            raise AssertionError
        candidates = edge_to_rules[edge] if edge in edge_to_rules else []
        if not candidates:
            raise AssertionError(f"Stratification failed; cannot find {edge} in {edge_to_rules}")
        rule_to_remove = candidates[0]
        horn_rules = [rule for i, rule in enumerate(horn_rules) if i != rule_to_remove]
        return force_stratification(horn_rules)
    return horn_rules


def ensure_terms_positional(theory: Theory):
    """
    Ensure that all terms in a theory have all positions filled and ordered.

        >>> from typedlogic import Term, Variable, PredicateDefinition, Theory
        >>> X = Variable("X", "str")
        >>> Y = Variable("Y", "str")
        >>> theory = Theory(predicate_definitions=[PredicateDefinition("P", {"x": "str", "y": "str"})])
        >>> s1 = Term("P", X, Y)
        >>> s2 = Term("P", {"x": X, "y": Y})
        >>> s3 = Term("P", {"y": Y, "x": X})
        >>> s4 = Term("P", {"y": Y})
        >>> s5 = Term("P", {})
        >>> theory.add(s1)
        >>> theory.add(s2)
        >>> theory.add(s3)
        >>> theory.add(s4)
        >>> theory.add(s5)
        >>> ensure_terms_positional(theory)
        >>> for s in theory.sentences:
        ...     print(s)
        P(?X, ?Y)
        P(?X, ?Y)
        P(?X, ?Y)
        P(None, ?Y)
        P(None, None)

    :param theory:
    :return:
    """

    def tr(s: Sentence):
        if isinstance(s, Term):
            pds = [pd for pd in theory.predicate_definitions if pd.predicate == s.predicate]
            if len(pds) != 1:
                # could include builtins
                return
            pd = pds[0]
            if s.positional is False:
                s.bindings = {k: s.bindings.get(k) for k, v in pd.arguments.items()}

    for s in theory.sentences:
        transform_sentence(s, tr)


def contains_negation_as_failure(sentence: Sentence) -> bool:
    """
    Check whether a sentence contains a :class:`NegationAsFailure` anywhere in its structure.

        >>> from typedlogic import Term, Variable, Forall
        >>> X = Variable("X", "str")
        >>> P = Term("P", X)
        >>> Q = Term("Q", X)
        >>> contains_negation_as_failure(P >> Q)
        False
        >>> contains_negation_as_failure(Forall([X], And(P, NegationAsFailure(Q)) >> Q))
        True

    :param sentence: the sentence to inspect
    :return: True if any subformula is a NegationAsFailure
    """
    if isinstance(sentence, NegationAsFailure):
        return True
    if isinstance(sentence, QuantifiedSentence):
        return contains_negation_as_failure(sentence.sentence)
    if isinstance(sentence, CardinalityConstraint):
        parts = [p for p in (sentence.template, sentence.conditions) if p is not None]
        return any(contains_negation_as_failure(p) for p in parts)
    if isinstance(sentence, BooleanSentence):
        return any(contains_negation_as_failure(op) for op in sentence.operands)
    return False


def _naf_predicates(sentence: Sentence) -> Set[str]:
    """
    Collect the predicates of atoms appearing (directly) under a NegationAsFailure.

    :param sentence: the sentence to inspect
    :return: set of predicate names negated by NAF
    """
    result: Set[str] = set()
    if isinstance(sentence, NegationAsFailure):
        for term in _terms_in(sentence.negated):
            result.add(term.predicate)
        return result
    if isinstance(sentence, QuantifiedSentence):
        return _naf_predicates(sentence.sentence)
    if isinstance(sentence, CardinalityConstraint):
        for part in (sentence.template, sentence.conditions):
            if part is not None:
                result |= _naf_predicates(part)
        return result
    if isinstance(sentence, BooleanSentence):
        for op in sentence.operands:
            result |= _naf_predicates(op)
    return result


def _terms_in(sentence: Sentence) -> Iterable[Term]:
    """
    Yield every Term atom in a sentence tree.

    :param sentence: the sentence to inspect
    :return: iterator over contained terms
    """
    if isinstance(sentence, CardinalityConstraint):
        for part in (sentence.template, sentence.conditions):
            if part is not None:
                yield from _terms_in(part)
        return
    if isinstance(sentence, Term):
        yield sentence
        return
    if isinstance(sentence, QuantifiedSentence):
        yield from _terms_in(sentence.sentence)
        return
    if isinstance(sentence, BooleanSentence):
        for op in sentence.operands:
            yield from _terms_in(op)


def _predicates_at_polarity(sentence: Sentence, positive: bool = True) -> Set[str]:
    """
    Collect predicates occurring at the given polarity in a sentence.

    Used to decide whether a sentence could *assert* atoms of a predicate (positive
    polarity) as opposed to merely testing them (negative polarity). Iff, Xor,
    ExactlyOne and cardinality constraints are treated conservatively as containing
    their predicates at both polarities.

    :param sentence: the sentence to inspect
    :param positive: the polarity of the current position
    :return: predicates occurring at the requested polarity
    """
    if isinstance(sentence, CardinalityConstraint):
        result: Set[str] = set()
        for part in (sentence.template, sentence.conditions):
            if part is not None:
                result |= {t.predicate for t in _terms_in(part)}
        return result
    if isinstance(sentence, Term):
        return {sentence.predicate} if positive else set()
    if isinstance(sentence, (Not, NegationAsFailure)):
        return _predicates_at_polarity(sentence.negated, not positive)
    if isinstance(sentence, Implies):
        return _predicates_at_polarity(sentence.antecedent, not positive) | _predicates_at_polarity(
            sentence.consequent, positive
        )
    if isinstance(sentence, Implied):
        return _predicates_at_polarity(sentence.operands[0], positive) | _predicates_at_polarity(
            sentence.operands[1], not positive
        )
    if isinstance(sentence, (Iff, Xor, ExactlyOne)):
        return {t.predicate for t in _terms_in(sentence)}
    if isinstance(sentence, QuantifiedSentence):
        return _predicates_at_polarity(sentence.sentence, positive)
    if isinstance(sentence, BooleanSentence):
        result = set()
        for op in sentence.operands:
            result |= _predicates_at_polarity(op, positive)
        return result
    return set()


def _destructure_definite_rules(sentence: Sentence) -> Optional[List[Tuple[Term, Sentence]]]:
    """
    Destructure a sentence into (head, body) rule pairs, if it has definite rule form.

    Recognized forms are an optionally universally quantified fact, ``body -> head``,
    or ``head <- body``, where the head is an atom or a conjunction of atoms
    (a conjunctive head yields one rule per conjunct). Returns None for any other form.

    :param sentence: the sentence to destructure
    :return: list of (head, body) pairs, or None if the sentence is not a definite rule
    """
    s = sentence
    while isinstance(s, Forall):
        s = s.sentence
    if isinstance(s, CardinalityConstraint):
        return None
    if isinstance(s, Term):
        return [(s, And())]
    if isinstance(s, Implied):
        s = Implies(s.operands[1], s.operands[0])
    if not isinstance(s, Implies):
        return None
    head = s.consequent
    body = s.antecedent
    if isinstance(head, Term) and not isinstance(head, CardinalityConstraint):
        return [(head, body)]
    if isinstance(head, And):
        head_atoms = [op for op in head.operands if isinstance(op, Term) and not isinstance(op, CardinalityConstraint)]
        if len(head_atoms) == len(head.operands):
            return [(h, body) for h in head_atoms]
    return None


def _body_literal_polarities(body: Sentence) -> List[Tuple[str, bool]]:
    """
    Collect (predicate, is_negative) dependency edges from a rule body.

    A body atom counts as negative when it occurs under an odd number of
    negations (classical or negation-as-failure).

    :param body: the rule body
    :return: list of (predicate, is_negative) pairs
    """
    positive = _predicates_at_polarity(body, positive=True)
    negative = _predicates_at_polarity(body, positive=False)
    return [(p, False) for p in sorted(positive)] + [(p, True) for p in sorted(negative)]


def _replace_naf_with_not(sentence: Sentence) -> Sentence:
    """
    Rewrite every NegationAsFailure in a sentence to a classical Not.

    :param sentence: the sentence to rewrite
    :return: the rewritten sentence
    """

    def tr(s: Sentence) -> Sentence:
        if isinstance(s, NegationAsFailure):
            return Not(s.negated)
        return s

    return transform_sentence(sentence, tr)


def clark_completion(
    theory: Theory,
    predicates: Optional[Collection[str]] = None,
    strict: bool = False,
) -> Theory:
    """
    Render a theory using negation-as-failure into classical FOL via (partial) Clark completion.

    Predicates tested by negation-as-failure are *completed*: an "only if" axiom is added
    stating that the predicate holds only when one of its defining rule bodies (or facts)
    holds. All ``NegationAsFailure`` operators are then replaced with classical ``Not``.
    Together with the original rules (the "if" direction), this yields the Clark completion
    of each completed predicate, giving classical solvers such as Z3 or Prover9 a faithful
    reading of stratified NAF programs.

        >>> from typedlogic import Forall, Implies, PredicateDefinition, Term, Theory, Variable
        >>> x = Variable("x", "str")
        >>> theory = Theory(predicate_definitions=[
        ...     PredicateDefinition("bird", {"x": "str"}),
        ...     PredicateDefinition("abnormal", {"x": "str"}),
        ...     PredicateDefinition("flies", {"x": "str"}),
        ... ])
        >>> theory.add(Forall([x], Implies(And(Term("bird", x), NegationAsFailure(Term("abnormal", x))),
        ...            Term("flies", x))))
        >>> completed = clark_completion(theory)
        >>> for s in completed.sentences:
        ...     print(as_fol(s))
        ∀[x:str]. bird(x) ∧ ¬abnormal(x) → flies(x)
        ∀[x:str]. ¬abnormal(x)

    Here ``abnormal`` has no defining rules or facts, so its completion closes it off
    entirely. A predicate with defining rules is completed to the disjunction of its
    rule bodies:

        >>> theory2 = Theory(predicate_definitions=[
        ...     PredicateDefinition("penguin", {"x": "str"}),
        ...     PredicateDefinition("abnormal", {"x": "str"}),
        ...     PredicateDefinition("bird", {"x": "str"}),
        ...     PredicateDefinition("flies", {"x": "str"}),
        ... ])
        >>> theory2.add(Forall([x], Implies(Term("penguin", x), Term("abnormal", x))))
        >>> theory2.add(Forall([x], Implies(And(Term("bird", x), NegationAsFailure(Term("abnormal", x))),
        ...             Term("flies", x))))
        >>> completed2 = clark_completion(theory2)
        >>> for s in completed2.sentences:
        ...     print(as_fol(s))
        ∀[x:str]. penguin(x) → abnormal(x)
        ∀[x:str]. bird(x) ∧ ¬abnormal(x) → flies(x)
        ∀[x:str]. abnormal(x) → (penguin(x))
        ∀[x:str]. ¬penguin(x)

    Note that ``penguin`` is completed as well (here to "there are no penguins",
    since the example declares no penguin facts): ``abnormal`` is defined in terms
    of ``penguin``, so closing ``abnormal`` requires closing ``penguin`` too.
    Ground facts contribute equality disjuncts, so with a fact ``penguin(pingu)``
    the last axiom would instead be ``∀[x:str]. penguin(x) → (x == 'pingu')``.

    The program restricted to the completed predicates must be a definite logic program:
    each completed predicate may only be defined by facts and rules with an atomic
    (or conjunctive-atomic) head. If a completed predicate occurs positively in any
    other kind of sentence, a :class:`NotInProfileError` is raised, since the
    completion axiom would then be unsound.

    If the program is not stratified, the completion may not agree with the
    stable-model semantics; by default a warning is logged (every stable model is
    still a model of the completion, so proving against the completion remains
    cautious/sound), and with ``strict=True`` a :class:`NotInProfileError` is raised.

    :param theory: the theory to transform
    :param predicates: predicates to complete; defaults to all predicates tested by NAF,
        plus every predicate they transitively depend on. Builtin comparison predicates
        (eq, lt, ...) are never completed; NAF over a builtin is simply rewritten to
        classical negation.
    :param strict: if True, raise instead of warning when the program is not stratified
    :return: a new theory with NAF replaced by classical negation plus completion axioms
    """
    axiom_sentences = theory.sentences

    # destructure axioms into definite rules where possible
    rules: List[Tuple[Term, Sentence]] = []
    non_rules: List[Sentence] = []
    for s in axiom_sentences:
        destructured = _destructure_definite_rules(s)
        if destructured is None:
            non_rules.append(s)
        else:
            rules.extend(destructured)

    if predicates is None:
        targets: Set[str] = set()
        for s in axiom_sentences:
            targets |= _naf_predicates(s)
        # builtins (eq, lt, ...) have fixed interpretations: ``not eq(...)`` is rewritten
        # to classical negation below, but there is nothing to complete
        targets -= _BUILTIN_PREDICATES
        # For ``not q`` to carry its stable-model meaning classically, q's definition must
        # be closed, which in turn requires closing the predicates q depends on: complete
        # the full dependency closure of the NAF-tested predicates (builtins excluded).
        body_dependencies: Dict[str, Set[str]] = defaultdict(set)
        for head, body in rules:
            body_dependencies[head.predicate] |= {
                t.predicate for t in _terms_in(body) if t.predicate not in _BUILTIN_PREDICATES
            }
        queue = list(targets)
        while queue:
            for dep in body_dependencies.get(queue.pop(), set()):
                if dep not in targets:
                    targets.add(dep)
                    queue.append(dep)
    else:
        targets = set(predicates)

    # completion is only sound if completed predicates are defined exclusively by
    # definite rules and facts
    for s in non_rules:
        offending = _predicates_at_polarity(s, positive=True) & targets
        if offending:
            raise NotInProfileError(
                f"Cannot Clark-complete predicate(s) {sorted(offending)}: "
                f"asserted (positively) by a non-rule sentence: {s}"
            )

    # stratification check over the rule dependency graph
    dependency_map: Dict[str, List[Tuple[str, bool]]] = defaultdict(list)
    for head, body in rules:
        dependency_map[head.predicate].extend(_body_literal_polarities(body))
    is_stratified, edge, _ = analyze_datalog_program(list(dependency_map.items()))
    if not is_stratified:
        msg = (
            f"Program is not stratified (negative cycle through {edge}); the Clark completion "
            "may be weaker than, or inconsistent with, the stable-model semantics"
        )
        if strict:
            raise NotInProfileError(msg)
        logger.warning(msg)

    completions: List[Sentence] = []
    predicate_definition_map = theory.predicate_definition_map
    for target in sorted(targets):
        pd = predicate_definition_map.get(target)
        defining = [(head, body) for head, body in rules if head.predicate == target]
        defining += [(t, And()) for t in theory.ground_terms if t.predicate == target]
        arg_types: List[Optional[str]]
        if pd is not None:
            arg_names = list(pd.arguments.keys())
            arg_types = [t if isinstance(t, str) else None for t in pd.arguments.values()]
        elif defining:
            arity = len(defining[0][0].bindings)
            arg_names = [f"x{i + 1}" for i in range(arity)]
            arg_types = [None] * arity
        else:
            raise NotInProfileError(
                f"Cannot Clark-complete predicate '{target}': no predicate definition and no defining rules"
            )
        canonical_vars = [Variable(name, domain=typ) for name, typ in zip(arg_names, arg_types, strict=True)]
        canonical_names = set(arg_names)

        disjuncts: List[Sentence] = []
        for rule_index, (head, body) in enumerate(defining):
            if pd is not None and head.positional is False:
                head_args = [head.bindings.get(k) for k in arg_names]
            else:
                head_args = list(head.bindings.values())
            if len(head_args) != len(canonical_vars):
                raise NotInProfileError(
                    f"Arity mismatch for '{target}': head {head} does not match arguments {arg_names}"
                )
            varmap: Dict[str, Variable] = {}
            equalities: List[Sentence] = []
            for zvar, arg in zip(canonical_vars, head_args, strict=True):
                if isinstance(arg, Variable) and arg.name not in varmap:
                    varmap[arg.name] = zvar
                elif isinstance(arg, Variable):
                    # repeated head variable: constrain to the canonical var it maps to
                    equalities.append(Term("eq", zvar, varmap[arg.name]))
                else:
                    equalities.append(Term("eq", zvar, arg))
            # standardize apart body variables that clash with the canonical head variables
            for v in _variables_in_order(body):
                if v.name not in varmap and v.name in canonical_names:
                    varmap[v.name] = Variable(f"{v.name}__d{rule_index}", domain=v.domain)
            renamed_body = map_variables(body, varmap)
            body_conjuncts = conjunction_as_list(renamed_body)
            inner_operands = equalities + [c for c in body_conjuncts if not (isinstance(c, And) and not c.operands)]
            inner: Sentence = inner_operands[0] if len(inner_operands) == 1 else And(*inner_operands)
            existential_vars = [v for v in _variables_in_order(renamed_body) if v.name not in canonical_names]
            if existential_vars:
                inner = Exists(existential_vars, inner)
            disjuncts.append(inner)

        head_atom = Term(target, *canonical_vars) if canonical_vars else Term(target)
        only_if: Sentence = Implies(head_atom, Or(*disjuncts)) if disjuncts else Not(head_atom)
        if canonical_vars:
            only_if = Forall(canonical_vars, only_if)
        # rule bodies copied into the disjuncts may themselves contain NAF
        completions.append(_replace_naf_with_not(only_if))

    new_groups = [
        replace(sg, sentences=[_replace_naf_with_not(s) for s in sg.sentences or []]) for sg in theory.sentence_groups
    ]
    if completions:
        new_groups.append(
            SentenceGroup(
                name="clark_completion",
                group_type=SentenceGroupType.AXIOM,
                sentences=completions,
            )
        )
    return replace(theory, sentence_groups=new_groups)
