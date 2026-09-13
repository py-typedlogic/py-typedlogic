"""
Tests for the Allen interval calculus example theory (``tests/theorems/allen_intervals.py``).

The scenarios are drawn from real developmental-stage data: numerically anchored human
stages, mouse Theiler stages with known starts but unknown ends, and Uberon
``existence_*`` assertions with no numbers at all. A final test derives the full
13x13 Allen composition table independently (by enumerating endpoint orderings) and
checks that the point-based theory reproduces it without the table ever being asserted.
"""

import itertools
import shutil
from typing import Dict, FrozenSet, Iterable, Optional, Set, Tuple, Type

import pytest

from tests.theorems import allen_intervals as ai
from typedlogic import FactMixin
from typedlogic.integrations.solvers.clingo import ClingoSolver
from typedlogic.integrations.solvers.souffle import SouffleSolver
from typedlogic.integrations.solvers.z3 import Z3Solver
from typedlogic.solver import Model, Solver

DATALOG_SOLVERS = [ClingoSolver] + ([SouffleSolver] if shutil.which("souffle") else [])

# Allen letters in the standard order; uppercase is the converse of lowercase (e is self-converse).
REL = "pmoFDseSdfOMP"
ATOM_CLASS: Dict[str, Type[FactMixin]] = {
    "p": ai.Precedes,
    "m": ai.Meets,
    "o": ai.Overlaps,
    "F": ai.FinishedBy,
    "D": ai.Contains,
    "s": ai.Starts,
    "e": ai.Equals,
    "S": ai.StartedBy,
    "d": ai.During,
    "f": ai.Finishes,
    "O": ai.OverlappedBy,
    "M": ai.MetBy,
    "P": ai.PrecededBy,
}
# Compound relations and the Allen label (set of atoms) each one stands for.
COMPOUND_LABEL: Dict[Type[FactMixin], FrozenSet[str]] = {
    ai.StartsDuring: frozenset("dfO"),
    ai.EndsDuring: frozenset("osd"),
    ai.StartsBefore: frozenset("pmoFD"),
    ai.StartsAfter: frozenset("dfOMP"),
    ai.EndsBefore: frozenset("pmosd"),
    ai.EndsAfter: frozenset("DSOMP"),
    ai.StartsWith: frozenset("seS"),
    ai.EndsWith: frozenset("Fef"),
    ai.TemporallyOverlaps: frozenset("oFDseSdfO"),
}
ATOM_NAMES = {cls.__name__ for cls in ATOM_CLASS.values()}
COMPOUND_NAMES = {cls.__name__ for cls in COMPOUND_LABEL}


def add_interval(solver: Solver, name: str, start: Optional[int] = None, end: Optional[int] = None) -> None:
    """Add an interval with named endpoints, optionally anchoring either endpoint numerically."""
    solver.add_fact(ai.HasStart(name, f"{name}.start"))
    solver.add_fact(ai.HasEnd(name, f"{name}.end"))
    if start is not None:
        solver.add_fact(ai.At(f"{name}.start", start))
    if end is not None:
        solver.add_fact(ai.At(f"{name}.end", end))


def relations(model: Model, x: str, y: str, names: Iterable[str]) -> Set[str]:
    """Names of the interval relations derived between x and y, restricted to ``names``."""
    wanted = set(names)
    return {t.predicate for t in model.ground_terms if t.predicate in wanted and list(t.values) == [x, y]}


def positions(model: Model) -> Dict[str, int]:
    """Point -> derived numeric position."""
    return {str(t.values[0]): int(t.values[1]) for t in model.ground_terms if t.predicate == "At"}


# ---------------------------------------------------------------------------
# Independent derivation of Allen's algebra from endpoint orderings
# ---------------------------------------------------------------------------


