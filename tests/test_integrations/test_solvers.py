import pytest
from typedlogic import And, Exists, Forall, Iff, Or, PredicateDefinition, Term, Theory, Variable, Xor
from typedlogic.datamodel import ExactlyOne
from typedlogic.integrations.solvers.clingo.clingo_solver import ClingoSolver
from typedlogic.integrations.solvers.prover9 import Prover9Solver
from typedlogic.integrations.solvers.snakelog import SnakeLogSolver
from typedlogic.integrations.solvers.souffle import SouffleSolver
from typedlogic.integrations.solvers.z3 import Z3Solver
from typedlogic.profiles import (
    AllowsComparisonTerms,
    ClosedWorld,
    MultipleModelSemantics,
    OpenWorld,
    PropositionalLogic,
)

SOLVERS = [
    SouffleSolver,
    ClingoSolver,
    Z3Solver,
    SnakeLogSolver,
    Prover9Solver,
]

PROP_LOGIC_THEORY = Theory(
    name="Propositional Logic",
    predicate_definitions=[PredicateDefinition(p, {}) for p in ["A", "B", "C", "D", "E"]],
)

PRED_LOGIC_THEORY = Theory(
    name="Pred Logic",
    predicate_definitions=[PredicateDefinition(f"{p}1", {"x": "str"}) for p in ["A", "B", "C", "D", "E"]],
)

PRED_LOGIC_THEORY_INTS = Theory(
    name="Pred Logic with ints",
    predicate_definitions=[PredicateDefinition(f"{p}1", {"x": "int"}) for p in ["A", "B", "C", "D", "E"]],
)

X = Variable("X")
Y = Variable("Y")
Z = Variable("Z")
CONST1 = "const1"
CONST2 = "const2"
A0 = Term("A")
B0 = Term("B")
C0 = Term("C")
D0 = Term("D")
E0 = Term("E")
A1 = Term("A1", CONST1)
A1_2 = Term("A1", CONST2)
B1 = Term("B1", CONST1)
B1_2 = Term("B1", CONST2)
C1 = Term("C1", CONST1)
D1 = Term("D1", CONST1)
E1 = Term("E1", CONST1)
A1x = Term("A1", X)
B1x = Term("B1", X)
C1x = Term("C1", X)
D1x = Term("D1", X)
E1x = Term("E1", X)
A1y = Term("A1", Y)
B1y = Term("B1", Y)


