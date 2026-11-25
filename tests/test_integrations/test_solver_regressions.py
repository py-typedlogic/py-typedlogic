"""Regression tests for solver behaviour on unknown results, skipped sentences and argument order."""

import logging

import pytest
import z3
from typedlogic import And, Exists, Forall, Implies, Not, PredicateDefinition, SentenceGroup, Term, Theory, Variable
from typedlogic.datamodel import NotInProfileError, SentenceGroupType
from typedlogic.integrations.solvers.souffle.souffle_compiler import SouffleCompiler
from typedlogic.integrations.solvers.z3.z3_solver import Z3Solver
from typedlogic.registry import all_compiler_classes, all_parser_classes, all_solver_classes, get_compiler, get_solver
from typedlogic.solver import Model, Solution, Solver

x, y, a = Variable("x"), Variable("y"), Variable("a")
LINK = PredicateDefinition("Link", {"source": "str", "target": "str"})


def test_z3_keyword_terms_follow_declared_argument_order() -> None:
    solver = get_solver("z3")
    solver.add(LINK)
    solver.add(Term("Link", {"target": "b", "source": "a"}))
    assert solver.prove(Term("Link", "a", "b")) is True
    assert solver.prove(Term("Link", "b", "a")) is False


@pytest.mark.parametrize("solver_name", ["z3", "clingo"])
def test_keyword_ground_terms_in_a_theory_are_normalized(solver_name: str) -> None:
    theory = Theory(predicate_definitions=[LINK], ground_terms=[Term("Link", {"target": "b", "source": "a"})])
    solver = get_solver(solver_name)
    solver.add(theory)
    assert solver.prove(Term("Link", "a", "b")) is True


def _undecided_z3_solver() -> Z3Solver:
    solver = Z3Solver()
    solver.wrapped_solver.set("timeout", 1)
    i, j, k = z3.Ints("i j k")
    solver.wrapped_solver.add(i * i * i + j * j * j + k * k * k == 42, i > 1000, j > 1000)
    assert solver.wrapped_solver.check() == z3.unknown
    return solver


def test_z3_unknown_is_not_reported_as_unsatisfiable() -> None:
    assert _undecided_z3_solver().check() == Solution(satisfiable=None)


def test_z3_unknown_is_not_reported_as_unproved() -> None:
    solver = _undecided_z3_solver()
    solver.add(PredicateDefinition("P", {"n": "str"}))
    assert solver.prove(Term("P", "a")) is None


class _UndecidedSolver(Solver):
    """A solver that, like Souffle, cannot decide satisfiability."""

    def check(self) -> Solution:
        return Solution(satisfiable=None)

    def models(self):
        yield Model(ground_terms=list(self.base_theory.sentences))


def test_prove_goals_runs_when_satisfiability_is_unknown() -> None:
    solver = _UndecidedSolver()
    solver.add(Term("P", "a"))
    solver.add(SentenceGroup(name="g", group_type=SentenceGroupType.GOAL, sentences=[Term("P", "a")]))
    assert list(solver.prove_goals()) == [(Term("P", "a"), True)]


def _existential_theory() -> Theory:
    theory = Theory(
        predicate_definitions=[
            PredicateDefinition("P", {"n": "str"}),
            PredicateDefinition("Q", {"n": "str", "m": "str"}),
        ]
    )
    theory.add(Term("P", "a"))
    theory.add(Forall([x], Implies(Term("P", x), Exists([y], Term("Q", x, y)))))
    return theory


def test_clingo_warns_when_it_drops_a_sentence(caplog: pytest.LogCaptureFixture) -> None:
    solver = get_solver("clingo")
    solver.add(_existential_theory())
    with caplog.at_level(logging.WARNING):
        solver.dump()
    assert "Skipping sentence not supported by ClingoSolver" in caplog.text


def test_clingo_strict_raises_instead_of_dropping() -> None:
    solver = get_solver("clingo", strict=True)
    solver.add(_existential_theory())
    with pytest.raises(NotInProfileError):
        solver.dump()


