"""
Tests for the N-glycan biosynthesis theory in :mod:`tests.theorems.glycan_biosynthesis`.

The theory is run under Clingo, whose closed-world semantics and stratified
negation match what the model needs: an enzyme is active unless a ``KnockedOut``
fact says otherwise, and reachability from the precursor is a least fixpoint.

Every expectation below is a published property of the mammalian N-glycosylation
pathway, so these double as a check that the axioms say what glycobiology says.
"""

from typing import Dict, FrozenSet, List, Sequence, Set, Tuple

import pytest

import tests.theorems.glycan_biosynthesis as gb
from tests.theorems.glycan_structures import LIBRARY, PRECURSOR, structure_facts
from typedlogic import Term
from typedlogic.integrations.solvers.clingo import ClingoSolver

Edge = Tuple[str, str, str]

WILD_TYPE_NETWORK: FrozenSet[Edge] = frozenset(
    {
        # Golgi mannosidase I trims the high-mannose series one alpha1-2 mannose at a time.
        ("Man9", "MAN1", "Man8"),
        ("Man8", "MAN1", "Man7"),
        ("Man7", "MAN1", "Man6"),
        ("Man6", "MAN1", "Man5"),
        # GnT-I opens the complex branch; mannosidase II then clears the alpha1-6 arm.
        ("Man5", "MGAT1", "GlcNAcMan5"),
        ("GlcNAcMan5", "MAN2", "GlcNAcMan4"),
        ("GlcNAcMan4", "MAN2", "GlcNAcMan3"),
        ("GlcNAcMan3", "MGAT2", "A2"),
        # Antenna elaboration.
        ("A2", "B4GALT1", "A2G1"),
        ("A2G1", "B4GALT1", "A2G2"),
        ("A2G2", "ST6GAL1", "A2G2S1"),
        ("A2G2S1", "ST6GAL1", "A2G2S2"),
        # Branching and capping.
        ("A2", "MGAT4", "A3"),
        ("A3", "MGAT5", "A4"),
        ("A2", "MGAT3", "A2B"),
        ("A3", "MGAT3", "A3B"),
        ("A2", "FUT8", "A2F"),
        ("GlcNAcMan5", "FUT8", "GlcNAcMan5F"),
        # Not on any route from the precursor, since Man5F itself is not producible,
        # but a valid edge in its own right.
        ("Man5F", "MGAT1", "GlcNAcMan5F"),
    }
)
"""The biosynthetic network the axioms should derive when every enzyme is active."""

KNOCKOUT_PHENOTYPES: Dict[gb.Enzyme, Set[str]] = {
    # Lec1: without GnT-I the cell cannot leave the high-mannose series at all.
    gb.Enzyme.MGAT1: {
        "GlcNAcMan5",
        "GlcNAcMan5F",
        "GlcNAcMan4",
        "GlcNAcMan3",
        "A2",
        "A2F",
        "A2B",
        "A2G1",
        "A2G2",
        "A2G2S1",
        "A2G2S2",
        "A3",
        "A3B",
        "A4",
    },
    # Losing mannosidase II strands the cell on hybrid glycans.
    gb.Enzyme.MAN2: {
        "GlcNAcMan4",
        "GlcNAcMan3",
        "A2",
        "A2F",
        "A2B",
        "A2G1",
        "A2G2",
        "A2G2S1",
        "A2G2S2",
        "A3",
        "A3B",
        "A4",
    },
    # CDG-IIa: the trimannosyl core is reached but no complex glycan is completed.
    gb.Enzyme.MGAT2: {
        "A2",
        "A2F",
        "A2B",
        "A2G1",
        "A2G2",
        "A2G2S1",
        "A2G2S2",
        "A3",
        "A3B",
        "A4",
    },
    gb.Enzyme.MGAT3: {"A2B", "A3B"},
    gb.Enzyme.MGAT4: {"A3", "A3B", "A4"},
    gb.Enzyme.MGAT5: {"A4"},
    gb.Enzyme.B4GALT1: {"A2G1", "A2G2", "A2G2S1", "A2G2S2"},
    gb.Enzyme.ST6GAL1: {"A2G2S1", "A2G2S2"},
    gb.Enzyme.FUT8: {"A2F", "GlcNAcMan5F"},
}
"""Structures each single knockout should remove from the producible set."""

