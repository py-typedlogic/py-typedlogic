import timeit

import pytest
from typedlogic.datamodel import Forall, PredicateDefinition, Term, Theory, Variable
from typedlogic.integrations.solvers.souffle import SouffleSolver
from typedlogic.integrations.solvers.souffle.souffle_compiler import SouffleCompiler
from typedlogic.parsers.pyparser.python_parser import PythonParser
from typedlogic.transformations import implies_from_parents

import tests.theorems.mortals as mortals
from tests import tree_edges
from tests.theorems import animals, numbers, paths, types_example

X = Variable("x")

@pytest.mark.parametrize("depth,num_children,expected",
                         [
                             (1, 2, 4),
                             (2, 2, 16),
                             (5, 2, 320),
                             (5, 3, 2004),
                             # (7, 3, 24603),
                         ])
def test_paths(depth, num_children, expected):
    """
    Test simple transitivity over paths.

    This also tests inference of implication axioms for python parent classes.

    This test can be adapted for benchmarking.

    Example benchmarks:

    - method: litelog, depth: 8, num_children: 3, entailed: 19680 elapsed: 0.088
    - souffle, depth: 8, num_children: 3, entailed: 19680 elapsed: 11.785


    :param method_name:
    :param depth:
    :param num_children:
    :param expected:
    :return:
    """
    solver = SouffleSolver()
    parser = PythonParser()
    theory = parser.transform(paths)
    theory = implies_from_parents(theory)
    solver.add(theory)
    for source, target in tree_edges("a", depth, num_children):
        solver.add(paths.Link(source=source, target=target))
    for s in theory.sentences:
        print("ORIG", s)

    compiler = SouffleCompiler()
    program = compiler.compile(solver.base_theory)
    print(program)
    start_time = timeit.default_timer()
    assert solver.check().satisfiable is not False
    model = solver.model()
    elapsed = timeit.default_timer() - start_time
    num_facts = len(model.ground_terms)
    print(f"method: SOUFFLE, depth: {depth}, num_children: {num_children}, entailed: {num_facts} elapsed: {elapsed:.3f}")
    assert model.ground_terms
    #for t in model.ground_terms:
    #    print(f"FACT: {t}")
    if expected is not None:
        assert num_facts == expected

def test_solver():
    solver = SouffleSolver()
    parser = PythonParser()
    theory = parser.transform(mortals)
    #for s in theory.sentences:
    #    print(s)
    #print(theory)
    solver.add(theory)
    assert solver.check().satisfiable is not False
    f1 = mortals.AncestorOf(ancestor="p1", descendant="p1a")
    f2 = mortals.AncestorOf(ancestor="p1a", descendant="p1aa")
    solver.add_fact(f1)
    solver.add_fact(f2)
    #print(solver.wrapped_solver)
    models = list(solver.models())
    assert models
    print("MODELS:" , models)
    model = models[0]
    for f in model.ground_terms:
        print(f" FACT={f}")
    # cycle
    f3 = mortals.AncestorOf(ancestor="p1aa", descendant="p1")
    solver.add_fact(f3)
    assert not solver.check().satisfiable
    #print(solver.dump())
    #print(solver.wrapped_solver.sexpr())


@pytest.mark.parametrize("axioms,goal,provable", [
    (Term("p", "a"), Term("p", "a"), True),
    (Term("p", "a"), Term("p", "b"), False),
    (Term("n", 1), Term("n", 1), True),
    (Term("n", 1), Term("n", 2), False),
    (Forall([X], Term("p", X) >> Term("q", X)),
     (Term("p", "a") >> Term("p", "a")),
      True),
    ]
)
def test_prove(axioms, goal, provable):
    pytest.skip("TODO")
    solver = SouffleSolver()
    solver.add(PredicateDefinition(predicate="p", arguments={"x": "str"}))
    solver.add(PredicateDefinition(predicate="q", arguments={"x": "str"}))
    solver.add(PredicateDefinition(predicate="n", arguments={"x": "int"}))
    solver.add(axioms)
    assert solver.check().satisfiable
    assert solver.prove(goal) == provable



def test_prove_goals():
    pytest.skip("TODO")
    solver = SouffleSolver()
    parser = PythonParser()
    theory = parser.transform(mortals)
    solver.add(theory)
    assert solver.check().satisfiable
    assert solver.goals
    results = list(solver.prove_goals(strict=True))
    assert results
    assert len(results) == 1

def test_souffle_compiler():
    parser = PythonParser()
    theory = parser.transform(mortals)
    compiler = SouffleCompiler()
    txt = compiler.compile(theory)
    print("## MORTALS:")
    print(txt)
    assert txt
    theory = parser.transform(animals)
    txt = compiler.compile(theory)
    print("## ANIMALS:")
    print(txt)
    # assert "(assert (forall ((x String) (species String)) (=> (Animal x dog) (not (Likes Fred x)))))" in sexpr
    theory = parser.transform(numbers)
    txt = compiler.compile(theory)
    print("## NUMBERS:")
    print(txt)



@pytest.mark.parametrize("t1,t2,inst1,inst2", [
    ("str", "str", "v1", "v2"),
    ("str", "int", "v1", 5),
    ("int", "int", 1, 2),
])
def test_types(t1, t2, inst1, inst2):
    pytest.skip("TODO")
    solver = SouffleSolver()
    compiler = SouffleCompiler()
    pd = PredicateDefinition(predicate="Test", arguments={"x": t1, "y": t2})
    theory = Theory(
        name="test",
        predicate_definitions=[pd],
    )
    sexpr = compiler.compile(theory)
    print(sexpr)
    # TODO: check why declare-fun not present
    assert not sexpr
    solver.add(theory)
    assert solver.check().satisfiable
    f1 = Term("Test", inst1, inst2)
    solver.add(f1)
    assert solver.check().satisfiable
    theory.add(f1)
    sexpr = compiler.compile(theory)
    print(sexpr)
    assert sexpr
    def map_type(t):
        if t == "int":
            return "Int"
        if t == "str":
            return "String"
        return t
    def map_val(v):
        if isinstance(v, str):
            return f'"{v}"'
        return str(v)
    t1m = map_type(t1)
    t2m = map_type(t2)
    assert f"(declare-fun Test ({t1m} {t2m}) Bool)" in sexpr
    inst1m = map_val(inst1)
    inst2m = map_val(inst2)
    assert f"(assert (Test {inst1m} {inst2m}))" in sexpr




def test_animals():
    pytest.skip("TODO")
    solver = SouffleSolver()
    parser = PythonParser()
    theory = parser.transform(animals)
    solver.add(theory)
    assert solver.check().satisfiable
    solver.add(animals.Likes(subject="Fred", object="fido"))
    print(solver.dump())
    assert not solver.check().satisfiable


def test_numbers():
    pytest.skip("TODO")
    solver = SouffleSolver()
    parser = PythonParser()
    theory = parser.transform(numbers)
    solver.add(theory)
    assert solver.check().satisfiable


def test_types_example():
    pytest.skip("TODO")
    solver = SouffleSolver()
    parser = PythonParser()
    theory = parser.transform(types_example)
    assert theory.constants["AGE_THRESHOLD"] == 18
    solver.add(theory)
    assert solver.constants["AGE_THRESHOLD"] == 18
    assert solver.check().satisfiable
    goals_proved = list(solver.prove_goals())
    assert goals_proved
    assert len(goals_proved) == 2
