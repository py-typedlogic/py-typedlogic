"""
Function for performing transformation and manipulation of Sentences and Theories
"""
import json
from collections import defaultdict
from copy import copy
from dataclasses import dataclass, field
from typing import List, Iterator, Iterable, Mapping, Callable, Optional, Dict, Any, Union, Type, Tuple

from typedlogic import Theory, Forall, Variable, Implies, Term, SentenceGroup, Sentence, BooleanSentence, \
    NegationAsFailure
from typedlogic.builtins import NUMERIC_BUILTINS, NAME_TO_INFIX_OP
from typedlogic.datamodel import Iff, And, Implied, Or, QuantifiedSentence, Not, Exists, Extension, Xor, ExactlyOne, \
    NotInProfileError
from typedlogic.utils.detect_stratified_negation import analyze_datalog_program


def sentences_from_predicate_hierarchy(theory: Theory) -> List[Sentence]:
    new_sentences: List[Sentence] = []
    if not theory.predicate_definitions:
        raise ValueError("Theory must have predicate definitions")
    for pd in theory.predicate_definitions:
        if pd.parents:
            for parent in pd.parents:
                # bindings = {arg: Variable(arg, domain=typ) for arg, typ in pd.arguments.items()}
                vars = [Variable(arg, domain=typ) for arg, typ in pd.arguments.items()]
                args = [Variable(arg) for arg in pd.arguments]
                impl = Implies(
                        antecedent=Term(parent, *args),
                        consequent=Term(pd.predicate, *args),
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
        [Forall([name: str] : Implies(Thing(?name), Person(?name)))]

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

def disjunction_as_list(sentence: Sentence) ->List[Sentence]:
    if isinstance(sentence, Or):
        return list(sentence.operands)
    return [sentence]

def conjunction_as_list(sentence: Sentence) -> List[Sentence]:
    if isinstance(sentence, And):
        return list(sentence.operands)
    return [sentence]

@dataclass
class PrologConfig:
    """
    Configuration for Prolog output.
    """
    use_lowercase_vars: Optional[bool] = False
    use_uppercase_predicates: Optional[bool]  = False
    disjunctive_datalog: Optional[bool]  = False
    operator_map: Optional[Mapping[str, str]] = None
    negation_symbol : str = field(default=r'\+')
    negation_as_failure_symbol : str = field(default=r'\+')
    assume_negation_as_failure: bool = False
    double_quote_strings: bool = False
    include_parens_for_zero_args: bool = False
    allow_function_terms: bool = True
    allow_nesting: bool = True
    null_term: str = "null(_)"
    allow_skolem_terms: bool = False

def as_prolog(sentence: Union[Sentence, List[Sentence]], config: Optional[PrologConfig]=None, depth=0, translate=False, strict=True) -> str:
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

    :param sentence: the sentence to render
    :param config:
    :param depth:
    :param translate:
    :param strict:
    :return:
    """
    if isinstance(sentence, list):
        return "\n".join(as_prolog(s, config, depth=depth) for s in sentence)
    if not config:
        config = PrologConfig()
    def _paren(s: str) -> str:
        if config.allow_nesting:
            return f"({s})"
        return s
    if translate:
        rules = to_horn_rules(sentence, allow_disjunctions_in_head=config.disjunctive_datalog)
        return "\n".join(as_prolog(s, config, depth=depth) for s in rules)
    if isinstance(sentence, Forall):
        sentence = sentence.sentence
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
        negated_clause = _paren(as_prolog(sentence.negated, config, depth+1))
        return f"{config.negation_symbol} {negated_clause}"
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
                if config.use_lowercase_vars:
                    return v.name
                return v.name.capitalize()
            if isinstance(v, Term):
                if not config.allow_function_terms:
                    raise ValueError(f"Nested term not supported: {v}")
                return as_prolog(v, config, depth+1)
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
    if not isinstance(sentence, Implies):
        raise NotInProfileError(f"Unsupported sentence {sentence}")
    # assumption: generation a (head :- body) implication
    if isinstance(sentence.consequent, Or) and len(sentence.consequent.operands) > 1:
        if not config.disjunctive_datalog:
            raise NotInProfileError(f"Disjunctions on LHS not allowed {sentence}")
    if isinstance(sentence.consequent, And):
        raise NotInProfileError(f"Conjunctions on LHS not allowed {sentence}\n"
                                "Transform using simplify_prolog_transform first")
    # check for unbound variables
    body_vars = []
    # eliminate Exists
    antecedent_list = [t.sentence if isinstance(t, Exists) else t for t in conjunction_as_list(sentence.antecedent)]
    for body_term in antecedent_list:
        if not isinstance(body_term, Term):
            # TODO: this currently assumes disjunctions are unrolled from body
            # raise NotInProfileError(f"Body must be a term {sentence}")
            continue
        body_vars.extend(body_term.variable_names)
    for head_term in disjunction_as_list(sentence.consequent):
        if isinstance(head_term, Not):
            continue
        if not isinstance(head_term, Term):
            raise NotInProfileError(f"Head must be a term, got: {type(head_term)} in {sentence}")
        head_vars = head_term.variable_names
        for v in head_vars:
            if v not in body_vars:
                raise NotInProfileError(f"Variable {v} in head not in body {sentence}")

    head = as_prolog(sentence.consequent, config, depth+1)
    body = as_prolog(sentence.antecedent, config, depth+1)
    if head.startswith("(") and head.endswith(")"):
        head = head[1:-1]
    if body == "true":
        return f"{head}."
    if head == "fail":
        return f":- {body}."
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
        if isinstance(sentence, Iff):
            sentences.append(Implies(sentence.left, sentence.right))
            sentences.append(Implies(sentence.right, sentence.left))
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


def as_fol(sentence, config: Optional[PrologConfig]=None) -> str:
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

    Examples:
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
        return f"({as_tptp(sentence.antecedent, config, depth + 1)} => {as_tptp(sentence.consequent, config, depth + 1)})"

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

    Examples:
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
        return f"({' & '.join(as_prover9(op, config, depth + 1) for op in sentence.operands)})"

    elif isinstance(sentence, Xor):
        return as_prover9(expand_xor(sentence), config, depth)

    elif isinstance(sentence, ExactlyOne):
        return as_prover9(expand_exactly_one(sentence), config, depth)

    elif isinstance(sentence, Or):
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
            format_var(v) if isinstance(v, Variable) else format_value(v) for v in sentence.bindings.values())
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

def transform_sentence(sentence: Sentence, rule: Callable[[Sentence], Sentence], varmap: Optional[Dict[str, Variable]] = None) -> Sentence:
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
    elif isinstance(sentence, Term):
        return sentence
    elif isinstance(sentence, Extension):
        return sentence.to_model_object()
    else:
        raise ValueError(f"Unknown sentence type {type(sentence)} // {sentence}")


def replace_constants(sentence: Sentence, constant_map: Dict[str, Any] ) -> Sentence:
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
        new_ops = []
        for op in sentence.operands:
            if isinstance(op, type(sentence)):
                new_ops.extend(op.operands)
            else:
                new_ops.append(op)
        return type(sentence)(*new_ops)
    return sentence



def skolemize(sentence: Sentence, universal_vars: Optional[List[Variable]] = None, substitution_map: Optional[Dict[str, Term]] = None) -> Sentence:
    """
    Skolemize a sentence.

    Examples:

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
        return Forall(sentence.variables, skolemize(sentence.sentence, universal_vars + sentence.variables, substitution_map))
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
        return Term(sentence.predicate,
                    {
                        k: substitution_map[v.name] if isinstance(v, Variable) and v.name in substitution_map else v
                        for k, v in sentence.bindings.items()
                    })
    else:
        raise ValueError(f"Unknown sentence type {type(sentence)} // {sentence}")


def to_cnf(sentence: Sentence, skip_skolemization=False) -> Sentence:
    """
    Convert a sentence to conjunctive normal form.

    Examples:

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
    #def raise_if_exists(s: Sentence) -> Sentence:
    #    if isinstance(s, Exists):
    #        raise NotInProfileError("Exists not allowed in CNF")
    #    return s

    #transform_sentence(sentence, raise_if_exists)
    # Drop universal quantifiers
    sentence = transform_sentence(sentence, lambda s: s.sentence if isinstance(s, Forall) else s)
    # Distribute OR over AND
    sentence = transform_sentence(sentence, distribute_and_over_or)
    return sentence

def to_cnf_lol(sentence: Sentence, **kwargs) -> List[List[Sentence]]:
    """
    Convert a sentence to a list of lists of sentences in conjunctive normal form.

    Examples:

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

    :param sentence:
    :param kwargs:
    :return:
    """
    sentence = to_cnf(sentence, **kwargs)
    sentence = simplify(sentence)
    if not isinstance(sentence, And):
        sentence = And(sentence)
    return [
        list(op.operands) if isinstance(op, Or) else [op] for op in sentence.operands
    ]

def to_horn_rules(sentence: Sentence, allow_disjunctions_in_head=False, allow_goal_clauses=None) -> List[Sentence]:
    """
    Convert a sentence to a list of Horn rules.

    Examples:

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
        >>> print(as_prolog(to_horn_rules((R & S) >> P)))
        p :- r, s.

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
        positive = [] # head
        negative = [] # body
        for lit in dnf_sentence:
            if isinstance(lit, Not):
                negative.append(lit.negated)
            else:
                positive.append(lit)
        if not positive and not negative:
            # The empty clause, consisting of no literals (which is equivalent to false) is a goal clause
            rules.append(Or())
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
            #for pos in positive:
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
            # we must be in disjunctive datalog at this pont
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
    if not isinstance(sentence, ExactlyOne):
        return sentence
    # expand XOR to an OR plus an AND, where len(operands) may be > 2
    operands = sentence.operands
    if len(operands) == 1:
        return operands[0]
    if len(operands) == 2:
        return And(Or(*operands), Not(And(*operands)))
    return Or(
        [And(op,
             Not(Or([op2 for op2 in operands if op2 != op])))
         for op in operands])


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
            if not s.positional:
                s.bindings = {k: s.bindings.get(k) for k, v in pd.arguments.items()}
    for s in theory.sentences:
        transform_sentence(s, tr)





