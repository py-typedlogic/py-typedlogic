import timeit

import pytest
from typedlogic import Forall
from typedlogic.datamodel import NotInProfileError, PredicateDefinition, Term
from typedlogic.integrations.solvers.snakelog import SnakeLogSolver
from typedlogic.parsers.pyparser.python_parser import PythonParser
from typedlogic.transformations import implies_from_parents

import tests.theorems.mortals as mortals
from tests import tree_edges
from tests.theorems import animals, paths


@pytest.mark.parametrize("method_name", ["litelog", "souffle"])
def test_solver(method_name):
    solver = SnakeLogSolver(method_name=method_name)
    parser = PythonParser()
    theory = parser.transform(mortals)

    solver.add(theory)
    assert solver.check().satisfiable is not False
    f1 = mortals.AncestorOf(ancestor="p1", descendant="p1a")
    f2 = mortals.AncestorOf(ancestor="p1a", descendant="p1aa")
    solver.add_fact(f1)
    solver.add_fact(f2)
    solver.add_fact(mortals.Person(name="Aristotle"))

    models = list(solver.models())
    assert models
    print("MODELS:", models)
    # Standard prolog-like engines only return one model
    assert len(models) == 1
    model = models[0]
    expected_fact = Term("AncestorOf", {"ancestor": "p1", "descendant": "p1aa"})
    for f in model.ground_terms:
        print(f" FACT={f}")
    assert expected_fact in model.ground_terms
    assert len(model.ground_terms) == 5
    assert solver.prove(Term("AncestorOf", "p1", "p1aa"))


@pytest.mark.parametrize("method_name", ["litelog", "souffle"])
def test_strict(method_name):
    pytest.skip("TODO: revisit after CNF translations")
    solver = SnakeLogSolver(method_name=method_name, strict=True)
    parser = PythonParser()
    theory = parser.transform(mortals)
    for sg in theory.sentence_groups:
        for s in sg.sentences:
            print(s)
            if isinstance(s, Forall):
                try:
                    print(solver.to_clause(s))
                except NotInProfileError as e:
                    print(e)
    with pytest.raises(NotInProfileError):
        solver.add(theory)


@pytest.mark.parametrize("method_name", ["litelog", "souffle"])
def test_solver_simple(method_name):
    solver = SnakeLogSolver(method_name=method_name)
    solver.add_predicate_definition(
        PredicateDefinition(predicate="AncestorOf", arguments={"ancestor": str, "descendant": str})
    )
    f1 = mortals.AncestorOf(ancestor="p1", descendant="p1a")
    solver.add_fact(f1)
    model = solver.model()
    for f in model.ground_terms:
        print(f" FACT={f}")
    assert model.ground_terms


@pytest.mark.parametrize("method_name", ["litelog", "souffle"])
def test_animals(method_name):
    solver = SnakeLogSolver(method_name=method_name)
    parser = PythonParser()
    theory = parser.transform(animals)
    for s in theory.sentence_groups:
        print(s)
    solver.add(theory)
    assert solver.check().satisfiable is not False
    model = solver.model()
    assert model.ground_terms
    for f in model.ground_terms:
        print(f" FACT={f}")


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
@pytest.mark.parametrize("method_name", ["litelog", "souffle"])
def test_paths(method_name, depth, num_children, expected):
    """
    Test simple transitivity over paths.

    This also tests inference of implication axioms for python parent classes.

    This test can be adapted for benchmarking.

    Example benchmarks:

    - method: method: litelog, depth: 7, num_children: 3, entailed: 24603 elapsed: 0.126
    - method: souffle, depth: 7, num_children: 3, entailed: 24603 elapsed: 1.426


    :param method_name:
    :param depth:
    :param num_children:
    :param expected:
    :return:
    """
    solver = SnakeLogSolver(method_name=method_name)
    parser = PythonParser()
    theory = parser.transform(paths)
    theory = implies_from_parents(theory)
    solver.add(theory)
    for source, target in tree_edges("a", depth, num_children):
        solver.add(paths.Link(source=source, target=target))

    start_time = timeit.default_timer()
    assert solver.check().satisfiable is not False
    model = solver.model()
    elapsed = timeit.default_timer() - start_time
    num_facts = len(model.ground_terms)
    print(
        f"method: {method_name}, depth: {depth}, num_children: {num_children}, entailed: {num_facts} elapsed: {elapsed:.3f}"
    )
    assert model.ground_terms
    if expected is not None:
        assert num_facts == expected
    # for f in model.facts:
    #    print(f" FACT={f}")