@pytest.mark.parametrize("solver_class", SOLVERS)
@pytest.mark.parametrize(
    "theory,asserted_axioms,asserted_ground_terms,expected_num_models,expected_ground_terms,profile",
    [
        (PROP_LOGIC_THEORY, [], [], 1, [], None),
        (PROP_LOGIC_THEORY, [And()], [], 1, [], None),
        (PROP_LOGIC_THEORY, [~Or()], [], 1, [], None),
        (PROP_LOGIC_THEORY, [A0], [], 1, [A0], None),
        (PROP_LOGIC_THEORY, [], [A0], 1, [A0], None),
        (PROP_LOGIC_THEORY, [~A0], [A0], 0, None, OpenWorld),
        (PROP_LOGIC_THEORY, [~~A0], [], 1, [A0], OpenWorld),
        (PROP_LOGIC_THEORY, [~A0], [A0], 0, [], ClosedWorld),
        (PROP_LOGIC_THEORY, [A0, ~A0], [], 0, None, None),
        (PROP_LOGIC_THEORY, [And(A0, ~A0)], [], 0, None, None),
        (PROP_LOGIC_THEORY, [], [A0, ~A0], 0, None, None),
        (PROP_LOGIC_THEORY, [A0 >> B0], [A0], 1, [A0, B0], None),
        (PROP_LOGIC_THEORY, [A0 << B0], [B0], 1, [A0, B0], None),
        (PROP_LOGIC_THEORY, [Iff(A0, B0)], [A0], 1, [A0, B0], None),
        (PROP_LOGIC_THEORY, [And(A0, B0)], [], 1, [A0, B0], None),
        (PROP_LOGIC_THEORY, [Or(A0, B0)], [], 2, None, None),
        (PROP_LOGIC_THEORY, [And(A0)], [], 1, [A0], None),
        (PROP_LOGIC_THEORY, [And(And(A0))], [], 1, [A0], None),
        (PROP_LOGIC_THEORY, [Xor(A0, B0)], [], 2, None, None),
        (PROP_LOGIC_THEORY, [ExactlyOne(A0, B0)], [], 2, None, None),
        (PROP_LOGIC_THEORY, [Iff(A0 | B0, C0)], [A0], 1, [A0, C0], None),
        (PROP_LOGIC_THEORY, [Iff(A0 | B0, C0)], [C0], 2, None, None),
        (PROP_LOGIC_THEORY, [Iff(A0 | B0, C0), Iff(C0 & D0, E0)], [A0, D0], 1, [A0, C0, D0, E0], None),
        (PROP_LOGIC_THEORY, [Xor(A0, B0)], [A0], 1, [A0], MultipleModelSemantics),  # stratified negation
        (PROP_LOGIC_THEORY, [Xor(A0, B0)], [A0, B0], 0, None, None),
        (PROP_LOGIC_THEORY, [Xor(A0, B0)], [~A0], 1, [B0], OpenWorld),
        (PROP_LOGIC_THEORY, [(A0 & B0) >> C0], [A0, B0], 1, [A0, B0, C0], None),
        (PROP_LOGIC_THEORY, [(A0 | B0) >> C0], [A0], 1, [A0, C0], None),
        (PROP_LOGIC_THEORY, [(A0 & ~B0) >> C0], [A0], 1, [A0, C0], ClosedWorld),
        (PROP_LOGIC_THEORY, [(A0 & ~B0) >> C0], [A0], 1, [A0], OpenWorld),
        (PROP_LOGIC_THEORY, [(A0 & ~B0) >> C0], [A0, B0], 1, [A0, B0], ClosedWorld),
        (PROP_LOGIC_THEORY, [A0 >> (B0 & C0)], [A0], 1, [A0, B0, C0], None),
        (PROP_LOGIC_THEORY, [A0 >> (B0 | C0)], [A0], 2, None, None),  # ASP test
        (PROP_LOGIC_THEORY, [A0 >> (B0 | C0)], [A0, ~B0], 1, [A0, C0], OpenWorld),
        (PROP_LOGIC_THEORY, [A0 >> (B0 | C0)], [~C0, ~B0], 1, [~A0], OpenWorld),
        (PROP_LOGIC_THEORY, [A0 << (B0 | C0)], [B0], 1, [A0, B0], None),
        (PRED_LOGIC_THEORY, [A1], [], 1, [A1], None),
        (PRED_LOGIC_THEORY, [A1], [], 1, [Exists([X], A1x)], None),
        (PRED_LOGIC_THEORY, [~Exists([X], A1x)], [], 1, [~Exists([X], A1x)], OpenWorld),
        (PRED_LOGIC_THEORY, [~Exists([X], A1x)], [A1], 0, None, OpenWorld),
        (
            PRED_LOGIC_THEORY,
            [(A1 & Exists([X], B1x)) >> C1],
            [A1, B1],
            1,
            [A1, B1, C1],
            AllowsComparisonTerms,
        ),  # TODO: better way to exclude snakelog
        (
            PRED_LOGIC_THEORY,
            [Forall([X], Iff(A1x | B1x, C1x)), Forall([X], Iff(C1x & D1x, E1x))],
            [A1, D1],
            1,
            [A1, C1, D1, E1],
            None,
        ),
        (
            PRED_LOGIC_THEORY,
            [Forall([X], Iff(A1x | ~B1x, C1x)), Forall([X], Iff(C1x & D1x, E1x))],
            [A1, D1, ~B1],
            1,
            [A1, C1, D1, E1],
            OpenWorld,
        ),
        # (PRED_LOGIC_THEORY, [Forall([X], Iff(A1x | B1x, C1x)),
        #                     Forall([X], Iff(C1x & D1x, E1x))],
        #                    [C1, A1|B1], 2,
        #                    None, OpenWorld),
        (
            PRED_LOGIC_THEORY,
            [Forall([X], Iff(A1x | ~B1x, C1x)), Forall([X], Iff(C1x & D1x, E1x))],
            [A1, D1],
            1,
            [A1, C1, D1, E1],
            ClosedWorld,
        ),
        (PRED_LOGIC_THEORY, [Forall([X], A1x >> B1x)], [A1], 1, [A1, B1], None),
        (PRED_LOGIC_THEORY, [Forall([X], A1x >> B1x)], [B1], 1, [B1], None),
        (PRED_LOGIC_THEORY, [Forall([X], A1x << B1x)], [B1], 1, [A1, B1], None),
        (PRED_LOGIC_THEORY, [Forall([X], Iff(A1x, B1x))], [A1], 1, [A1, B1], None),
        # (PRED_LOGIC_THEORY, [Forall([X], (A1x & Forall([Y], B2xy)) >> C2xy(X,Y), [
        (PRED_LOGIC_THEORY, [Forall([X], ~(A1x & B1x))], [A1, B1], 0, None, OpenWorld),
        (
            PRED_LOGIC_THEORY,
            [Forall([X], (A1x & Term("eq", X, CONST1)) >> B1x)],
            [A1],
            1,
            [A1, B1],
            AllowsComparisonTerms,
        ),
        (
            PRED_LOGIC_THEORY,
            [Forall([X], (A1x & Term("eq", X, CONST1)) >> B1x)],
            [A1_2],
            1,
            [A1_2],
            AllowsComparisonTerms,
        ),
        (
            PRED_LOGIC_THEORY,
            [Forall([X], (A1x & Term("ne", X, CONST1)) >> B1x)],
            [A1, A1_2],
            1,
            [A1, A1_2, B1_2],
            AllowsComparisonTerms,
        ),
        (PRED_LOGIC_THEORY, [Forall([X], (A1x & Term("ne", X, CONST1)) >> B1x)], [A1], 1, [A1], AllowsComparisonTerms),
        # TODO: ints with Z3
        # (PRED_LOGIC_THEORY_INTS,
        # [Forall([X], (A1x & Term("gt", X, 1)) >> B1x)],
        # [Term("A1", 2)], 1, [Term("A1", 2), Term("B1", 2)], AllowsComparisonTerms),
        # (PRED_LOGIC_THEORY, [Forall([X, Y], ~(Term("A", X) & Term("B", Y)))], [A1, B1], 0, None, OpenWorld),
    ],
)
def test_solvers(
    solver_class, theory, asserted_axioms, asserted_ground_terms, expected_num_models, expected_ground_terms, profile
):
    solver = solver_class()
    if profile == ClosedWorld:
        solver.assume_closed_world = True
    if theory == PROP_LOGIC_THEORY and solver.profile.not_impl(PropositionalLogic):
        pytest.skip("Propositional Logic is not supported by this solver")
    if profile and not solver.profile.impl(profile):
        # pytest.skip("Profile not supported by this solver")
        return
    solver.add(theory)
    for axiom in asserted_axioms:
        solver.add(axiom)
    for fact in asserted_ground_terms:
        solver.add(fact)
    info = f"TH: {asserted_axioms} + DB: {asserted_ground_terms} from {solver_class} {theory}"
    print(info)
    print("PROGRAM: ", solver.dump())
    result = solver.check()
    if expected_num_models:
        assert result.satisfiable is not False
    else:
        assert result.satisfiable is not True, "Expected unsatisfiable"
    if expected_num_models:
        all_models = list(solver.models())
        if expected_num_models > 1 and solver.profile.impl(MultipleModelSemantics):
            assert (
                len(all_models) == expected_num_models
            ), f"Expected {expected_num_models} models, got {len(all_models)}\n{info}"
        model = solver.model()
        assert model
        for f in model.ground_terms:
            print("FACT", f, type(f))
        if (
            solver_class not in (Z3Solver, Prover9Solver)
            and expected_ground_terms is not None
            and all(isinstance(f, Term) for f in expected_ground_terms)
        ):
            assert set(model.ground_terms) == set(
                expected_ground_terms
            ), f"Mismatched axioms: {asserted_axioms}\n{info}"
        for f in expected_ground_terms or []:
            assert solver.prove(f), (
                f"could not prove {f} using axioms: {asserted_axioms} + \n"
                f"TH: {theory.sentences} + DB: {asserted_ground_terms} from {solver_class} {theory}"
            )


@pytest.mark.parametrize("solver_class", [SouffleSolver, ClingoSolver])
def test_paths_with_distance(solver_class):
    solver = solver_class()
    import tests.theorems.paths_with_distance as pwd

    solver.load(pwd)
    solver.add(pwd.Link(source="a", target="b"))
    solver.add(pwd.Link(source="b", target="c"))
    solver.add(pwd.Link(source="c", target="d"))
    solver.add(pwd.Link(source="d", target="e"))
    model = solver.model()
    print(solver.dump())
    for t in model.ground_terms:
        print(t)
    assert Term("Path", "a", "e", 4) in model.ground_terms


@pytest.mark.parametrize("solver_class", [Z3Solver, Prover9Solver, ClingoSolver])
def test_simple_contradiction(solver_class):
    solver = solver_class()
    import tests.theorems.simple_contradiction as sc

    solver.load(sc)
    assert solver.check().satisfiable is False
