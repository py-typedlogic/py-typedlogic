import pytest
from typedlogic.compiler import ModelSyntax
from typedlogic.datamodel import And, Exists, Forall, Implies, PredicateDefinition, Term, Theory, Variable
from typedlogic.integrations.solvers.z3 import Z3Solver
from typedlogic.integrations.solvers.z3.z3_compiler import Z3Compiler
from typedlogic.parsers.pyparser.python_parser import PythonParser

import tests.theorems.mortals as mortals
from tests.theorems import animals, numbers, types_example

X = Variable("x")


def test_solver():
    solver = Z3Solver()
    parser = PythonParser()
    theory = parser.transform(mortals)
    # for s in theory.sentences:
    #    print(s)
    # print(theory)
    solver.add(theory)
    assert solver.check().satisfiable
    f1 = mortals.AncestorOf(ancestor="p1", descendant="p1a")
    f2 = mortals.AncestorOf(ancestor="p1a", descendant="p1aa")
    assert solver.check().satisfiable
    solver.add_fact(f1)
    assert solver.check().satisfiable
    solver.add_fact(f2)
    # print(solver.wrapped_solver)
    assert solver.check().satisfiable
    models = list(solver.models())
    assert models
    print("MODELS:", models)
    model = models[0]
    # for f in model.facts:
    #    print(f" FACT={f}")
    # cycle
    f3 = mortals.AncestorOf(ancestor="p1aa", descendant="p1")
    solver.add_fact(f3)
    assert not solver.check().satisfiable
    # print(solver.dump())
    # print(solver.wrapped_solver.sexpr())


@pytest.mark.parametrize(
    "axioms,goal,provable",
    [
        (Term("p", "a"), Term("p", "a"), True),
        (Term("p", "a"), Term("p", "b"), False),
        (Term("n", 1), Term("n", 1), True),
        (Term("n", 1), Term("n", 2), False),
        (Forall([X], Term("p", X) >> Term("q", X)), (Term("p", "a") >> Term("p", "a")), True),
    ],
)
def test_prove(axioms, goal, provable):
    solver = Z3Solver()
    solver.add(PredicateDefinition(predicate="p", arguments={"x": "str"}))
    solver.add(PredicateDefinition(predicate="q", arguments={"x": "str"}))
    solver.add(PredicateDefinition(predicate="n", arguments={"x": "int"}))
    solver.add(axioms)
    assert solver.check().satisfiable
    assert solver.prove(goal) == provable


def test_prove_goals():
    solver = Z3Solver()
    parser = PythonParser()
    theory = parser.transform(mortals)
    solver.add(theory)
    assert solver.check().satisfiable
    assert solver.goals
    results = list(solver.prove_goals(strict=True))
    assert results
    assert len(results) == 1


def test_z3_compiler():
    parser = PythonParser()
    theory = parser.transform(mortals)
    compiler = Z3Compiler()
    sexpr = compiler.compile(theory)
    print("## MORTALS:")
    print(sexpr)
    assert sexpr
    sexpr2 = compiler.compile(theory, syntax=ModelSyntax.SEXPR)
    assert sexpr == sexpr2
    fexpr = compiler.compile(theory, syntax=ModelSyntax.FUNCTIONAL)
    print("## FUNCTIONAL:")
    print(fexpr)
    assert fexpr
    assert fexpr != sexpr
    theory = parser.transform(animals)
    sexpr = compiler.compile(theory)
    print("## ANIMALS:")
    print(sexpr)
    # assert "(assert (forall ((x String) (species String)) (=> (Animal x dog) (not (Likes Fred x)))))" in sexpr
    theory = parser.transform(numbers)
    sexpr = compiler.compile(theory)
    print(sexpr)
    assert "(name1 String)" in sexpr
    assert "(name2 String)" in sexpr
    # assert "(age Integer)" in sexpr


