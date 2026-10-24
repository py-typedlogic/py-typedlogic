"""Fail-closed compilation and numerical semantics of probabilistic constructs."""

# Assertions express the expected semantics in this test module.
# ruff: noqa: S101

from dataclasses import dataclass
from typing import Any

import pytest
from problog import get_evaluatable
from problog.program import PrologString

from typedlogic import And, Fact, Forall, Implies, Or, PredicateDefinition, Term, Theory, Variable
from typedlogic.datamodel import Exists, Iff, NegationAsFailure, NotInProfileError
from typedlogic.extensions.probabilistic import AnnotatedDisjunction, Evidence, Probability, That
from typedlogic.integrations.solvers.problog.problog_compiler import ProbLogCompiler
from typedlogic.integrations.solvers.problog.problog_solver import ProbLogSolver


def compile_sentences(*sentences: Any, strict: bool = True) -> str:
    """Compile a small theory without automatically added queries."""
    theory = Theory()
    for sentence in sentences:
        theory.add(sentence)
    return ProbLogCompiler().compile(theory, strict=strict, include_queries=False)


def evaluate(program: str) -> dict[str, float]:
    """Evaluate the actual ProbLog program, rather than its rendering alone."""
    return {str(term): value for term, value in get_evaluatable().create_from(PrologString(program)).evaluate().items()}


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf"), -float("inf"), True, "0.5", None])
def test_invalid_probabilities_rejected(value: Any, strict: bool) -> None:
    """Typed construction and raw terms both reject invalid probability values."""
    with pytest.raises(ValueError, match="finite number"):
        Probability(value, That(Term("P")))
    raw = Term("Probability", value, Term("That", Term("P")))
    with pytest.raises(ValueError, match="finite number"):
        compile_sentences(raw, strict=strict)


@pytest.mark.parametrize("value", ["false", "true", 0, 1, None])
def test_evidence_requires_boolean(value: Any) -> None:
    """Text or integer values must not be coerced to truth values."""
    with pytest.raises(ValueError, match="must be bool"):
        Evidence(Term("P"), value)
    with pytest.raises(ValueError, match="must be bool"):
        compile_sentences(Term("Evidence", Term("P"), value))


@pytest.mark.parametrize(
    "atom", [Term("P", Variable("x")), Term("P", Term("Function", Variable("x"))), Term("P", None)]
)
def test_evidence_must_be_ground(atom: Term) -> None:
    """Nested function terms cannot conceal unbound observation variables."""
    with pytest.raises(ValueError, match="must be ground"):
        compile_sentences(Evidence(atom, True))


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize(
    "wrapped",
    [
        And(Term("P"), Term("Q")),
        Or(Term("P"), Term("Q")),
        Implies(Term("P"), And(Term("Q"), Term("R"))),
        Implies(Term("P"), Or(Term("Q"), Term("R"))),
        Implies(Or(Term("P"), Term("Q")), Term("R")),
        Implies(Term("P"), Or()),
        ~Term("P"),
    ],
)
def test_probability_cannot_be_distributed_over_transformed_rules(wrapped: Any, strict: bool) -> None:
    """One weighted connective must never silently become independent draws."""
    with pytest.raises(NotInProfileError):
        compile_sentences(Probability(0.4, That(wrapped)), strict=strict)


@pytest.mark.parametrize(
    "sentence",
    [
        Exists([Variable("x")], Term("P", Variable("x"))),
        Or(Term("P"), Term("Q")),
        And(Term("P"), Term("Q")),
        Iff(Term("P"), Term("Q")),
        Implies(Term("P"), Or(Term("Q"), Term("R"))),
        Implies(Term("P"), Term("add", 1, 2)),
        Implies(Term("P"), Term("Q", Variable("x"))),
        Implies(Term("P"), Term("Q", Term("F", Variable("x")))),
        Implies(Term("eq", Variable("x"), Variable("y")), Term("Q", Variable("x"))),
        Implies(~Term("P"), Term("Q")),
    ],
)
def test_strict_path_never_silently_drops_or_reinterprets_sentence(sentence: Any) -> None:
    """Unsupported input fails even when a valid preceding clause exists."""
    with pytest.raises(NotInProfileError):
        compile_sentences(Term("Valid"), sentence)


@pytest.mark.parametrize("argument", [None, Term("F", None), Variable("_")])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("conditional", [False, True])
def test_strict_heads_reject_anonymous_arguments(argument: Any, weighted: bool, conditional: bool) -> None:
    """None and anonymous variables cannot bypass strict head grounding checks."""
    sentence = Term("P", argument)
    if conditional:
        sentence = Implies(Term("Body", argument), sentence)
    if weighted:
        sentence = Probability(0.5, That(sentence))
    with pytest.raises(NotInProfileError, match="Anonymous arguments"):
        compile_sentences(sentence)


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("argument", [None, Term("F", None), Variable("_")])
def test_disjunction_heads_reject_anonymous_arguments(argument: Any, strict: bool) -> None:
    """A new categorical choice must never introduce an unbound anonymous head."""
    choice = AnnotatedDisjunction(((0.4, Term("A", argument)), (0.6, Term("B"))), body=Term("Body", argument))
    with pytest.raises(NotInProfileError, match="Anonymous arguments"):
        compile_sentences(choice, strict=strict)


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("heads", [(Term("A"), Term("a")), (Term("P", Term("F", "x")), Term("P", Term("f", "x")))])
def test_disjunction_rejects_rendered_head_collisions(heads: Any, strict: bool) -> None:
    """Distinct typed predicates must remain distinct after Prolog lowercasing."""
    with pytest.raises(ValueError, match="collide after rendering"):
        compile_sentences(AnnotatedDisjunction(((0.4, heads[0]), (0.6, heads[1]))), strict=strict)


