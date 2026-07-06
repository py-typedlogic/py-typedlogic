import pytest
from typedlogic.compiler import ModelSyntax
from typedlogic.datamodel import (
    And,
    CardinalityConstraint,
    Exists,
    Forall,
    Implies,
    Not,
    Or,
    PredicateDefinition,
    Term,
    Theory,
    Variable,
)
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


def _cardinality_solver() -> Z3Solver:
    """A Z3 solver pre-loaded with predicate definitions used by the cardinality tests."""
    solver = Z3Solver()
    solver.add_predicate_definition(PredicateDefinition(predicate="Thing", arguments={"x": "str"}))
    solver.add_predicate_definition(PredicateDefinition(predicate="Wing", arguments={"y": "str"}))
    solver.add_predicate_definition(PredicateDefinition(predicate="HasWing", arguments={"x": "str", "y": "str"}))
    solver.add_predicate_definition(PredicateDefinition(predicate="Part", arguments={"y": "str"}))
    solver.add_predicate_definition(PredicateDefinition(predicate="HasPart", arguments={"x": "str", "y": "str"}))
    return solver


def test_cardinality_at_most_zero_existence_check():
    """A ``maximum_number`` of 0 forbids any witness (∀y. ¬(template ∧ conditions))."""
    x = Variable("X")
    y = Variable("Y")
    solver = _cardinality_solver()
    # Every Thing must have at most 0 wings.
    solver.add_sentence(
        Forall([x], Implies(Term("Thing", x), CardinalityConstraint(Term("HasWing", x, y), Term("Wing", y), None, 0)))
    )
    solver.add_fact(Term("Thing", "fly1"))
    # No wing asserted: consistent.
    assert solver.check().satisfiable
    # Asserting a wing for fly1 violates the "at most 0 wings" constraint.
    solver.add_fact(Term("Wing", "w1"))
    solver.add_fact(Term("HasWing", "fly1", "w1"))
    assert not solver.check().satisfiable


@pytest.mark.parametrize("actual_count,satisfiable", [(0, True), (1, True), (2, True), (3, False), (4, False)])
def test_cardinality_at_most_n(actual_count: int, satisfiable: bool):
    """An upper bound is violated once more than N pairwise-distinct witnesses are asserted."""
    x = Variable("X")
    y = Variable("Y")
    solver = _cardinality_solver()
    # Every Thing must have at most 2 parts.
    solver.add_sentence(
        Forall([x], Implies(Term("Thing", x), CardinalityConstraint(Term("HasPart", x, y), Term("Part", y), None, 2)))
    )
    solver.add_fact(Term("Thing", "t1"))
    for i in range(actual_count):
        solver.add_fact(Term("Part", f"p{i}"))
        solver.add_fact(Term("HasPart", "t1", f"p{i}"))
    assert solver.check().satisfiable == satisfiable


def test_cardinality_at_least_with_closed_domain():
    """A lower bound has teeth once the domain of witnesses is otherwise constrained.

    Under Z3's open-world assumption an "at least 1" constraint is satisfiable on its own
    (Z3 may invent a witness), but becomes unsatisfiable once another axiom forbids any
    witness from existing.
    """
    x = Variable("X")
    y = Variable("Y")
    solver = _cardinality_solver()
    # Every Thing must have at least 1 part.
    solver.add_sentence(
        Forall([x], Implies(Term("Thing", x), CardinalityConstraint(Term("HasPart", x, y), Term("Part", y), 1, None)))
    )
    solver.add_fact(Term("Thing", "t1"))
    # Open world: Z3 may posit a part for t1.
    assert solver.check().satisfiable
    # Now forbid anything from having a part; t1 can no longer meet its lower bound.
    solver.add_sentence(Forall([x, y], Implies(Term("HasPart", x, y), Or())))
    assert not solver.check().satisfiable


