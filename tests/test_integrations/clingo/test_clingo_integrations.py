import timeit
from typing import Optional

import pytest

from typedlogic import Theory, NegationAsFailure
from typedlogic.datamodel import Variable, Term, Or, And, Implies, Exists, Not, CardinalityConstraint
from typedlogic.integrations.solvers.clingo.clingo_solver import ClingoSolver
from typedlogic.parsers.pyparser.python_parser import PythonParser
from typedlogic.transformations import implies_from_parents, to_horn_rules, simplify, as_prolog

from tests import tree_edges
from tests.theorems import paths

X = Variable("x")


@pytest.mark.parametrize(
    "depth,num_children,expected",
    [
        (1, 2, 4),
        (2, 2, 16),
        (5, 2, 320),
        (5, 3, 2004),
        (7, 3, 24603),
    ],
)
def test_paths(depth, num_children, expected):
    """
    Test simple transitivity over paths.

    This also tests inference of implication axioms for python parent classes.

    This test can be adapted for benchmarking.

    Example benchmarks:

    - method: litelog, depth: 8, num_children: 3, entailed: 19680 elapsed: 0.088
    - clingo, depth: 8, num_children: 3, entailed: 19680 elapsed: 11.785


    :param method_name:
    :param depth:
    :param num_children:
    :param expected:
    :return:
    """
    solver = ClingoSolver()
    parser = PythonParser()
    theory = parser.transform(paths)
    theory = implies_from_parents(theory)
    solver.add(theory)
    for source, target in tree_edges("a", depth, num_children):
        solver.add(paths.Link(source=source, target=target))
    for s in theory.sentences:
        print("ORIG", s)

    start_time = timeit.default_timer()
    assert solver.check().satisfiable is not False
    model = solver.model()
    elapsed = timeit.default_timer() - start_time
    num_facts = len(model.ground_terms)
    print(f"method: clingo, depth: {depth}, num_children: {num_children}, entailed: {num_facts} elapsed: {elapsed:.3f}")
    assert model.ground_terms
    # for t in model.ground_terms:
    #    print(f"FACT: {t}")
    if expected is not None:
        assert num_facts == expected


def test_constraints1():
    theory = Theory()
    x = Variable("X")
    theory.add(Term("A", x) >> Or())
    solver = ClingoSolver()
    solver.add(theory)
    assert solver.check().satisfiable
    solver.add(Term("A", "i1"))
    print(solver.dump())
    assert not solver.check().satisfiable

def test_constraints2():
    pytest.skip("TODO: existentials as constraints")
    theory = Theory()
    x = Variable("X")
    y = Variable("Y")
    theory.add(Implies(Term("B", x), Exists([y], Term("C", x))))
    solver = ClingoSolver()
    solver.add(theory)
    solver.add(Term("B", "i1"))
    assert not solver.check().satisfiable
    solver = ClingoSolver()
    solver.add(theory)
    solver.add(Term("B", "i1"))
    solver.add(Term("C", "i1"))
    print(solver.dump())
    assert solver.check().satisfiable


def test_constraints3():
    pytest.skip("Can't be expressed")
    theory = Theory()
    x = Variable("X")
    y = Variable("Y")
    theory.add(Implies(Term("B", x), Exists([y], Term("C", x, y))))
    solver = ClingoSolver()
    solver.add(theory)
    print("THEORY:")
    print(solver.dump())
    solver.add(Term("B", "i1"))
    assert not solver.check().satisfiable
    solver = ClingoSolver()
    solver.add(theory)
    solver.add(Term("B", "i1"))
    solver.add(Term("C", "i1", "z"))
    print("COMBINED:")
    print(solver.dump())
    assert solver.check().satisfiable

def test_constraints4():
    theory = Theory()
    x = Variable("X")
    y = Variable("_Y")
    theory.add(Implies(And(Term("B", x), Not(Term("C", x))), Term("foo")))
    solver = ClingoSolver()
    solver.add(theory)
    print("THEORY:")
    print(solver.dump())
    solver.add(Term("B", "i1"))
    assert solver.check().satisfiable
    for model in solver.models():
        print("MODEL:")
        for t in model.ground_terms:
            print(f"FACT: {t}")


def test_constraints5():
    theory = Theory()
    x = Variable("X")
    y = Variable("_Y")
    theory.add(Implies(Term("C", x, y), Term("has_C", x)))
    theory.add(Implies(And(Term("B", x), NegationAsFailure(Term("has_C", x))), Or()))
    solver = ClingoSolver()
    solver.add(theory)
    print("THEORY:")
    print(solver.dump())
    solver.add(Term("B", "i1"))
    assert not solver.check().satisfiable


