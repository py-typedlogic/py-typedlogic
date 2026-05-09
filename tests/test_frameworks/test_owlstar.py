"""Tests for the OWLStar framework predicates and rules."""

# ruff: noqa: S101

import pytest
import typedlogic.integrations.frameworks.owlstar as owlstar_package
from typedlogic.integrations.frameworks.owlstar import owlstar
from typedlogic.integrations.solvers.souffle.souffle_compiler import SouffleCompiler
from typedlogic.parsers.pyparser.introspection import translate_module_to_theory


def test_owlstar_module_loads_predicates_and_axioms():
    """Test that the OWLStar module exposes predicates and axiom groups."""
    theory = translate_module_to_theory(owlstar)

    predicate_names = {predicate.predicate for predicate in theory.predicate_definitions}
    assert "Edge" not in predicate_names
    assert "PredicateCharacteristic" not in predicate_names
    assert {
        "DisjointClasses",
        "DisjointOver",
        "EdgeAllNone",
        "EdgeAllOne",
        "EdgeAllSome",
        "TransitivePredicate",
    } <= predicate_names
    assert {group.name for group in theory.sentence_groups} >= {"disjointness", "transitivity", "unary_rules"}


def test_owlstar_package_loads_predicates_and_axioms():
    """Test that the public OWLStar package module can be loaded as a theory."""
    theory = translate_module_to_theory(owlstar_package)

    predicate_names = {predicate.predicate for predicate in theory.predicate_definitions}
    assert "EdgeAllSome" in predicate_names
    assert "DisjointOver" in predicate_names
    assert {group.name for group in theory.sentence_groups} >= {"disjointness", "transitivity", "unary_rules"}


def test_owlstar_disjointness_is_preserved_for_souffle_compilation():
    """Test that Souffle compilation keeps disjointness as positive inference."""
    theory = translate_module_to_theory(owlstar)
    compiled = SouffleCompiler().compile(theory)

    assert "EdgeAllNone(s, p, c2) :- DisjointOver(c1, c2, p), EdgeAllSome(s, p, c1)." in compiled
    assert "EdgeAllNone(s, p, c2) :- DisjointClasses(c1, c2), EdgeAllOne(s, p, c1)." in compiled


def test_owlstar_disjoint_over_detects_inconsistent_all_some_edges_with_z3():
    """Test that Z3 detects inconsistent all-some edges over disjoint classes."""
    pytest.importorskip("z3")
    from typedlogic.integrations.solvers.z3.z3_solver import Z3Solver

    solver = Z3Solver()
    solver.load(owlstar)
    solver.add(owlstar.DisjointOver("Nucleus", "Membrane", "part_of"))
    solver.add(owlstar.EdgeAllSome("Cell", "part_of", "Nucleus"))
    solver.add(owlstar.EdgeAllSome("Cell", "part_of", "Membrane"))

    assert solver.check().satisfiable is False


def test_owlstar_disjoint_classes_allow_distinct_existential_fillers_with_z3():
    """Test that bare class disjointness does not reject two all-some edges."""
    pytest.importorskip("z3")
    from typedlogic.integrations.solvers.z3.z3_solver import Z3Solver

    solver = Z3Solver()
    solver.load(owlstar)
    solver.add(owlstar.DisjointClasses("Nucleus", "Membrane"))
    solver.add(owlstar.EdgeAllSome("Cell", "part_of", "Nucleus"))
    solver.add(owlstar.EdgeAllSome("Cell", "part_of", "Membrane"))

    assert solver.check().satisfiable is True


def test_owlstar_disjoint_classes_constrain_exact_one_edges_with_z3():
    """Test that exact-one edges are incompatible with disjoint same-predicate fillers."""
    pytest.importorskip("z3")
    from typedlogic.integrations.solvers.z3.z3_solver import Z3Solver

    solver = Z3Solver()
    solver.load(owlstar)
    solver.add(owlstar.DisjointClasses("Nucleus", "Membrane"))
    solver.add(owlstar.EdgeAllOne("Cell", "part_of", "Nucleus"))
    solver.add(owlstar.EdgeAllSome("Cell", "part_of", "Membrane"))

    assert solver.check().satisfiable is False


def test_owlstar_edge_all_one_entails_edge_all_some_with_z3():
    """Test that exact-one restrictions expose their existential consequence."""
    pytest.importorskip("z3")
    from typedlogic.integrations.solvers.z3.z3_solver import Z3Solver

    solver = Z3Solver()
    solver.load(owlstar)
    solver.add(owlstar.EdgeAllOne("Finger", "part_of", "Hand"))

    assert solver.prove(owlstar.EdgeAllSome.p("Finger", "part_of", "Hand")) is True