def test_cardinality_range_consistent():
    """A witness count within an explicit ``[min, max]`` range is satisfiable."""
    x = Variable("X")
    y = Variable("Y")
    solver = _cardinality_solver()
    # Every Thing must have between 1 and 3 parts.
    solver.add_sentence(
        Forall([x], Implies(Term("Thing", x), CardinalityConstraint(Term("HasPart", x, y), Term("Part", y), 1, 3)))
    )
    solver.add_fact(Term("Thing", "t1"))
    solver.add_fact(Term("Part", "p0"))
    solver.add_fact(Term("HasPart", "t1", "p0"))
    solver.add_fact(Term("Part", "p1"))
    solver.add_fact(Term("HasPart", "t1", "p1"))
    assert solver.check().satisfiable


def test_cardinality_range_upper_violation():
    """Exceeding the upper end of a ``[min, max]`` range is unsatisfiable."""
    x = Variable("X")
    y = Variable("Y")
    solver = _cardinality_solver()
    solver.add_sentence(
        Forall([x], Implies(Term("Thing", x), CardinalityConstraint(Term("HasPart", x, y), Term("Part", y), 1, 2)))
    )
    solver.add_fact(Term("Thing", "t1"))
    for i in range(3):
        solver.add_fact(Term("Part", f"p{i}"))
        solver.add_fact(Term("HasPart", "t1", f"p{i}"))
    assert not solver.check().satisfiable


@pytest.mark.parametrize("actual_count,satisfiable", [(1, True), (2, False)])
def test_cardinality_infers_counted_variable_sort_from_predicate(actual_count: int, satisfiable: bool):
    """An untyped counted variable takes its sort from the (int-typed) predicate it is counted over.

    Without domain inference the witness defaults to a string sort and mis-sorts against the
    int-typed ``HasPart``/``Part`` arguments, raising a Z3 sort mismatch instead of checking the bound.
    """
    solver = Z3Solver()
    solver.add_predicate_definition(PredicateDefinition(predicate="Thing", arguments={"x": "int"}))
    solver.add_predicate_definition(PredicateDefinition(predicate="Part", arguments={"y": "int"}))
    solver.add_predicate_definition(PredicateDefinition(predicate="HasPart", arguments={"x": "int", "y": "int"}))
    x = Variable("X")
    y = Variable("Y")
    # Every Thing must have at most 1 part; Y is untyped and must be inferred as int.
    solver.add_sentence(
        Forall([x], Implies(Term("Thing", x), CardinalityConstraint(Term("HasPart", x, y), Term("Part", y), None, 1)))
    )
    solver.add_fact(Term("Thing", 1))
    for i in range(actual_count):
        part = 10 * (i + 1)
        solver.add_fact(Term("Part", part))
        solver.add_fact(Term("HasPart", 1, part))
    assert solver.check().satisfiable == satisfiable


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


def test_untyped_quantified_variables_infer_type_from_declared_predicate():
    """Untyped tlog quantifier variables get their sort from the predicate they are used in.

    Without inference, quantified variables default to a string sort and mis-sort against an
    int-typed predicate, so a functional-dependency constraint fails to fire.
    """
    from typedlogic.parsers.tlog_parser import TLogParser

    inconsistent = TLogParser().parse(
        """
        pred foo(x: int, y: int).
        foo(1, 1).
        foo(1, 2).
        all x, y1, y2 | foo(x, y1), foo(x, y2) -> y1 = y2.
        """
    )
    solver = Z3Solver()
    solver.add(inconsistent)
    assert not solver.check().satisfiable

    consistent = TLogParser().parse(
        """
        pred foo(x: int, y: int).
        foo(1, 1).
        foo(2, 2).
        all x, y1, y2 | foo(x, y1), foo(x, y2) -> y1 = y2.
        """
    )
    solver = Z3Solver()
    solver.add(consistent)
    assert solver.check().satisfiable


def _naf_theory() -> Theory:
    """Build a mixed theory: one NAF rule plus a pure-Horn axiom and facts."""
    from typedlogic.datamodel import NegationAsFailure

    x = Variable("x", "str")
    theory = Theory(
        predicate_definitions=[
            PredicateDefinition("bird", {"x": "str"}),
            PredicateDefinition("penguin", {"x": "str"}),
            PredicateDefinition("abnormal", {"x": "str"}),
            PredicateDefinition("flies", {"x": "str"}),
        ],
    )
    theory.add(Forall([x], Implies(Term("penguin", x), Term("abnormal", x))))
    theory.add(Forall([x], Implies(And(Term("bird", x), NegationAsFailure(Term("abnormal", x))), Term("flies", x))))
    theory.ground_terms.extend([Term("bird", "tweety"), Term("bird", "pingu"), Term("penguin", "pingu")])
    return theory


