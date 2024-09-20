from __future__ import annotations

from pathlib import Path

import pytest
from typedlogic import FactMixin
from typedlogic.datamodel import NotInProfileError, Term
from typedlogic.decorators import predicate
from typedlogic.integrations.frameworks.owldl import (
    ObjectIntersectionOf,
    ObjectSomeValuesFrom,
    PropertyExpressionChain,
    Thing,
    TopObjectProperty,
)
from typedlogic.integrations.frameworks.owldl.reasoner import OWLReasoner
from typedlogic.integrations.solvers.clingo import ClingoSolver
from typedlogic.integrations.solvers.prover9 import Prover9Solver
from typedlogic.integrations.solvers.snakelog import SnakeLogSolver
from typedlogic.integrations.solvers.souffle import SouffleSolver
from typedlogic.integrations.solvers.z3 import Z3Solver
from typedlogic.parsers.pyparser.python_parser import PythonParser
from typedlogic.transformations import PrologConfig, as_prolog, to_horn_rules

from tests import INPUT_DIR, TESTS_DIR

ONTOLOGY_DIR = TESTS_DIR / "test_frameworks" / "owldl"

@predicate
class Person(Thing):
    """A person is a thing."""

    disjoint_union_of = ["Man", "Woman"]

@predicate
class Man(Person):
    pass

@predicate
class Woman(Person):
    pass

@predicate
class HasDescendant(TopObjectProperty):
    transitive = True
    asymmetric = True
    domain = Person
    range = Person

@predicate
class HasChild(HasDescendant):
    range = Person

@predicate
class HasAncestor(TopObjectProperty):
    inverse_of = HasDescendant

@predicate
class HasParent(HasAncestor):
    inverse_of = HasChild

@predicate
class HasGrandchild(HasDescendant):
    subproperty_chain = PropertyExpressionChain(HasChild, HasChild)

@predicate
class Parent(Person):
    """A parent is a person who has a child."""

    equivalent_to = ObjectIntersectionOf(Person, ObjectSomeValuesFrom(HasChild, Thing))

@predicate
class Father(Person):
    equivalent_to = ObjectIntersectionOf(Parent, Man)


def test_instances():
    p = Person("P1")
    assert isinstance(p, Person)
    assert isinstance(p, FactMixin)
    hs = HasChild("P1", "P2")
    for ax in Parent.axioms():
        print(ax)
    assert Parent.axioms()
    sentences = Parent.to_sentences()
    for s in sentences:
        print(s)
    assert sentences
    for cls in [Person, HasDescendant, HasChild, HasGrandchild, Parent, Father]:
        for s in cls.to_sentences():
            print(f"CLASS={cls} AXIOMS={cls.axioms()} SENTENCE={s}")


def test_pyparse():
    p = PythonParser()
    theory = p.parse(Path(__file__))
    assert theory.predicate_definitions
    for s in theory.sentences:
        print(s)
    progs = {}
    for nesting in [True, False]:
        prolog_config = PrologConfig(disjunctive_datalog=True, allow_nesting=nesting)
        lines = []
        for sentence in theory.sentences:
            try:
                for rule in to_horn_rules(sentence, allow_disjunctions_in_head=True, allow_goal_clauses=True):
                    lines.append(as_prolog(rule, config=prolog_config))
            except NotInProfileError as e:
                print(f"Skipping sentence {sentence} due to {e}")
        progs[nesting] = lines

    assert progs[True] == progs[False]


@pytest.mark.parametrize("facts,expected,abox,coherent", [
    ([
        #Person("P1"),
        #Person("P2"),
        HasChild("P1", "P2"),
        HasChild("P2", "P3"),
        Man("P1"),
      ],
      [Person("P1"),
       Person("P2"),
       HasDescendant("P1", "P2"), HasDescendant("P1", "P3"), HasDescendant("P2", "P3"),
       HasGrandchild("P1", "P3"),
       Parent("P1"),
       # Parent("P2"),
       Father("P1"),
       HasParent("P2", "P1"),
       HasParent("P3", "P2"),
       HasAncestor("P2", "P1"),
       HasAncestor("P3", "P2"),
       HasAncestor("P3", "P1"),
       ],
        True,
        True),
    ([
        Person("P1"),
        Person("P2"),
        HasChild("P1", "P2"),
        HasChild("P2", "P3"),
        HasChild("P3", "P1"),
        ],
        None,
        True,
        False),
])
@pytest.mark.parametrize("solver", [Z3Solver, ClingoSolver, SouffleSolver])
def test_reasoning(solver, facts, expected, abox, coherent):
    """
    Tests the OWL reasoner.

    The OWL Reasoner translates the OWL axioms into FOL, and then will apply a wrapped solver.

    - the Z3 solver should give complete results, but it is slow so we skip it
    - Souffle cannot handle stratified negation, so results may not be complete even for simple rule subsets
    - Clingo should give complete results for the disjunctive datalog subset

    :param solver:
    :param facts:
    :param expected:
    :param abox:
    :param coherent:
    :return:
    """
    if solver == Z3Solver:
        pytest.skip("Slow")
    reasoner = OWLReasoner(solver_class=solver)
    assert __file__.endswith(".py")
    reasoner.init_from_file(__file__)
    for f in facts:
        reasoner.add(f)
    if solver != SouffleSolver:
        #print("COHERENT=", reasoner.coherent())
        #print(reasoner.solver.dump())
        assert reasoner.coherent() == coherent, f"Expected {coherent} for {facts}"
    if solver == Z3Solver:
        pytest.skip("TODO: models from Z3")
    if coherent:
        model = reasoner.model()
        print(reasoner.solver.dump())
        for t in model.ground_terms:
            print(t)
        expected = [e.to_model_object() for e in expected]
        for e in expected:
            assert e in model.ground_terms



