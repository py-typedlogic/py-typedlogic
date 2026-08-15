"""Tests for the metatheory: reflecting a theory into facts and reasoning over them."""

import pytest

import tests.theorems.animals as animals
import tests.theorems.barbers as barbers
import tests.theorems.defined_types_example as defined_types_example
import tests.theorems.ehr_phenotyping as ehr_phenotyping
import tests.theorems.enums_example as enums_example
import tests.theorems.family_relationships as family_relationships
import tests.theorems.metatheory_house_rules as house_rules
import tests.theorems.mortals as mortals
import tests.theorems.numbers as numbers
import tests.theorems.optional_example as optional_example
import tests.theorems.paths as paths
import tests.theorems.paths_with_distance as paths_with_distance
import tests.theorems.signaling_pathways as signaling_pathways
import tests.theorems.simple_contradiction as simple_contradiction
import tests.theorems.types_example as types_example
import tests.theorems.unary_predicates as unary_predicates
from typedlogic import Theory
from typedlogic.datamodel import And, Forall, Implies, NegationAsFailure, Not, PredicateDefinition, Term, Variable
from typedlogic.parsers.pyparser import PythonParser
from typedlogic.theories.metatheory import check_theory, theory_to_facts
from typedlogic.theories.metatheory.vocabulary import (
    ArgName,
    ArgType,
    BodyPredicate,
    HeadPredicate,
    NegatedBodyPredicate,
    PredicateDeclared,
    TypeBase,
    TypeUnionMember,
    VarPosition,
)
from typedlogic.utils.detect_stratified_negation import Graph

X = Variable("x")
Y = Variable("y")


def _branded_theory() -> Theory:
    """Build a theory with two types that share a representation but must not mix."""
    return Theory(
        name="branded",
        type_definitions={"PersonID": "str", "OrgID": "str", "Age": "int"},
        predicate_definitions=[
            PredicateDefinition("Person", {"id": "PersonID"}),
            PredicateDefinition("Org", {"id": "OrgID"}),
            PredicateDefinition("HasAge", {"id": "PersonID", "age": "Age"}),
            PredicateDefinition("Flag", {"id": "PersonID"}),
        ],
    )


def _kinds(result) -> list:
    """List the diagnostic kinds in a check result."""
    return [d.kind for d in result.diagnostics]


# --- Reflection ----------------------------------------------------------------------


def test_reflection_records_predicate_signatures():
    """Declarations become facts, so rules can quantify over argument positions."""
    facts = theory_to_facts(_branded_theory())
    assert PredicateDeclared("Person") in facts
    assert ArgType("HasAge", 1, "Age") in facts
    assert ArgName("HasAge", 1, "age") in facts


def test_reflection_records_type_definitions():
    """Scalar definitions and union members are distinguished, as they subtype differently."""
    theory = Theory(
        name="types",
        type_definitions={"PersonID": "str", "Key": ["PersonID", "int"]},
        predicate_definitions=[PredicateDefinition("P", {"k": "Key"})],
    )
    facts = theory_to_facts(theory)
    assert TypeBase("PersonID", "str") in facts
    assert TypeUnionMember("Key", "PersonID") in facts
    assert TypeUnionMember("Key", "int") in facts


def test_reflection_records_variable_positions():
    """A variable's occurrences are what let a rule's types be compared across literals."""
    theory = _branded_theory()
    theory.add(Forall([X], Implies(Term("Person", X), Term("Flag", X))))
    facts = theory_to_facts(theory)
    assert VarPosition("Sentences", "x", "Person", 0) in facts
    assert VarPosition("Sentences", "x", "Flag", 0) in facts
    assert HeadPredicate("Sentences", "Flag") in facts
    assert BodyPredicate("Sentences", "Person") in facts


@pytest.mark.parametrize("negation", [Not, NegationAsFailure])
def test_reflection_records_both_negations(negation):
    """Classical negation and negation as failure both make a dependency negative."""
    theory = _branded_theory()
    theory.add(Forall([X], Implies(And(Term("Person", X), negation(Term("Org", X))), Term("Flag", X))))
    facts = theory_to_facts(theory)
    assert NegatedBodyPredicate("Sentences", "Org") in facts


# --- Type checking -------------------------------------------------------------------


def test_clean_theory_has_no_diagnostics():
    """A theory that declares everything it uses passes."""
    theory = _branded_theory()
    theory.add(Forall([X], Implies(Term("Person", X), Term("Flag", X))))
    assert check_theory(theory).ok


def test_variable_spanning_incompatible_types_is_a_clash():
    """PersonID and OrgID share a representation but neither is assignable to the other."""
    theory = _branded_theory()
    theory.add(Forall([X], Implies(And(Term("Person", X), Term("Org", X)), Term("Flag", X))))
    result = check_theory(theory)
    assert _kinds(result) == ["TypeClash"]
    assert "not compatible" in str(result)


def test_clash_is_reported_once_per_variable():
    """Incompatibility is symmetric, so the raw derivation holds in both directions."""
    theory = _branded_theory()
    theory.add(Forall([X], Implies(And(Term("Person", X), Term("Org", X)), Term("Flag", X))))
    assert len(check_theory(theory).diagnostics) == 1


