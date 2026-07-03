"""Tests for the well-founded semantics solver and its backends.

The ``native`` and ``problog`` backends run everywhere; the ``xsb`` backend is
skipped when the external XSB executable is not on PATH (mirroring the Souffle
and Prover9 integration tests).
"""

import shutil

import pytest

from typedlogic.integrations.solvers.wellfounded import (
    NegativeCycleError,
    WellFoundedModel,
    WellFoundedSolver,
)
from typedlogic.parsers.tlog_parser import TLogParser

# --- fixtures: canonical normal logic programs -------------------------------

BIRDS = """
pred Bird(name: str).
pred Penguin(name: str).
pred Abnormal(name: str).
pred Flies(name: str).

Bird("tweety").
Bird("opus").
Penguin("opus").

Abnormal(x) :- Penguin(x).
Flies(x) :- Bird(x), not Abnormal(x).
"""

EVEN_LOOP = """
pred p().
pred q().
p() :- not q().
q() :- not p().
"""

ODD_LOOP = """
pred p().
p() :- not p().
"""


def solve(program: str, backend: str = "native") -> WellFoundedModel:
    solver = WellFoundedSolver(backend=backend)
    solver.add(TLogParser().parse(program))
    return solver.model()


def true_atoms(model: WellFoundedModel):
    return sorted(str(t) for t in model.ground_terms)


def undefined_atoms(model: WellFoundedModel):
    return sorted(str(t) for t in model.undefined_terms)


# --- native backend: full three-valued semantics -----------------------------


def test_native_stratified_default_reasoning():
    """A bird flies unless shown abnormal; the penguin does not."""
    model = solve(BIRDS)
    assert "Flies(tweety)" in true_atoms(model)
    assert "Flies(opus)" not in true_atoms(model)
    assert undefined_atoms(model) == []  # stratified => total model


def test_native_even_loop_is_undefined():
    """p :- not q; q :- not p has two stable models but a single WFS: both undefined."""
    model = solve(EVEN_LOOP)
    assert true_atoms(model) == []
    assert undefined_atoms(model) == ["p", "q"]


def test_native_odd_loop_is_undefined():
    """p :- not p has no stable model but a single WFS: p undefined."""
    model = solve(ODD_LOOP)
    assert true_atoms(model) == []
    assert undefined_atoms(model) == ["p"]


def test_native_always_satisfiable():
    """A well-founded model always exists, even for the paradoxical odd loop."""
    solver = WellFoundedSolver()
    solver.add(TLogParser().parse(ODD_LOOP))
    assert solver.check().satisfiable is True
    assert len(list(solver.models())) == 1


def test_native_positive_recursion():
    """Ordinary transitive closure works (positive bodies, no negation)."""
    program = """
    pred edge(a: str, b: str).
    pred path(a: str, b: str).
    edge("a", "b").
    edge("b", "c").
    path(x, y) :- edge(x, y).
    path(x, z) :- edge(x, y), path(y, z).
    """
    model = solve(program)
    atoms = true_atoms(model)
    assert "path(a, c)" in atoms
    assert undefined_atoms(model) == []


# --- problog backend: two-valued WFS via a wrapped engine --------------------


def test_problog_agrees_on_stratified():
    """The wrapped ProbLog engine agrees with the native backend on stratified programs."""
    pytest.importorskip("problog")
    native = set(true_atoms(solve(BIRDS, backend="native")))
    problog = set(true_atoms(solve(BIRDS, backend="problog")))
    assert native == problog


def test_problog_refuses_negative_cycle():
    """ProbLog implements only the two-valued restriction: it refuses undefined programs."""
    pytest.importorskip("problog")
    with pytest.raises(NegativeCycleError):
        solve(EVEN_LOOP, backend="problog")


# --- backend selection / error handling --------------------------------------


def test_unknown_backend_raises():
    solver = WellFoundedSolver(backend="nope")
    solver.add(TLogParser().parse(ODD_LOOP))
    with pytest.raises(ValueError):
        solver.model()


def test_xsb_missing_binary_raises_clear_error():
    if shutil.which("xsb") is not None:
        pytest.skip("XSB is installed; this test checks the missing-binary path")
    solver = WellFoundedSolver(backend="xsb")
    solver.add(TLogParser().parse(ODD_LOOP))
    with pytest.raises(FileNotFoundError):
        solver.model()


# --- xsb backend: only when the external engine is available -----------------


@pytest.mark.skipif(shutil.which("xsb") is None, reason="XSB executable not on PATH")
def test_xsb_stratified_matches_native():
    native = set(true_atoms(solve(BIRDS, backend="native")))
    xsb = set(true_atoms(solve(BIRDS, backend="xsb")))
    assert native == xsb


@pytest.mark.skipif(shutil.which("xsb") is None, reason="XSB executable not on PATH")
def test_xsb_even_loop_is_undefined():
    model = solve(EVEN_LOOP, backend="xsb")
    assert true_atoms(model) == []
    assert undefined_atoms(model) == ["p", "q"]