def _holds(r: str, s1: int, e1: int, s2: int, e2: int) -> bool:
    return {
        "p": e1 < s2,
        "m": e1 == s2,
        "o": s1 < s2 < e1 < e2,
        "F": s1 < s2 and e1 == e2,
        "D": s1 < s2 and e2 < e1,
        "s": s1 == s2 and e1 < e2,
        "e": s1 == s2 and e1 == e2,
        "S": s1 == s2 and e2 < e1,
        "d": s2 < s1 and e1 < e2,
        "f": s2 < s1 and e1 == e2,
        "O": s2 < s1 < e2 < e1,
        "M": s1 == e2,
        "P": e2 < s1,
    }[r]


def _atom(s1: int, e1: int, s2: int, e2: int) -> str:
    hits = [r for r in REL if _holds(r, s1, e1, s2, e2)]
    assert len(hits) == 1, (s1, e1, s2, e2, hits)
    return hits[0]


def composition_table() -> Dict[Tuple[str, str], FrozenSet[str]]:
    """Derive the 13x13 Allen composition table by brute-force enumeration of six endpoints."""
    table: Dict[Tuple[str, str], Set[str]] = {}
    for sa, ea, sb, eb, sc, ec in itertools.product(range(6), repeat=6):
        if not (sa < ea and sb < eb and sc < ec):
            continue
        key = (_atom(sa, ea, sb, eb), _atom(sb, eb, sc, ec))
        table.setdefault(key, set()).add(_atom(sa, ea, sc, ec))
    return {k: frozenset(v) for k, v in table.items()}


def test_composition_table_shape():
    """Sanity check of the independent derivation against Allen (1983)."""
    table = composition_table()
    assert len(table) == 169
    assert table[("p", "p")] == {"p"}
    assert table[("m", "m")] == {"p"}
    assert table[("M", "M")] == {"P"}
    assert table[("o", "o")] == set("pmo")
    assert table[("p", "P")] == set(REL)
    assert sum(1 for v in table.values() if len(v) == 1) == 97


# ---------------------------------------------------------------------------
# Scenario 1: numerically anchored stages (HsapDv-like). Days post fertilization.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("solver_class", DATALOG_SOLVERS)
def test_numeric_anchoring_decides_atoms(solver_class):
    """Where both endpoints are known, comparing four numbers fixes the Allen atom."""
    solver = solver_class()
    solver.load(ai)
    add_interval(solver, "embryo", 0, 56)
    add_interval(solver, "CS10", 22, 24)
    add_interval(solver, "CS11", 24, 26)
    add_interval(solver, "CS12", 26, 30)
    add_interval(solver, "neurulation", 20, 28)
    model = solver.model()
    expected = {
        ("CS10", "CS11"): "Meets",
        ("CS11", "CS10"): "MetBy",
        ("CS10", "CS12"): "Precedes",
        ("CS10", "embryo"): "During",
        ("embryo", "CS12"): "Contains",
        ("neurulation", "CS11"): "Contains",
        ("neurulation", "CS12"): "Overlaps",
        ("CS12", "neurulation"): "OverlappedBy",
    }
    for (x, y), atom in expected.items():
        assert relations(model, x, y, ATOM_NAMES) == {atom}, (x, y)
    # RO compound relations follow from the same numbers
    assert "StartsDuring" in relations(model, "CS10", "embryo", COMPOUND_NAMES)
    assert "EndsDuring" in relations(model, "neurulation", "CS12", COMPOUND_NAMES)
    assert "TemporallyOverlaps" in relations(model, "CS12", "neurulation", COMPOUND_NAMES)
    assert "TemporallyOverlaps" not in relations(model, "CS10", "CS11", COMPOUND_NAMES)