KNOCKOUT_CASES: List[Tuple[gb.Enzyme, Set[str]]] = sorted(KNOCKOUT_PHENOTYPES.items(), key=lambda case: case[0].value)
"""The knockout expectations above, in a stable order for parametrization."""

UNPRODUCIBLE: Set[str] = {"Man5F", "GlcNAcMan2"}
"""Structures in the library that no route from the precursor reaches, for two different reasons."""


def solve(knockouts: Sequence[gb.Enzyme] = ()) -> List[Term]:
    """Derive all consequences of the theory for the given set of enzyme knockouts."""
    solver = ClingoSolver()
    solver.load(gb)
    for fact in structure_facts():
        solver.add(fact)
    solver.add(gb.Precursor(structure=PRECURSOR))
    for enzyme in knockouts:
        solver.add(gb.KnockedOut(enzyme=enzyme))
    return solver.model().ground_terms


def producible(knockouts: Sequence[gb.Enzyme] = ()) -> Set[str]:
    """Structures reachable from the precursor under the given knockouts."""
    return {t.values[0] for t in solve(knockouts) if t.predicate == "Producible"}


def network(knockouts: Sequence[gb.Enzyme] = ()) -> Set[Edge]:
    """Edges of the derived biosynthetic network."""
    return {(t.values[0], t.values[1], t.values[2]) for t in solve(knockouts) if t.predicate == "Converts"}


def test_network_is_derived_from_enzyme_specificities() -> None:
    """The whole pathway follows from substrate specificity plus structural comparison."""
    assert network() == WILD_TYPE_NETWORK


def test_precursor_reaches_the_rest_of_the_library() -> None:
    """Everything except the deliberately unreachable structures is producible from Man9."""
    assert producible() == set(LIBRARY) - UNPRODUCIBLE


def test_core_fucosylation_requires_the_gnt1_product() -> None:
    """FUT8 cannot fucosylate Man5, even though Man5F is one residue away from it."""
    assert ("Man5", "FUT8", "Man5F") not in network()
    assert ("GlcNAcMan5", "FUT8", "GlcNAcMan5F") in network()
    assert "Man5F" not in producible()


def test_bisecting_glcnac_blocks_further_branching() -> None:
    """GnT-III acts as a branch terminator: GnT-IV cannot act once the glycan is bisected."""
    edges = network()
    # A3B is one GlcNAc away from A2B, but the bisected acceptor shuts GnT-IV out.
    assert ("A2B", "MGAT4", "A3B") not in edges
    # Taking the branches in the other order works, so A3B is still producible.
    assert ("A3", "MGAT3", "A3B") in edges
    assert "A3B" in producible()


def test_mannosidase_ii_needs_gnt1_first() -> None:
    """Mannosidase II cannot trim the alpha1-6 arm of Man5 before GnT-I has acted."""
    trimmed_from_man5 = {edge for edge in network() if edge[0] == "Man5" and edge[1] == gb.Enzyme.MAN2.value}
    assert trimmed_from_man5 == set()


def test_gnt5_waits_for_mannosidase_ii() -> None:
    """GnT-V needs the site that the alpha1-6 arm mannose occupies until mannosidase II removes it."""
    assert "A4" not in producible([gb.Enzyme.MAN2])


def test_core_arm_mannoses_are_never_trimmed() -> None:
    """No mannosidase removes a mannose attached directly to the core beta-mannose."""
    # Mannosidase II's linkage specificity matches the alpha1-6 arm mannose of GlcNAcMan3,
    # so without the core-arm guard the network would run on down to GlcNAcMan2.
    assert {edge for edge in network() if edge[2] == "GlcNAcMan2"} == set()
    assert "GlcNAcMan2" not in producible()


@pytest.mark.parametrize("enzyme,lost", KNOCKOUT_CASES)
def test_knockout_phenotypes(enzyme: gb.Enzyme, lost: Set[str]) -> None:
    """Each single knockout removes exactly the structures that depend on that enzyme."""
    assert set(LIBRARY) - UNPRODUCIBLE - producible([enzyme]) == lost


def test_knockouts_are_monotone() -> None:
    """Removing an enzyme can only shrink what the cell can make."""
    wild_type = producible()
    for enzyme in KNOCKOUT_PHENOTYPES:
        assert producible([enzyme]) < wild_type
