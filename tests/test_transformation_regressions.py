"""Regression tests for rendering and normal-form transformations."""

from dataclasses import replace

import pytest
from typedlogic import And, Exists, Forall, Iff, Implies, Not, Or, PredicateDefinition, Sentence, Term, Theory, Variable
from typedlogic.datamodel import CardinalityConstraint, ExactlyOne, Implied, NegationAsFailure, Xor
from typedlogic.transformations import (
    as_fol,
    as_prolog,
    as_tptp,
    ensure_terms_positional,
    force_stratification,
    implies_from_parents,
    replace_constants,
    skolemize,
)

P, Q, R = Term("P"), Term("Q"), Term("R")
x, y = Variable("x"), Variable("y")


def test_each_existential_gets_a_fresh_skolem_symbol() -> None:
    sentence = And(Exists([y], Term("P", y)), Exists([y], Term("Q", y)), Exists([y], Term("R", y)))
    assert skolemize(sentence) == And(Term("P", Term("sk__1")), Term("Q", Term("sk__2")), Term("R", Term("sk__3")))


def test_skolem_substitution_does_not_leak_out_of_scope() -> None:
    sentence = And(Exists([y], Term("P", y)), Forall([y], Term("Q", y)))
    assert skolemize(sentence) == And(Term("P", Term("sk__1")), Forall([y], Term("Q", y)))


@pytest.mark.parametrize(
    "sentence,expected",
    [
        (Not(And(P, Q)), "¬(P ∧ Q)"),
        (Implies(Implies(P, Q), R), "(P → Q) → R"),
        (Implies(And(P, NegationAsFailure(Q)), R), "P ∧ not Q → R"),
        (Xor(P, Q), "(P ⊕ Q)"),
        (Implies(And(P, Q), R), "P ∧ Q → R"),
        (And(Iff(P, Q), R), "(P ↔ Q) ∧ R"),
        (Implies(P, And()), "P → ⊤"),
        (Implies(P, Or()), "P → ⊥"),
    ],
)
def test_as_fol_is_unambiguous(sentence, expected: str) -> None:
    assert as_fol(sentence) == expected


def test_as_fol_rejects_unknown_nodes() -> None:
    with pytest.raises(ValueError, match="Unsupported sentence type"):
        as_fol("not a sentence")


@pytest.mark.parametrize(
    "sentence,expected",
    [
        (Implies(P, Q), "(p => q)"),
        (Implied(P, Q), "(q => p)"),
        (Xor(P, Q), "((p | q) & ~(p & q))"),
        (ExactlyOne(P, Q), "((p | q) & ~(p & q))"),
        (Implies(P, Or()), "(p => $false)"),
    ],
)
def test_as_tptp_forms(sentence, expected: str) -> None:
    assert as_tptp(sentence) == expected


def test_as_prolog_renders_booleans_as_atoms_not_variables() -> None:
    assert as_prolog(Term("P", True, False)) == "p(true, false)"


def test_cardinality_constraints_compare_by_content() -> None:
    cc1 = CardinalityConstraint(Term("a", x), Term("b", x), 1, 1)
    cc2 = CardinalityConstraint(Term("c", y), Term("d", y), 2, 3)
    assert cc1 != cc2
    assert cc1 == CardinalityConstraint(Term("a", x), Term("b", x), 1, 1)


def test_replace_constants_preserves_cardinality_constraints() -> None:
    cc = CardinalityConstraint(Term("a", x, Variable("K")), Term("b", x), 1, 2)
    replaced = replace_constants(cc, {"K": 5})
    assert isinstance(replaced, CardinalityConstraint)
    assert replaced.template == Term("a", x, 5)
    assert (replaced.minimum_number, replaced.maximum_number) == (1, 2)


@pytest.mark.parametrize("negation", [Not, NegationAsFailure])
def test_force_stratification_breaks_negative_cycles(negation) -> None:
    rules: list[Sentence] = [Implies(negation(Q), P), Implies(negation(P), Q)]
    assert len(force_stratification(rules)) == 1


def _hierarchy_theory() -> Theory:
    return Theory(
        name="t",
        constants={"C": 1},
        type_definitions={"T": "str"},
        predicate_definitions=[
            PredicateDefinition("A", {"n": "str"}, parents=["B"]),
            PredicateDefinition("B", {"n": "str"}),
        ],
        ground_terms=[Term("A", "a")],
    )


def test_implies_from_parents_keeps_the_rest_of_the_theory() -> None:
    theory = _hierarchy_theory()
    result = implies_from_parents(theory)
    assert [str(s) for s in result.sentences] == ["∀n: str : (A(?n) -> B(?n))"]
    assert replace(result, sentence_groups=[]) == replace(theory, sentence_groups=[])


def test_implies_from_parents_without_predicate_definitions() -> None:
    assert implies_from_parents(Theory()).sentences == []


def test_ensure_terms_positional_reorders_rules_and_ground_terms() -> None:
    theory = Theory(
        predicate_definitions=[PredicateDefinition("Link", {"source": "str", "target": "str"})],
        ground_terms=[Term("Link", {"target": "b", "source": "a"})],
    )
    theory.add(Term("Link", {"target": y, "source": x}))
    # keys the definition does not declare are left untouched rather than blanked
    theory.add(Term("Link", {"src": "p", "dst": "q"}))
    ensure_terms_positional(theory)
    assert theory.ground_terms == [Term("Link", "a", "b")]
    assert theory.sentences == [Term("Link", x, y), Term("Link", "p", "q")]


def test_theory_merge() -> None:
    t1 = _hierarchy_theory()
    t2 = Theory(
        name="other",
        constants={"D": 2},
        predicate_definitions=[PredicateDefinition("B", {"n": "str"}), PredicateDefinition("Z", {"n": "str"})],
        ground_terms=[Term("Z", "z")],
    )
    t2.add(Implies(Term("A", x), Term("Z", x)))
    t1.merge(t2)
    assert t1.name == "t"
    assert t1.constants == {"C": 1, "D": 2}
    assert [pd.predicate for pd in t1.predicate_definitions] == ["A", "B", "Z"]
    assert t1.sentences == [Implies(Term("A", x), Term("Z", x))]
    assert t1.ground_terms == [Term("A", "a"), Term("Z", "z")]