@pytest.mark.parametrize("solver_class", [Z3Solver, ClingoSolver, Prover9Solver, SouffleSolver])
def test_consistency(solver_class):
    if solver_class == Prover9Solver:
        pytest.skip("TODO")
    if solver_class == SouffleSolver:
        pytest.skip("TODO")
    reasoner = OWLReasoner(solver_class=solver_class)
    reasoner.init_from_file(str(INPUT_DIR / "family_owldl.py"))
    facts = [Term("HasChild", "a", "b"), Term("HasChild", "b", "c") , Term("HasChild", "c", "a")]
    for f in facts:
        reasoner.add(f)
    assert not reasoner.coherent()

@pytest.mark.parametrize("depth,num_children,expected",
                         [
                             (1, 2, 4),
                             (2, 2, 16),
                             (5, 2, 320),
                             #(5, 3, 2004),
                             # (7, 3, 24603),
                         ])
@pytest.mark.parametrize("solver_class", [ClingoSolver, SouffleSolver, SnakeLogSolver])
def test_paths(solver_class, depth, num_children, expected):
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
    reasoner = OWLReasoner(solver_class=solver_class)
    import tests.test_frameworks.owldl.paths_owldl as paths_owldl
    links = paths_owldl.generate_ontology(node="a", depth=depth, num_children=num_children)
    reasoner.init_from_file(str(ONTOLOGY_DIR / "paths_owldl.py"))
    for s in reasoner.theory.sentences:
        print(f"S={s}")
    reasoner.add(links)
    #for s in reasoner.theory.sentences:
    #    print(f"S2={s}")
    assert reasoner.coherent()
    model = reasoner.model()
    for t in model.iter_retrieve("Path"):
        print(t)
    num_facts = len(list(model.iter_retrieve("Path"))) + len(list(model.iter_retrieve("Link")))
    if expected is not None:
        assert num_facts == expected



def test_incremental():
    # pytest.skip("TODO: test stratification")
    solver_class = ClingoSolver
    reasoner = OWLReasoner(solver_class=solver_class)
    reasoner.init_from_file(str(INPUT_DIR / "family_owldl.py"))
    facts = [Term("HasChild", "a", "b"), Term("HasChild", "b", "c")]
    for f in facts:
        reasoner.add(f)
    assert reasoner.coherent()
    model = reasoner.model()
    for t in model.ground_terms:
        print(t)
    assert len(list(model.iter_retrieve("HasDescendant"))) == 3
    assert len(list(model.iter_retrieve("HasAncestor"))) == 3
    # assert len(list(model.iter_retrieve("Parent"))) > 0
    print(reasoner.solver.dump())
    # inconsistent
    reasoner.set_solver_class(Z3Solver)
    reasoner.add(facts + [Term("HasChild", "c", "a")])
    for s in reasoner.theory.sentences:
        print(s)
    assert not reasoner.coherent()

def test_via_load():
    import tests.test_frameworks.owldl.family as family
    sentences = family.Parent.to_sentences()
    assert sentences
    for s in sentences:
        print(s)
        pc = PrologConfig()
        try:
            rules = to_horn_rules(s, allow_disjunctions_in_head=True, allow_goal_clauses=True)
        except NotInProfileError as e:
            print(f"Skipping sentence {s} due to {e}")
        for rule in rules:
            print(f"  RULE={rule}")
            try:
                pl = as_prolog(rule, config=pc, translate=True)
                print(f"    PROLOG={pl}")
            except NotInProfileError as e:
                print(f"Skipping sentence {s} due to {e}")