@pytest.mark.parametrize(
    "t1,t2,inst1,inst2",
    [
        ("str", "str", "v1", "v2"),
        ("str", "int", "v1", 5),
        ("int", "int", 1, 2),
    ],
)
def test_types(t1, t2, inst1, inst2):
    solver = Z3Solver()
    compiler = Z3Compiler()
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
    solver = Z3Solver()
    parser = PythonParser()
    theory = parser.transform(animals)
    solver.add(theory)
    assert solver.check().satisfiable
    solver.add(animals.Likes(subject="Fred", object="fido"))
    print(solver.dump())
    assert not solver.check().satisfiable


def test_numbers():
    solver = Z3Solver()
    parser = PythonParser()
    theory = parser.transform(numbers)
    solver.add(theory)
    assert solver.check().satisfiable


def test_types_example():
    solver = Z3Solver()
    parser = PythonParser()
    theory = parser.transform(types_example)
    assert theory.constants["AGE_THRESHOLD"] == 18
    solver.add(theory)
    assert solver.constants["AGE_THRESHOLD"] == 18
    assert solver.check().satisfiable
    goals_proved = list(solver.prove_goals())
    assert goals_proved
    assert len(goals_proved) == 2


@pytest.mark.parametrize(
    "op,py_result",
    [
        ("add", 7),
        ("sub", 1),
        ("mul", 12),
    ],
)
def test_nested_builtin_terms(op, py_result):
    """Nested arithmetic terms should map through the full builtin table, not just add."""
    import z3

    solver = Z3Solver()
    solver.add(PredicateDefinition(predicate="R", arguments={"a": "int"}))
    a = Variable("a", "int")
    b = Variable("b", "int")
    # R(op(a, b)) with a=4, b=3 supplied via constants
    solver.constants["a"] = 4
    solver.constants["b"] = 3
    expr = solver.translate(Term("R", {"a": Term(op, a, b)}))
    # The nested term evaluates to a concrete Z3 value equal to the Python result.
    assert z3.simplify(expr.arg(0)) == z3.simplify(z3.IntVal(py_result))


def test_deeply_nested_builtin_terms():
    """Nested arithmetic terms should recurse through arbitrary builtin subterms."""
    import z3

    solver = Z3Solver()
    solver.add(PredicateDefinition(predicate="R", arguments={"a": "int"}))
    a = Variable("a", "int")
    b = Variable("b", "int")
    c = Variable("c", "int")
    solver.constants.update({"a": 4, "b": 3, "c": 2})
    expr = solver.translate(Term("R", {"a": Term("add", Term("sub", a, b), c)}))
    assert z3.simplify(expr.arg(0)) == z3.simplify(z3.IntVal(3))


def test_quantifier_variable_not_captured_across_siblings():
    """A variable bound only inside one subformula must not leak into a sibling."""
    solver = Z3Solver()
    solver.add(PredicateDefinition(predicate="P", arguments={"x": "int"}))
    solver.add(PredicateDefinition(predicate="Q", arguments={"x": "int"}))
    x = Variable("x", "int")
    y = Variable("y", "int")
    # forall x: (exists y: P(y)) & Q(y)  -- the second y has no binding in scope
    sentence = Forall([x], And(Exists([y], Term("P", {"x": y})), Term("Q", {"x": y})))
    with pytest.raises(ValueError):
        solver.translate(sentence)


def test_reasoning_with_existential_subformula():
    """End-to-end: an existential nested in a universal should reason correctly."""
    solver = Z3Solver()
    solver.add(PredicateDefinition(predicate="Edge", arguments={"src": "int", "tgt": "int"}))
    solver.add(PredicateDefinition(predicate="HasOut", arguments={"src": "int"}))
    x = Variable("x", "int")
    y = Variable("y", "int")
    # forall x: (exists y: Edge(x, y)) -> HasOut(x)
    solver.add(Forall([x], Implies(Exists([y], Term("Edge", {"src": x, "tgt": y})), Term("HasOut", {"src": x}))))
    solver.add_fact(Term("Edge", {"src": 1, "tgt": 2}))
    assert solver.check().satisfiable
    assert solver.prove(Term("HasOut", {"src": 1}))