@pytest.mark.parametrize("min_count", [0, None])
def test_cardinality_zero(min_count: int):
    theory = Theory()
    x = Variable("X")
    y = Variable("Y")
    thing = Term("Thing", x)
    hp = Term("HasPart", x, y)
    wing = Term("Wing", y)
    # note that min_count is implicitly zero, so it should not matter if
    # we explicitly set it or leave it as null
    rule = Implies(
            And(
            thing,
                CardinalityConstraint(hp, wing, min_count, 0)
            ),
            #Term("CardinalityConstraint", hp, wing, 0, 0),
            Term("Wingless", x)
        )
    print(rule)
    print(to_horn_rules(rule))
    print(simplify(rule))
    print(as_prolog(rule))
    theory.add(
        rule
    )
    solver = ClingoSolver()
    solver.add(theory)
    print("THEORY:")
    print(solver.dump())
    solver.add(Term("Thing", "fly1"))
    solver.add(Term("Thing", "fly2"))
    solver.add(Term("Wing", "fly2wing1"))
    solver.add(Term("HasPart", "fly2", "fly2wing1"))
    assert solver.check().satisfiable
    n = 0
    for model in solver.models():
        print("MODEL:")
        for t in model.ground_terms:
            print(f"  FACT: {t}")
            # TODO: remap casing
            if t == Term("wingless", "fly1"):
                n += 1
    assert n == 1, f"Expected 1 Wingless, got {n}"

def test_cardinality_existence_check():
    """
    Alternate way of doing an existence check

    fly1 has no asserted wings
    fly2 has one asserted wing

    if fly2 is asserted to have a wing, then consistent
    if fly1 is asserted not to have a wing, then inconsistent

    :return:
    """
    theory = Theory()
    x = Variable("X")
    y = Variable("Y")
    thing = Term("Thing", x)
    hp = Term("HasPart", x, y)
    ep = Term("ExpectedHasPart", x)
    wing = Term("Wing", y)
    rule = Implies(
            And(
                ep,
                CardinalityConstraint(hp, hp, None, 0)
            ),
            Or(),
        )
    print(rule)
    print(to_horn_rules(rule))
    print(simplify(rule))
    print(as_prolog(rule))
    theory.add(
        rule
    )
    solver = ClingoSolver()
    solver.add(theory)
    print("THEORY:")
    print(solver.dump())
    solver.add(Term("Thing", "fly1"))
    solver.add(Term("Thing", "fly2"))
    solver.add(Term("Wing", "fly2wing1"))
    solver.add(Term("HasPart", "fly2", "fly2wing1"))
    solver.add(Term("ExpectedHasPart", "fly2"))
    assert solver.check().satisfiable
    n = 0
    for model in solver.models():
        print("MODEL:")
        for t in model.ground_terms:
            print(f"  FACT: {t}")
    solver.add(Term("ExpectedHasPart", "fly1"))
    assert not solver.check().satisfiable

@pytest.mark.parametrize("actual_count", [0, 1, 2, 3, 4])
@pytest.mark.parametrize("max_count", [None, 0, 1, 2, 3])
@pytest.mark.parametrize("min_count", [None, 0, 1, 2, 3])
def test_cardinality_nary(min_count: int, max_count: int, actual_count: int):
    pytest.skip("TODO")
    theory = Theory()
    x = Variable("X")
    y = Variable("Y")
    thing = Term("Thing", x)
    hp = Term("HasPart", x, y)
    part = Term("Part", y)
    rule = Implies(
            thing,
            CardinalityConstraint(hp, part, min_count, max_count)
        )
    print(rule)
    print(to_horn_rules(rule))
    print(simplify(rule))
    print(as_prolog(rule))
    theory.add(
        rule
    )
    solver = ClingoSolver()
    solver.add(theory)
    print("THEORY:")
    print(solver.dump())
    solver.add(Term("Thing", "t1"))
    for part_num in range(0, actual_count):
        p = f"p{part_num}"
        solver.add(Term("Part", p))
        solver.add(Term("HasPart", "f1", p))
    print("ALL:")
    print(solver.dump())
    is_sat = True
    if min_count is not None and actual_count < min_count:
        is_sat = False
    if max_count is not None and actual_count > max_count:
        is_sat = False
    assert solver.check().satisfiable == is_sat