def test_strict_option_is_opt_in() -> None:
    """Retain legacy deterministic conversion until callers opt into the subset."""
    sentence = Or(Term("P"), Term("Q"))
    assert compile_sentences(sentence, strict=False) == r"q :- \+ p."


def test_atomic_horn_probabilities_and_negative_evidence() -> None:
    """Conditional probabilities agree with manual Bayes and Boolean evidence."""
    disease, symptom = Term("Disease"), Term("Symptom")
    program = compile_sentences(
        Probability(0.2, That(disease)),
        Probability(0.8, That(Implies(disease, symptom))),
        Probability(0.1, That(Implies(NegationAsFailure(disease), symptom))),
        Evidence(symptom, False),
        Term("query", disease),
    )
    assert evaluate(program)["disease"] == pytest.approx(0.04 / 0.76)


def test_dataclass_atoms_and_forall_rules() -> None:
    """The strict subset accepts existing Fact-based atomic Horn expressions."""

    @dataclass(frozen=True)
    class Person(Fact):
        name: str

    @dataclass(frozen=True)
    class Symptom(Fact):
        name: str

    x = Variable("x")
    program = compile_sentences(
        Person("patient"),
        Probability(0.7, That(Forall([x], Implies(Person(x), Symptom(x))))),
        Evidence(Symptom("patient"), True),
        Term("query", Term("Symptom", "patient")),
    )
    assert evaluate(program)['symptom("patient")'] == 1.0


def test_annotated_disjunction_is_exclusive_and_conditionable() -> None:
    """Candidate priors form one categorical choice, not independent facts."""
    a, b, symptom = Term("A"), Term("B"), Term("Symptom")
    program = compile_sentences(
        AnnotatedDisjunction(((0.4, a), (0.6, b))),
        Probability(0.8, That(Implies(a, symptom))),
        Probability(0.2, That(Implies(b, symptom))),
        Implies(And(a, b), Term("Both")),
        Evidence(symptom, True),
        Term("query", a),
        Term("query", b),
        Term("query", Term("Both")),
    )
    result = evaluate(program)
    assert result == pytest.approx({"a": 0.32 / 0.44, "b": 0.12 / 0.44, "both": 0.0})


def test_conditional_disjunction_has_independent_groundings_and_null_choice() -> None:
    """A subunit probability sum leaves an explicit implicit-none outcome."""
    x = Variable("x")
    program = compile_sentences(
        Term("Person", "one"),
        Term("Person", "two"),
        AnnotatedDisjunction(((0.2, Term("A", x)), (0.3, Term("B", x))), body=Term("Person", x)),
        Implies(And(Term("A", "one"), Term("A", "two")), Term("BothPeople")),
        Implies(And(NegationAsFailure(Term("A", "one")), NegationAsFailure(Term("B", "one"))), Term("Neither")),
        Term("query", Term("BothPeople")),
        Term("query", Term("A", "one")),
        Term("query", Term("Neither")),
    )
    assert evaluate(program) == pytest.approx({'a("one")': 0.2, "bothpeople": 0.04, "neither": 0.5})


@pytest.mark.parametrize(
    "alternatives",
    [
        (),
        ((0.7, Term("A")), (0.5, Term("B"))),
        ((0.4, Term("A")), (0.4, Term("A"))),
        ((0.4, Or(Term("A"), Term("B"))),),
    ],
)
def test_invalid_disjunctions_rejected(alternatives: Any) -> None:
    """Bad totals, duplicate or non-atomic heads cannot silently change a choice."""
    with pytest.raises(ValueError):
        compile_sentences(AnnotatedDisjunction(alternatives))


def test_strict_solver_uses_same_compilation_policy() -> None:
    """Both execution and dump honor the public solver option."""
    solver = ProbLogSolver(strict_compilation=True)
    solver.add(Or(Term("P"), Term("Q")))
    with pytest.raises(NotInProfileError):
        solver.dump()
    with pytest.raises(NotInProfileError):
        solver.model()


def test_solver_returns_disjunction_probabilities() -> None:
    """Automatic queries omit AD metadata and return ordinary candidate atoms."""
    solver = ProbLogSolver(strict_compilation=True)
    for predicate in ("A", "B", "AnnotatedDisjunction"):
        solver.add_predicate_definition(PredicateDefinition(predicate, {}))
    solver.add(AnnotatedDisjunction(((0.4, Term("A")), (0.6, Term("B")))))
    probabilities = solver.model().term_probabilities
    assert probabilities == pytest.approx({Term("A"): 0.4, Term("B"): 0.6})
