"""
Reflect a theory into ground facts of the metatheory vocabulary.

This is the bridge that makes rules about types possible without a second-order logic:
a :class:`~typedlogic.datamodel.Theory` goes in, and a list of ordinary facts comes out,
ready to be loaded into any solver alongside
:mod:`typedlogic.theories.metatheory.axioms`.

Reflection is deliberately partial. Constructs it cannot describe in the vocabulary --
arithmetic subterms, builtin comparisons, sentences with no Horn form -- are skipped
rather than approximated, so a derived diagnostic always corresponds to something really
present in the theory. The cost is that reflection alone proves nothing about what it
skipped; see :func:`skipped_sentences` to see what a given theory lost.
"""

from typing import Any, Dict, Iterable, List, Optional, Tuple

from typedlogic import Fact, Sentence, Term, Theory, Variable
from typedlogic.builtins import NUMERIC_BUILTINS
from typedlogic.datamodel import (
    And,
    Extension,
    Implies,
    NegationAsFailure,
    Not,
    NotInProfileError,
    PredicateDefinition,
    SentenceGroupType,
)
from typedlogic.theories.metatheory.vocabulary import (
    ArgName,
    ArgType,
    BaseType,
    BodyPredicate,
    ConstantPosition,
    HeadPredicate,
    NegatedBodyPredicate,
    PredicateDeclared,
    PredicateName,
    PredicateParent,
    RuleID,
    TypeBase,
    TypeExists,
    TypeName,
    TypeUnionMember,
    VarName,
    VarPosition,
)
from typedlogic.transformations import to_horn_rules

#: Base types always present in the subtype lattice, so that a branded type has something
#: to be a subtype *of* even when the theory declares no type definitions of its own.
BASE_TYPES = ("str", "int", "float", "bool")

#: Python types mapped to the base type names used in predicate declarations. `bool` is
#: checked before `int` because it is a subclass of it.
_PYTHON_BASE_TYPES: Tuple[Tuple[type, str], ...] = (
    (bool, "bool"),
    (int, "int"),
    (float, "float"),
    (str, "str"),
)


def _base_type_of(value: Any) -> Optional[str]:
    """
    Name the base type of a literal value.

    :param value: A literal appearing at an argument position
    :return: The base type name, or None if the value is of no type the vocabulary knows
    """
    for py_type, name in _PYTHON_BASE_TYPES:
        if isinstance(value, py_type):
            return name
    return None


def _positional_values(term: Term, pd: Optional[PredicateDefinition]) -> List[Tuple[int, Any]]:
    """
    Return a term's arguments paired with their declared positions.

    Keyword-indexed terms are matched against the predicate's declared argument order,
    keeping each value at its declared position: a term that omits an argument must not
    shift the ones after it into the omitted slot.

    :param term: The term whose arguments are wanted
    :param pd: The declaration for the term's predicate, if the theory has one
    :return: Pairs of declared position and argument value
    """
    if term.positional is False and pd is not None:
        return [(i, term.bindings[name]) for i, name in enumerate(pd.arguments) if name in term.bindings]
    return list(enumerate(term.values))


def _rule_terms(sentence: Sentence) -> Optional[Tuple[List[Term], List[Term], List[Term]]]:
    """
    Split a Horn rule into head terms, positive body terms, and negated body terms.

    :param sentence: A sentence already normalized by `to_horn_rules`
    :return: The three groups of terms, or None if the sentence has no rule shape
    """
    if isinstance(sentence, Term):
        return [sentence], [], []
    if not isinstance(sentence, Implies):
        return None
    head, body = sentence.consequent, sentence.antecedent
    heads = [t for t in _conjuncts(head) if isinstance(t, Term)]
    positive: List[Term] = []
    negative: List[Term] = []
    for literal in _conjuncts(body):
        # Both negations matter here: `Not` is classical, `NegationAsFailure` is what the
        # Python surface's unary minus produces. Either one makes the dependency negative.
        if isinstance(literal, (Not, NegationAsFailure)):
            negative.extend(t for t in _conjuncts(literal.operands[0]) if isinstance(t, Term))
        elif isinstance(literal, Term):
            positive.append(literal)
    return heads, positive, negative


def _conjuncts(sentence: Any) -> List[Sentence]:
    """
    Flatten a conjunction into its operands, treating anything else as a single operand.

    :param sentence: A sentence, possibly an `And`
    :return: The conjoined sentences
    """
    if isinstance(sentence, And):
        return [s for operand in sentence.operands for s in _conjuncts(operand)]
    if isinstance(sentence, Sentence):
        return [sentence]
    return []


def _is_builtin(predicate: str) -> bool:
    """
    Determine whether a predicate is a builtin operator rather than a theory predicate.

    :param predicate: The predicate name from a term
    :return: True for builtins such as `eq`, `lt`, and `add`
    """
    return predicate in NUMERIC_BUILTINS