# ---------------------------------------------------------------------------
# Scenario 2: starts known, ends unknown, joined by "immediately preceded by"
# (MmusDv Theiler stages). Hours post coitum.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("solver_class", DATALOG_SOLVERS)
def test_endpoints_propagate_across_meets(solver_class):
    """``meets`` transfers a number across a qualitative link; ``M o M`` yields strict precedence."""
    solver = solver_class()
    solver.load(ai)
    add_interval(solver, "TS10", start=156)
    add_interval(solver, "TS11", start=168)
    add_interval(solver, "TS12", start=180)
    add_interval(solver, "TS13", start=192)
    for later, earlier in [("TS11", "TS10"), ("TS12", "TS11"), ("TS13", "TS12")]:
        solver.add_fact(ai.MetBy(later, earlier))
    model = solver.model()
    pos = positions(model)
    assert pos["TS10.end"] == 168
    assert pos["TS11.end"] == 180
    assert pos["TS12.end"] == 192
    assert "TS13.end" not in pos
    # two steps back along the chain is strictly-preceded-by, which RO cannot express
    assert relations(model, "TS10", "TS12", ATOM_NAMES) == {"Precedes"}
    assert relations(model, "TS13", "TS10", ATOM_NAMES) == {"PrecededBy"}
    assert relations(model, "TS10", "TS11", ATOM_NAMES) == {"Meets"}


# ---------------------------------------------------------------------------
# Scenario 3: no numbers at all (Uberon existence_* assertions)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("solver_class", DATALOG_SOLVERS)
def test_intersection_and_composition_without_numbers(solver_class):
    """Two assertions about one pair intersect; assertions through a shared stage compose."""
    solver = solver_class()
    solver.load(ai)
    for name in ["morula", "cleavage", "conceptus", "embryo_stage", "blastocyst", "blastula", "gastrula"]:
        add_interval(solver, name)
    # intersection: dfO ∩ osd = d   (RO cannot derive its own 'existence starts and ends during')
    solver.add_fact(ai.StartsDuring("morula", "cleavage"))
    solver.add_fact(ai.EndsDuring("morula", "cleavage"))
    # intersection: seS ∩ Fef = e
    solver.add_fact(ai.StartsWith("conceptus", "embryo_stage"))
    solver.add_fact(ai.EndsWith("conceptus", "embryo_stage"))
    # composition: d o p = p
    solver.add_fact(ai.During("blastocyst", "blastula"))
    solver.add_fact(ai.Precedes("blastula", "gastrula"))
    model = solver.model()
    assert relations(model, "morula", "cleavage", ATOM_NAMES) == {"During"}
    assert relations(model, "conceptus", "embryo_stage", ATOM_NAMES) == {"Equals"}
    assert relations(model, "blastocyst", "gastrula", ATOM_NAMES) == {"Precedes"}
    assert relations(model, "gastrula", "blastocyst", ATOM_NAMES) == {"PrecededBy"}
    # nothing was asserted between blastocyst and gastrula: the relation is inferred
    assert relations(model, "morula", "gastrula", ATOM_NAMES) == set()


# ---------------------------------------------------------------------------
# Scenario 4: inconsistency detection
# ---------------------------------------------------------------------------


def test_degenerate_interval_is_inconsistent():
    """A zero-width stage violates the proper-interval axiom."""
    solver = ClingoSolver()
    solver.load(ai)
    add_interval(solver, "TS27", 456, 456)
    assert solver.check().satisfiable is False


def test_develops_from_starts_after():
    """``develops_from ⊑ starts_after``: a derived structure cannot begin before its precursor."""
    solver = ClingoSolver()
    solver.load(ai)
    add_interval(solver, "neural_plate", 18, 22)
    add_interval(solver, "neural_tube", 16, 30)
    solver.add_fact(ai.DevelopsFrom("neural_tube", "neural_plate"))
    assert solver.check().satisfiable is False

    solver = ClingoSolver()
    solver.load(ai)
    add_interval(solver, "neural_plate", 18, 22)
    add_interval(solver, "neural_tube", 20, 30)
    solver.add_fact(ai.DevelopsFrom("neural_tube", "neural_plate"))
    assert solver.check().satisfiable is True
    model = solver.model()
    assert "StartsAfter" in relations(model, "neural_tube", "neural_plate", COMPOUND_NAMES)
    assert relations(model, "neural_tube", "neural_plate", ATOM_NAMES) == {"OverlappedBy"}


