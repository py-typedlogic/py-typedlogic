"""Tests for the base Solver and Model classes."""

from typing import Iterator

import pytest

from typedlogic import And, Implies, Not, Or, Variable
from typedlogic.datamodel import Exists, SentenceGroup, Term
from typedlogic.solver import Model, Solution, Solver

X = Variable("x")
P_X = Term("P", X)
Q_X = Term("Q", X)


class DummySolver(Solver):
    """Minimal concrete solver: its model is just the ground terms added so far."""

    def check(self) -> Solution:
        return Solution(satisfiable=True)

    def models(self) -> Iterator[Model]:
        yield Model(ground_terms=list(self.base_theory.ground_terms))


@pytest.mark.parametrize(
    "sentence",
    [
        And(P_X, Q_X),
        Or(P_X, Q_X),
        Not(P_X),
        Implies(P_X, Q_X),
    ],
)
def test_boolean_sentences_are_hashable(sentence):
    """Equal boolean sentences must be usable in sets/dicts with eq-consistent hashes."""
    assert hash(sentence) == hash(type(sentence)(*sentence.operands))
    assert len({sentence, type(sentence)(*sentence.operands)}) == 1


def test_distinct_boolean_sentences_hash_into_distinct_set_entries():
    assert len({And(P_X, Q_X), And(Q_X, P_X), Or(P_X, Q_X)}) == 3


def test_add_sentence_deduplicates():
    solver = DummySolver()
    s = Implies(P_X, Q_X)
    solver.add(s)
    solver.add(s)
    assert solver.base_theory.sentences == [s]
    # an equal-but-distinct instance is also deduplicated
    solver.add(Implies(P_X, Q_X))
    assert solver.base_theory.sentences == [s]
    # a different sentence is added
    s2 = Implies(Q_X, P_X)
    solver.add(s2)
    assert solver.base_theory.sentences == [s, s2]


def test_add_sentence_group_then_sentence_deduplicates():
    solver = DummySolver()
    s = Implies(P_X, Q_X)
    solver.add(SentenceGroup(name="g", sentences=[s]))
    assert solver.base_theory.sentences == [s]
    solver.add(s)
    assert solver.base_theory.sentences == [s]


def test_add_many_sentences():
    solver = DummySolver()
    sentences = [Term("Edge", f"n{i}", f"n{i + 1}") for i in range(500)]
    for s in sentences:
        solver.add_sentence(s)
    for s in sentences:
        solver.add_sentence(s)
    assert solver.base_theory.sentences == sentences


class P:
    """Stand-in predicate class for retrieve-by-type."""


@pytest.fixture
def model() -> Model:
    return Model(
        ground_terms=[
            Term("P", "a", "b"),
            Term("P", "c", "d"),
            Term("Q", "e"),
        ]
    )


def test_retrieve_by_predicate(model):
    assert model.retrieve("P") == [Term("P", "a", "b"), Term("P", "c", "d")]
    assert model.retrieve("Q") == [Term("Q", "e")]
    assert model.retrieve("R") == []


def test_retrieve_by_type(model):
    assert model.retrieve(P) == [Term("P", "a", "b"), Term("P", "c", "d")]


def test_retrieve_with_args(model):
    assert model.retrieve("P", "a") == [Term("P", "a", "b")]
    assert model.retrieve("P", None, "d") == [Term("P", "c", "d")]
    assert model.retrieve("P", "a", "d") == []


def test_retrieve_sees_terms_added_after_first_retrieve(model):
    assert len(model.retrieve("P")) == 2
    model.ground_terms.append(Term("P", "x", "y"))
    assert len(model.retrieve("P")) == 3
    assert len(model.retrieve("Q")) == 1


def test_prove_ground_term():
    solver = DummySolver()
    solver.base_theory.ground_terms.extend([Term("P", "a", "b"), Term("Q", "e")])
    assert solver.prove(Term("P", "a", "b")) is True
    assert solver.prove(Term("P", "a", "zzz")) is False
    assert solver.prove(Term("R", "a")) is False


def test_prove_term_with_variables():
    solver = DummySolver()
    solver.base_theory.ground_terms.append(Term("P", "a", "b"))
    assert solver.prove(Term("P", X, "b")) is True
    assert solver.prove(Term("P", X, "zzz")) is False
    assert solver.prove(Exists([X], Term("P", X, "b"))) is True


def test_add_sentence_with_unhashable_values_deduplicates():
    """Sentences embedding unhashable values (e.g. raw fact objects) must still dedup."""
    solver = DummySolver()
    s = Term("P", [1, 2])
    solver.add(s)
    solver.add(s)
    assert solver.base_theory.sentences == [s]
    solver.add(Term("P", [1, 2]))
    assert solver.base_theory.sentences == [s]
