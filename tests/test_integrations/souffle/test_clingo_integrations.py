import timeit

import pytest
from typedlogic.datamodel import Variable
from typedlogic.integrations.solvers.clingo.clingo_solver import ClingoSolver
from typedlogic.parsers.pyparser.python_parser import PythonParser
from typedlogic.transformations import implies_from_parents

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
