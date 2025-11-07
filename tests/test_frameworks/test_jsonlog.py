import pytest
from typedlogic.integrations.solvers.snakelog import SnakeLogSolver
from typedlogic.integrations.solvers.souffle import SouffleSolver
from typedlogic.integrations.solvers.z3 import Z3Solver
from typedlogic.theories.jsonlog import jsonlog
from typedlogic.theories.jsonlog.jsonlog import (
    ArrayPointerHasMember,
    PointerIntValue,
    PointerIsArray,
    PointerIsLiteral,
    PointerIsObject,
    PointerStringValue,
    ObjectPointerHasProperty,
)
from typedlogic.theories.jsonlog.loader import generate_from_object


@pytest.mark.parametrize(
    "source,expected",
    [
        ({}, {PointerIsObject("/")}),
        ("x", {PointerIsLiteral("/"), PointerStringValue("/", "x")}),
        (1, {PointerIsLiteral("/"), PointerIntValue("/", 1)}),
        (
            {"k": 1},
            {PointerIsObject("/"), ObjectPointerHasProperty("/", "k", "/k/"), PointerIntValue("/k/", 1), PointerIsLiteral("/k/")},
        ),
        (
            ["x"],
            {PointerIsArray("/"), ArrayPointerHasMember("/", 0, "/[0]"), PointerStringValue("/[0]", "x"), PointerIsLiteral("/[0]")},
        ),
        (
            ["x", 1],
            {
                PointerIsArray("/"),
                ArrayPointerHasMember("/", 0, "/[0]"),
                PointerStringValue("/[0]", "x"),
                PointerIsLiteral("/[0]"),
                ArrayPointerHasMember("/", 1, "/[1]"),
                PointerIntValue("/[1]", 1),
                PointerIsLiteral("/[1]"),
            },
        ),
        (
            {"k": ["x", 1]},
            {
                PointerIsObject("/"),
                ObjectPointerHasProperty("/", "k", "/k/"),
                PointerIsArray("/k/"),
                ArrayPointerHasMember("/k/", 0, "/k/[0]"),
                PointerStringValue("/k/[0]", "x"),
                PointerIsLiteral("/k/[0]"),
                ArrayPointerHasMember("/k/", 1, "/k/[1]"),
                PointerIntValue("/k/[1]", 1),
                PointerIsLiteral("/k/[1]"),
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