def _described_rules(theory: Theory) -> Tuple[List[Tuple[str, Sentence]], List[Sentence]]:
    """
    Normalize a theory's asserted sentences to named Horn rules, tracking what was lost.

    Rules are named after the sentence group they came from so that diagnostics point at
    something the author recognizes, such as the decorated function's name. A sentence
    that cannot be normalized, or that normalizes to something with no rule shape, lands
    in the second list; deciding both outcomes in one pass keeps :func:`theory_to_facts`
    and :func:`skipped_sentences` from drifting apart.

    :param theory: The theory to normalize
    :return: Pairs of rule id and normalized sentence, and the sentences not described
    """
    rules: List[Tuple[str, Sentence]] = []
    skipped: List[Sentence] = []
    groups = [
        (sg.name or "sentences", list(sg.sentences or []))
        for sg in theory.sentence_groups
        if sg.group_type in (None, SentenceGroupType.AXIOM)
    ]
    groups.append(("ground_terms", list(theory.ground_terms)))
    for group_name, sentences in groups:
        for sentence in sentences:
            model_object = sentence.to_model_object() if isinstance(sentence, Extension) else sentence
            try:
                normalized = to_horn_rules(model_object, allow_goal_clauses=True)
            except (NotInProfileError, ValueError):
                skipped.append(sentence)
                continue
            described = [rule for rule in normalized if _rule_terms(rule) is not None]
            if not normalized or len(described) < len(normalized):
                skipped.append(sentence)
            for i, rule in enumerate(described):
                rules.append((f"{group_name}[{i}]" if len(described) > 1 else group_name, rule))
    return rules, skipped


def skipped_sentences(theory: Theory) -> List[Sentence]:
    """
    List the asserted sentences that reflection could not fully describe.

    Reflection covers what has a Horn form. Anything else contributes no facts, so a
    clean type check says nothing about it; this function makes that gap inspectable
    rather than silent.

        >>> from typedlogic import Theory
        >>> skipped_sentences(Theory(name="empty"))
        []

    :param theory: The theory to inspect
    :return: Sentences of which some part produced no rules
    """
    return _described_rules(theory)[1]


def theory_to_facts(theory: Theory) -> List[Fact]:
    """
    Reflect a theory into ground facts of the metatheory vocabulary.

    The result describes the theory's declarations and rule structure, and is intended to
    be loaded into a solver together with :mod:`typedlogic.theories.metatheory.axioms`.

        >>> from typedlogic import Theory
        >>> from typedlogic.datamodel import PredicateDefinition
        >>> theory = Theory(
        ...     name="people",
        ...     type_definitions={"PersonID": "str"},
        ...     predicate_definitions=[PredicateDefinition("Person", {"id": "PersonID"})],
        ... )
        >>> facts = theory_to_facts(theory)
        >>> TypeBase("PersonID", "str") in facts
        True
        >>> ArgType("Person", 0, "PersonID") in facts
        True

    :param theory: The theory to reflect
    :return: Ground facts describing the theory
    """
    facts: List[Fact] = []
    declared_types = set(BASE_TYPES)

    type_definitions: Dict[str, Any] = theory.type_definitions or {}
    for name, definition in type_definitions.items():
        declared_types.add(name)
        if isinstance(definition, list):
            for member in definition:
                if isinstance(member, str):
                    declared_types.add(member)
                    facts.append(TypeUnionMember(TypeName(name), TypeName(member)))
        elif isinstance(definition, str):
            declared_types.add(definition)
            facts.append(TypeBase(TypeName(name), TypeName(definition)))

    for pd in theory.predicate_definitions:
        predicate = PredicateName(pd.predicate)
        facts.append(PredicateDeclared(predicate))
        for parent in pd.parents or []:
            facts.append(PredicateParent(predicate, PredicateName(parent)))
        for position, (arg_name, arg_type) in enumerate(pd.arguments.items()):
            if not isinstance(arg_type, str):
                arg_type = pd.argument_base_type(arg_name)
            declared_types.add(arg_type)
            facts.append(ArgName(predicate, position, arg_name))
            facts.append(ArgType(predicate, position, TypeName(arg_type)))

    facts.extend(BaseType(TypeName(t)) for t in BASE_TYPES)
    facts.extend(TypeExists(TypeName(t)) for t in sorted(declared_types))

    predicate_map = theory.predicate_definition_map
    for rule_name, rule in _described_rules(theory)[0]:
        split = _rule_terms(rule)
        if split is None:
            continue
        rule_id = RuleID(rule_name)
        heads, positive, negative = split
        for term in heads:
            if not _is_builtin(term.predicate):
                facts.append(HeadPredicate(rule_id, PredicateName(term.predicate)))
        for term in positive:
            if not _is_builtin(term.predicate):
                facts.append(BodyPredicate(rule_id, PredicateName(term.predicate)))
        for term in negative:
            if not _is_builtin(term.predicate):
                facts.append(NegatedBodyPredicate(rule_id, PredicateName(term.predicate)))
        for term in heads + positive + negative:
            if _is_builtin(term.predicate):
                continue
            predicate = PredicateName(term.predicate)
            for position, value in _positional_values(term, predicate_map.get(term.predicate)):
                if isinstance(value, Variable):
                    facts.append(VarPosition(rule_id, VarName(value.name), predicate, position))
                elif isinstance(value, Term):
                    # A computed subterm (`d1 + d2`) has no single declared type; typing it
                    # would need an arithmetic signature the vocabulary does not carry.
                    continue
                else:
                    base_type = _base_type_of(value)
                    if base_type is not None:
                        facts.append(ConstantPosition(rule_id, TypeName(base_type), predicate, position))

    return _deduplicate(facts)


def _deduplicate(facts: Iterable[Fact]) -> List[Fact]:
    """
    Remove duplicate facts while keeping their order.

    :param facts: The reflected facts
    :return: The same facts, each appearing once
    """
    seen = set()
    unique = []
    for fact in facts:
        if fact in seen:
            continue
        seen.add(fact)
        unique.append(fact)
    return unique
