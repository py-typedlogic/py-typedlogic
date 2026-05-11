"""Synthetic biology design checks for the gallery notebook."""

# ruff: noqa: S101
#
# The theory is intentionally small, but it spans three practical layers:
# 1. Assembly structure checks for compatible Golden Gate-style overhangs.
# 2. GO-driven pathway reachability for engineered metabolic functions.
# 3. GO-CAM curation checks for causal edges between molecular functions.

from dataclasses import dataclass

from typedlogic import Fact, axiom


@dataclass(frozen=True)
class Part(Fact):
    """A DNA part in an ordered assembly."""

    name: str
    part_type: str
    five_oh: str
    three_oh: str
    position: int


@dataclass(frozen=True)
class CanLigate(Fact):
    """Two parts have compatible overhangs and can ligate."""

    upstream: str
    downstream: str


@dataclass(frozen=True)
class IntendedAdjacent(Fact):
    """Two parts are adjacent in the intended design order."""

    upstream: str
    downstream: str


@dataclass(frozen=True)
class MisligationRisk(Fact):
    """A compatible ligation exists outside the intended adjacency order."""

    upstream: str
    downstream: str


@axiom
def ligation_compatibility(
    n1: str,
    t1: str,
    fo1: str,
    to1: str,
    pos1: int,
    n2: str,
    t2: str,
    fo2: str,
    to2: str,
    pos2: int,
):
    """Derive ligation compatibility when the upstream 3' overhang matches the downstream 5' overhang."""
    if Part(n1, t1, fo1, to1, pos1) and Part(n2, t2, fo2, to2, pos2):
        if to1 == fo2 and n1 != n2:
            assert CanLigate(n1, n2)


@axiom
def intended_adjacency(
    n1: str,
    t1: str,
    fo1: str,
    to1: str,
    pos1: int,
    n2: str,
    t2: str,
    fo2: str,
    to2: str,
    pos2: int,
):
    """Derive intended adjacency from the declared part positions."""
    if Part(n1, t1, fo1, to1, pos1) and Part(n2, t2, fo2, to2, pos2):
        if pos2 == pos1 + 1:
            assert IntendedAdjacent(n1, n2)


@axiom
def misligation_detection(
    upstream: str,
    downstream: str,
    n1: str,
    t1: str,
    fo1: str,
    to1: str,
    pos1: int,
    n2: str,
    t2: str,
    fo2: str,
    to2: str,
    pos2: int,
):
    """Flag compatible ligations that skip over the intended next position."""
    if (
        CanLigate(upstream, downstream)
        and Part(n1, t1, fo1, to1, pos1)
        and Part(n2, t2, fo2, to2, pos2)
        and upstream == n1
        and downstream == n2
    ):
        if pos2 != pos1 + 1:
            assert MisligationRisk(upstream, downstream)


@dataclass(frozen=True)
class EncodesProtein(Fact):
    """A CDS part encodes a protein."""

    part: str
    protein: str


@dataclass(frozen=True)
class HasMolecularFunction(Fact):
    """A protein has a GO molecular function."""

    protein: str
    go_mf: str


@dataclass(frozen=True)
class FunctionCatalyzes(Fact):
    """A molecular function converts a substrate metabolite to a product metabolite."""

    go_mf: str
    substrate: str
    product: str


@dataclass(frozen=True)
class DesignContains(Fact):
    """A named design contains a part."""

    design: str
    part: str


@dataclass(frozen=True)
class AvailableMetabolite(Fact):
    """A metabolite is available to a design from the environment or an encoded function."""

    design: str
    metabolite: str


@dataclass(frozen=True)
class RequiredMetabolite(Fact):
    """A metabolite that the engineered cell needs for the design intent."""

    design: str
    metabolite: str


@axiom
def metabolite_produced_by_design(
    design: str,
    part: str,
    protein: str,
    go_mf: str,
    substrate: str,
    product: str,
):
    """Propagate metabolite availability through functions encoded by the design."""
    if (
        DesignContains(design, part)
        and EncodesProtein(part, protein)
        and HasMolecularFunction(protein, go_mf)
        and FunctionCatalyzes(go_mf, substrate, product)
        and AvailableMetabolite(design, substrate)
    ):
        assert AvailableMetabolite(design, product)


@dataclass(frozen=True)
class GOAspect(Fact):
    """The aspect of a GO term: molecular function, biological process, or cellular component."""

    go_term: str
    aspect: str


@dataclass(frozen=True)
class GOCAMIndividual(Fact):
    """An individual in a GO-CAM model instantiating a GO class."""

    iri: str
    go_class: str


@dataclass(frozen=True)
class CausalRelation(Fact):
    """A relation that should connect molecular function individuals in GO-CAM."""

    relation: str


@dataclass(frozen=True)
class CausalEdge(Fact):
    """A causal relation between two GO-CAM individuals."""

    upstream_iri: str
    downstream_iri: str
    relation: str


@dataclass(frozen=True)
class GOCAMViolation(Fact):
    """A derived GO-CAM curation rule violation."""

    individual: str
    rule: str


@axiom
def causal_edge_upstream_must_be_mf(
    up: str,
    down: str,
    rel: str,
    upstream_class: str,
    aspect: str,
):
    """Require the upstream node of a causal edge to instantiate a molecular function."""
    if (
        CausalEdge(up, down, rel)
        and CausalRelation(rel)
        and GOCAMIndividual(up, upstream_class)
        and GOAspect(upstream_class, aspect)
    ):
        if aspect != "MF":
            assert GOCAMViolation(up, "causal_upstream_not_MF")


@axiom
def causal_edge_downstream_must_be_mf(
    up: str,
    down: str,
    rel: str,
    downstream_class: str,
    aspect: str,
):
    """Require the downstream node of a causal edge to instantiate a molecular function."""
    if (
        CausalEdge(up, down, rel)
        and CausalRelation(rel)
        and GOCAMIndividual(down, downstream_class)
        and GOAspect(downstream_class, aspect)
    ):
        if aspect != "MF":
            assert GOCAMViolation(down, "causal_downstream_not_MF")
