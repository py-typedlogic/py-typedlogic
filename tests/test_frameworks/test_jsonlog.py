import pytest
from typedlogic.integrations.solvers.snakelog import SnakeLogSolver
from typedlogic.integrations.solvers.souffle import SouffleSolver
from typedlogic.integrations.solvers.z3 import Z3Solver
from typedlogic.theories.jsonlog import jsonlog
from typedlogic.theories.jsonlog.jsonlog import (
    ArrayPointerHasMember,
    NodeIntValue,
    NodeIsList,
    NodeIsLiteral,
    NodeIsObject,
    NodeStringValue,
    ObjectPointerHasProperty,
)
from typedlogic.theories.jsonlog.loader import generate_from_object


@pytest.mark.parametrize(
    "source,expected",
    [
        ({}, {NodeIsObject("/")}),
        ("x", {NodeIsLiteral("/"), NodeStringValue("/", "x")}),
        (1, {NodeIsLiteral("/"), NodeIntValue("/", 1)}),
        (
            {"k": 1},
            {NodeIsObject("/"), ObjectPointerHasProperty("/", "k", "/k/"), NodeIntValue("/k/", 1), NodeIsLiteral("/k/")},
        ),
        (
            ["x"],
            {NodeIsList("/"), ArrayPointerHasMember("/", 0, "/[0]"), NodeStringValue("/[0]", "x"), NodeIsLiteral("/[0]")},
        ),
        (
            ["x", 1],
            {
                NodeIsList("/"),
                ArrayPointerHasMember("/", 0, "/[0]"),
                NodeStringValue("/[0]", "x"),
                NodeIsLiteral("/[0]"),
                ArrayPointerHasMember("/", 1, "/[1]"),
                NodeIntValue("/[1]", 1),
                NodeIsLiteral("/[1]"),
            },
        ),
        (
            {"k": ["x", 1]},
            {
                NodeIsObject("/"),
                ObjectPointerHasProperty("/", "k", "/k/"),
                NodeIsList("/k/"),
                ArrayPointerHasMember("/k/", 0, "/k/[0]"),
                NodeStringValue("/k/[0]", "x"),
                NodeIsLiteral("/k/[0]"),
                ArrayPointerHasMember("/k/", 1, "/k/[1]"),
                NodeIntValue("/k/[1]", 1),
                NodeIsLiteral("/k/[1]"),
            },
        ),
    ],
)
def test_jsonlog_loader(source, expected):
    facts = set(generate_from_object(source))
    assert facts == expected


@pytest.mark.parametrize("source,valid", [({"k": ["x", 1]}, True)])
@pytest.mark.parametrize("solver_class", [Z3Solver, SouffleSolver, SnakeLogSolver])
def test_jsonlog_check(solver_class, source, valid):
    solver = solver_class()
    solver.load(jsonlog)
    assert solver.check().satisfiable is not False
    solver.add(generate_from_object(source))
    assert solver.check().satisfiable is not False
    model = solver.model()
    assert model
    if not isinstance(solver, Z3Solver):
        print(solver)
        print(solver.dump())
        facts = model.ground_terms
        for f in facts:
            print(f)