def _constraint_theory() -> Theory:
    theory = Theory(predicate_definitions=[PredicateDefinition("P", {"n": "str"})])
    theory.add(Term("P", "a"))
    theory.add(Forall([x], Not(Term("P", x))))
    return theory


def test_souffle_compiler_warns_about_dropped_constraints(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        SouffleCompiler().compile(_constraint_theory())
    assert "Skipping sentence not expressible in Souffle" in caplog.text


def test_souffle_compiler_strict_raises_on_dropped_constraints() -> None:
    with pytest.raises(NotInProfileError):
        SouffleCompiler(strict=True).compile(_constraint_theory())


def test_souffle_compiler_types_and_booleans() -> None:
    theory = Theory(predicate_definitions=[PredicateDefinition("M", {"n": "str", "v": "float", "ok": "bool"})])
    theory.add(Term("M", "a", 1.5, False))
    assert SouffleCompiler().compile(theory) == '.decl M(n: symbol, v: float, ok: symbol)\nM("a", 1.5, "false").'


@pytest.mark.souffle
def test_souffle_solver_round_trips_floats_and_booleans() -> None:
    solver = get_solver("souffle")
    solver.add(PredicateDefinition("M", {"n": "str", "v": "float", "ok": "bool"}))
    solver.add(Term("M", "a", 1.5, False))
    assert [t.values for t in solver.model().ground_terms] == [("a", 1.5, False)]


@pytest.mark.souffle
def test_souffle_solver_raises_when_souffle_fails() -> None:
    solver = get_solver("souffle")
    solver.add(PredicateDefinition("P", {"n": "int"}))
    solver.add(Term("P", "not-a-number"))
    with pytest.raises(RuntimeError, match="Souffle failed"):
        solver.model()


def test_clingo_substitutes_theory_constants() -> None:
    theory = Theory(
        constants={"ADULT_AGE": 18},
        predicate_definitions=[
            PredicateDefinition("Age", {"n": "str", "a": "int"}),
            PredicateDefinition("Adult", {"n": "str"}),
        ],
    )
    theory.add(Term("Age", "bob", 30))
    theory.add(Term("Age", "kid", 3))
    theory.add(Forall([x, a], Implies(And(Term("Age", x, a), Term("ge", a, Variable("ADULT_AGE"))), Term("Adult", x))))
    solver = get_solver("clingo")
    solver.add(theory)
    assert solver.model().retrieve("Adult") == [Term("Adult", "bob")]
    assert "adult(X) :- age(X, A), A >= 18." in get_compiler("prolog").compile(theory)


def test_wellfounded_rejects_builtin_comparisons() -> None:
    solver = get_solver("wellfounded")
    solver.add(Term("Age", "bob", 30))
    solver.add(Forall([x, a], Implies(And(Term("Age", x, a), Term("ge", a, 18)), Term("Adult", x))))
    with pytest.raises(NotInProfileError, match="builtin"):
        solver.model()


def test_registry_passes_keyword_arguments() -> None:
    assert get_solver("z3", strict=True).strict is True


@pytest.mark.parametrize("classes", [all_solver_classes, all_parser_classes, all_compiler_classes])
def test_registry_lists_only_concrete_implementations(classes) -> None:
    assert "" not in classes()


def test_registry_does_not_import_packages_twice() -> None:
    import sys

    assert not [name for name in sys.modules if name.startswith("typedlogic") and name.endswith(".__init__")]


@pytest.mark.parametrize("handle,expected", [("fol", "P('a')"), ("tptp", "p('a')"), ("prover9", "P(s_a)")])
def test_compilers_emit_ground_terms(handle: str, expected: str) -> None:
    theory = Theory(predicate_definitions=[PredicateDefinition("P", {"n": "str"})], ground_terms=[Term("P", "a")])
    assert expected in get_compiler(handle).compile(theory)
