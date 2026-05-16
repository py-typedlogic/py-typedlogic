"""Tests for reified HiLog-like subclass propagation."""

from typing import cast

import pytest

from typedlogic import Forall, PredicateDefinition, Term, Theory, Variable
from typedlogic.compilers.fol_compiler import FOLCompiler
from typedlogic.compilers.prolog_compiler import PrologCompiler
from typedlogic.integrations.solvers.clingo.clingo_solver import ClingoSolver
from typedlogic.integrations.solvers.problog.problog_compiler import ProbLogCompiler
from typedlogic.integrations.solvers.souffle.souffle_compiler import SouffleCompiler
from typedlogic.integrations.solvers.z3 import Z3Solver
from typedlogic.integrations.solvers.z3.z3_compiler import Z3SExprCompiler
from typedlogic.transformations import PrologConfig, as_prolog, to_horn_rules


def meta_instantiation_theory() -> Theory:
    """Build a first-order encoding of subclass propagation over reified instances."""
    x = Variable("x", "str")
    y = Variable("y", "str")
    i = Variable("i", "str")
    theory = Theory(
        name="meta_instantiation",
        predicate_definitions=[
            PredicateDefinition("is_a", {"child": "str", "parent": "str"}),
            PredicateDefinition("inst", {"instance": "str", "class": "str"}),
        ],
    )
    theory.add(
        Forall(
            [x, y],
            Term("is_a", x, y) >> Forall([i], Term("inst", i, x) >> Term("inst", i, y)),
        )
    )
    return theory


def true_hilog_theory() -> Theory:
    """Build a true HiLog-style rule with variables in predicate position."""
    x = Variable("x", "str")
    y = Variable("y", "str")
    i = Variable("i", "str")
    theory = Theory(
        name="true_hilog",
        predicate_definitions=[
            PredicateDefinition("isa", {"child": "str", "parent": "str"}),
        ],
    )
    theory.add(
        Forall(
            [x, y],
            Term("isa", x, y) >> Forall([i], Term(cast(str, x), i) >> Term(cast(str, y), i)),
        )
    )
    return theory


def check(condition: bool, message: str) -> None:
    """Fail the test if the condition is false."""
    if not condition:
        pytest.fail(message)


@pytest.mark.parametrize("solver_class", [Z3Solver, ClingoSolver])
def test_meta_instantiation_rule_entails_parent_instantiation(solver_class):
    """The reified inst/2 encoding works in both first-order and Datalog-style backends."""
    solver = solver_class()
    solver.add(meta_instantiation_theory())
    solver.add(Term("is_a", "cat", "mammal"))
    solver.add(Term("inst", "felix", "cat"))

    check(solver.check().satisfiable is not False, "Expected the theory and facts to be satisfiable")
    check(
        solver.prove(Term("inst", "felix", "mammal")) is True,
        "Expected inst(felix, mammal) to be entailed",
    )


def test_meta_instantiation_rule_lowers_to_horn_rule():
    """Nested universal implication lowers to the Datalog rule used by Clingo-like targets."""
    [rule] = to_horn_rules(meta_instantiation_theory().sentences[0])

    check(
        as_prolog(rule, PrologConfig(double_quote_strings=True)) == "inst(I, Y) :- is_a(X, Y), inst(I, X).",
        f"Unexpected Horn rule: {rule}",
    )


def test_true_hilog_rule_can_be_represented_in_the_datamodel() -> None:
    """The datamodel can hold predicate variables even though target compilers reject them."""
    sentence = true_hilog_theory().sentences[0]

    check("?x(?i) -> ?y(?i)" in str(sentence), f"Expected predicate variables in: {sentence}")


def test_true_hilog_rule_is_not_directly_compilable_to_clingo() -> None:
    """Clingo compilation currently assumes first-order terms with fixed predicate names."""
    solver = ClingoSolver()
    solver.add(true_hilog_theory())

    with pytest.raises(AttributeError, match="lower"):
        solver.dump()


@pytest.mark.parametrize(
    "compiler,expected_fragments",
    [
        (
            FOLCompiler(),
            [
                "is_a(x, y)",
                "inst(i, x)",
                "inst(i, y)",
            ],
        ),
        (
            Z3SExprCompiler(),
            [
                "(forall ((x String) (y String))",
                "(forall ((i String))",
                "(=> (inst i x) (inst i y))",
            ],
        ),
        (
            PrologCompiler(),
            [
                "inst(I, Y) :- is_a(X, Y), inst(I, X).",
            ],
        ),
        (
            ProbLogCompiler(),
            [
                "inst(I, Y) :- is_a(X, Y), inst(I, X).",
                "query(inst(Instance, Class)).",
            ],
        ),
        (
            SouffleCompiler(),
            [
                ".decl inst(instance: symbol, class: symbol)",
                "inst(i, y) :- is_a(x, y), inst(i, x).",
            ],
        ),
    ],
)
def test_meta_instantiation_rule_compiles_across_targets(compiler, expected_fragments: list[str]) -> None:
    """Backends either preserve the quantifier structure or lower it to a Horn rule."""
    compiled = compiler.compile(meta_instantiation_theory())

    for fragment in expected_fragments:
        check(fragment in compiled, f"Expected {fragment!r} in:\n{compiled}")