def test_subtype_and_base_type_are_compatible():
    """A variable may span a branded position and a position declared with its base type."""
    theory = _branded_theory()
    theory.predicate_definitions.append(PredicateDefinition("Named", {"name": "str"}))
    theory.add(Forall([X], Implies(And(Term("Person", X), Term("Named", X)), Term("Flag", X))))
    assert check_theory(theory).ok


def test_literal_of_wrong_base_type_is_a_clash():
    """An int cannot fill a position declared with a string-based type."""
    theory = _branded_theory()
    theory.add(Term("Person", 42))
    assert _kinds(check_theory(theory)) == ["ConstantClash"]


def test_literal_of_right_base_type_is_accepted():
    """A string literal is admissible at a branded string position, as in Souffle."""
    theory = _branded_theory()
    theory.add(Term("Person", "alice"))
    assert check_theory(theory).ok


def test_undeclared_predicate_is_reported():
    """A rule over an undeclared predicate escapes every signature check."""
    theory = _branded_theory()
    theory.add(Forall([X], Implies(Term("Ghost", X), Term("Flag", X))))
    assert _kinds(check_theory(theory)) == ["UndeclaredPredicate"]


def test_opaque_types_do_not_produce_clashes():
    """A type that cannot be resolved to a base type constrains nothing.

    Reporting an incompatibility here would be reporting the checker's own ignorance:
    enums and unreduced annotations reach the theory as bare names with no definition.
    """
    theory = Theory(
        name="opaque",
        predicate_definitions=[
            PredicateDefinition("Tagged", {"id": "Mystery"}),
            PredicateDefinition("Named", {"id": "str"}),
        ],
    )
    theory.add(Forall([X], Implies(Term("Tagged", X), Term("Named", X))))
    assert check_theory(theory).ok


# --- Properties of the rule graph ----------------------------------------------------


@pytest.mark.parametrize("negation", [Not, NegationAsFailure])
def test_recursion_through_negation_is_reported(negation):
    """A predicate defined in terms of its own negation has no unique least model."""
    theory = _branded_theory()
    theory.add(Forall([X], Implies(And(Term("Person", X), negation(Term("Flag", X))), Term("Flag", X))))
    assert "UnstratifiedNegation" in _kinds(check_theory(theory))


def test_stratified_negation_is_not_reported():
    """Negating a predicate that does not depend back on the head is fine."""
    theory = _branded_theory()
    theory.add(Forall([X], Implies(And(Term("HasAge", X, Y), NegationAsFailure(Term("Person", X))), Term("Flag", X))))
    assert "UnstratifiedNegation" not in _kinds(check_theory(theory))


# --- Extensibility -------------------------------------------------------------------


def test_user_axioms_add_checks_without_changing_the_checker():
    """The point of the design: a project's own rule is enforced like any built-in one."""
    theory = Theory(
        name="unbranded",
        predicate_definitions=[PredicateDefinition("Person", {"name": "str"})],
    )
    assert check_theory(theory).ok

    result = check_theory(
        theory,
        extra_axioms=[house_rules],
        extra_diagnostics=[house_rules.UnbrandedArgument],
    )
    assert _kinds(result) == ["UnbrandedArgument"]


# --- The existing corpus -------------------------------------------------------------

CLEAN_THEORY_MODULES = [
    animals,
    defined_types_example,
    ehr_phenotyping,
    enums_example,
    family_relationships,
    mortals,
    numbers,
    optional_example,
    paths,
    paths_with_distance,
    signaling_pathways,
    simple_contradiction,
    types_example,
    unary_predicates,
]


@pytest.mark.parametrize("module", CLEAN_THEORY_MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_existing_theories_produce_no_diagnostics(module):
    """The checker must be quiet on theories known to be well formed.

    A checker that cries wolf on the existing corpus would be unusable, and most of these
    exercise the constructs most likely to produce false positives: enums, `Optional`,
    unions, arithmetic, and class hierarchies.
    """
    result = check_theory(PythonParser().transform(module))
    assert result.ok, str(result)


def test_barber_paradox_is_detected():
    """The one theory in the corpus that really does recurse through negation."""
    result = check_theory(PythonParser().transform(barbers))
    assert _kinds(result) == ["UnstratifiedNegation"]


@pytest.mark.parametrize(
    "module", CLEAN_THEORY_MODULES + [barbers], ids=lambda m: m.__name__.rsplit(".", 1)[-1]
)
def test_stratification_agrees_with_the_imperative_detector(module):
    """Cross-check the derived result against the hand-written Tarjan implementation."""
    theory = PythonParser().transform(module)
    facts = theory_to_facts(theory)
    heads: dict = {}
    for fact in facts:
        if isinstance(fact, HeadPredicate):
            heads.setdefault(fact.rule, []).append(fact.predicate)
    graph = Graph()
    for fact in facts:
        if isinstance(fact, BodyPredicate):
            for head in heads.get(fact.rule, []):
                graph.add_edge(head, fact.predicate, False)
        elif isinstance(fact, NegatedBodyPredicate):
            for head in heads.get(fact.rule, []):
                graph.add_edge(head, fact.predicate, True)
    graph.tarjan()
    stratified, _ = graph.is_stratified()

    derived = "UnstratifiedNegation" in _kinds(check_theory(theory))
    assert derived is not stratified