def test_develops_from_is_transitive_and_qualitative():
    """Lineage chains compose with no numbers: the axiom applies through the transitive closure."""
    solver = ClingoSolver()
    solver.load(ai)
    for name in ["ectoderm", "neural_plate", "neural_tube"]:
        add_interval(solver, name)
    solver.add_fact(ai.DevelopsFrom("neural_tube", "neural_plate"))
    solver.add_fact(ai.DevelopsFrom("neural_plate", "ectoderm"))
    model = solver.model()
    assert "StartsAfter" in relations(model, "neural_tube", "ectoderm", COMPOUND_NAMES)
    assert "StartsBefore" in relations(model, "ectoderm", "neural_tube", COMPOUND_NAMES)


# ---------------------------------------------------------------------------
# The composition table is a theorem of the point definitions
# ---------------------------------------------------------------------------


def test_composition_table_is_derived_not_asserted():
    """
    Recover the composition table from the point definitions.

    For every pair of atoms (R1, R2), assert ``a R1 b`` and ``b R2 c`` on fresh intervals and
    read off what the theory derives between a and c.

    - An atom is derived exactly when the composition is a singleton.
    - A compound relation is derived exactly when its Allen label contains the composition:
      the endpoint invariants characterise the compound relations exactly.
    """
    table = composition_table()
    solver = ClingoSolver()
    solver.load(ai)
    names = {}
    for i, (r1, r2) in enumerate(table):
        a, b, c = f"a{i}", f"b{i}", f"c{i}"
        names[(r1, r2)] = (a, c)
        for name in (a, b, c):
            add_interval(solver, name)
        solver.add_fact(ATOM_CLASS[r1](a, b))
        solver.add_fact(ATOM_CLASS[r2](b, c))
    model = solver.model()
    for (r1, r2), (a, c) in names.items():
        expected = table[(r1, r2)]
        derived_atoms = relations(model, a, c, ATOM_NAMES)
        if len(expected) == 1:
            assert derived_atoms == {ATOM_CLASS[next(iter(expected))].__name__}, (r1, r2)
        else:
            assert derived_atoms == set(), (r1, r2, derived_atoms)
        derived_compounds = relations(model, a, c, COMPOUND_NAMES)
        expected_compounds = {cls.__name__ for cls, label in COMPOUND_LABEL.items() if expected <= label}
        assert derived_compounds == expected_compounds, (r1, r2, expected)


# ---------------------------------------------------------------------------
# Z3: the same theory as first-order axioms over integers
# ---------------------------------------------------------------------------


def _z3(timeout_ms: int = 30000) -> Z3Solver:
    solver = Z3Solver()
    solver.load(ai)
    solver.wrapped_solver.set("timeout", timeout_ms)
    return solver


def test_z3_proves_propagation_and_precedence():
    """Z3 proves a propagated endpoint and the two-step strict precedence, and refutes its converse."""
    solver = _z3()
    add_interval(solver, "TS10", start=156)
    add_interval(solver, "TS11", start=168)
    add_interval(solver, "TS12", start=180)
    solver.add_fact(ai.MetBy("TS11", "TS10"))
    solver.add_fact(ai.MetBy("TS12", "TS11"))
    assert solver.prove(ai.At("TS10.end", 168)) is True
    assert solver.prove(ai.Precedes("TS10", "TS12")) is True
    assert solver.prove(ai.Precedes("TS12", "TS10")) is not True


def test_z3_intersection_without_numbers():
    """Z3 proves ``during`` from ``starts during`` and ``ends during`` with no numbers."""
    solver = _z3()
    add_interval(solver, "morula")
    add_interval(solver, "cleavage")
    solver.add_fact(ai.StartsDuring("morula", "cleavage"))
    solver.add_fact(ai.EndsDuring("morula", "cleavage"))
    assert solver.prove(ai.During("morula", "cleavage")) is True


def test_z3_detects_inconsistency():
    """Z3 reports unsat for a zero-width interval and for a lineage that contradicts the windows."""
    solver = _z3()
    add_interval(solver, "TS27", 456, 456)
    assert solver.check().satisfiable is False

    solver = _z3()
    add_interval(solver, "neural_plate", 18, 22)
    add_interval(solver, "neural_tube", 16, 30)
    solver.add_fact(ai.DevelopsFrom("neural_tube", "neural_plate"))
    assert solver.check().satisfiable is False