def test_naf_sentences_are_skipped_with_a_warning(caplog):
    """One NAF rule must not break classical obligations elsewhere in the theory."""
    import logging

    theory = _naf_theory()
    solver = Z3Solver()
    with caplog.at_level(logging.WARNING):
        solver.add(theory)
    assert any("negation-as-failure" in rec.message for rec in caplog.records)
    assert solver.check().satisfiable
    # the pure-Horn part of the theory is still provable
    assert solver.prove(Term("abnormal", "pingu")) is True
    # the NAF rule was skipped, so its consequences are not derivable
    assert solver.prove(Term("flies", "tweety")) is False


def test_naf_sentences_raise_in_strict_mode():
    """With strict=True the solver refuses NAF instead of weakening the theory."""
    from typedlogic.datamodel import NotInProfileError

    theory = _naf_theory()
    solver = Z3Solver(strict=True)
    with pytest.raises(NotInProfileError, match="negation-as-failure"):
        solver.add(theory)


def test_prove_returns_unknown_for_naf_goal():
    """A goal containing NAF cannot be decided classically; prove returns None."""
    from typedlogic.datamodel import NegationAsFailure

    solver = Z3Solver()
    solver.add(PredicateDefinition(predicate="p", arguments={"x": "str"}))
    solver.add(Term("p", "a"))
    assert solver.prove(NegationAsFailure(Term("p", "b"))) is None


def test_clark_completion_makes_naf_theory_provable():
    """Clark completion gives the NAF rules a faithful classical rendering for Z3."""
    from typedlogic.transformations import clark_completion

    completed = clark_completion(_naf_theory())
    solver = Z3Solver()
    solver.add(completed)
    assert solver.check().satisfiable
    # tweety is a bird and provably not abnormal under the completion
    assert solver.prove(Term("flies", "tweety")) is True
    # pingu is an abnormal penguin: flies(pingu) must not be entailed
    assert solver.prove(Term("flies", "pingu")) is False
    assert solver.prove(Term("abnormal", "pingu")) is True
    assert solver.prove(Not(Term("abnormal", "tweety"))) is True


def test_clark_completion_locally_stratified_recursion_through_negation():
    """A locally stratified program (mutual NAF recursion over a finite member tree) proves classically."""
    from typedlogic.datamodel import NegationAsFailure
    from typedlogic.transformations import clark_completion

    i, j = Variable("i", "str"), Variable("j", "str")
    theory = Theory(
        predicate_definitions=[
            PredicateDefinition("member", {"parent": "str", "child": "str"}),
            PredicateDefinition("scope", {"i": "str"}),
            PredicateDefinition("sat", {"i": "str"}),
            PredicateDefinition("viol", {"i": "str"}),
        ],
    )
    theory.add(Forall([i], Implies(And(Term("scope", i), NegationAsFailure(Term("viol", i))), Term("sat", i))))
    theory.add(Forall([i, j], Implies(And(Term("member", i, j), NegationAsFailure(Term("sat", j))), Term("viol", i))))
    theory.ground_terms.extend(
        [
            Term("scope", "root"),
            Term("scope", "leaf1"),
            Term("scope", "leaf2"),
            Term("member", "root", "leaf1"),
            Term("member", "root", "leaf2"),
        ]
    )
    solver = Z3Solver()
    solver.add(clark_completion(theory))
    assert solver.check().satisfiable
    # leaves have no members, hence no violations, hence are satisfied
    assert solver.prove(Term("sat", "leaf1")) is True
    # both members of root are satisfied, so root is not violated and is satisfied
    assert solver.prove(Term("viol", "root")) is False
    assert solver.prove(Term("sat", "root")) is True
