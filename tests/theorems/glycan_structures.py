"""
A reference library of N-glycan structures for :mod:`tests.theorems.glycan_biosynthesis`.

These are data, not theory: the same role played by a set of GlyTouCan accessions
or the structures identified in a glycomics run. Each glycan is written as a tree
of monosaccharides and flattened into ``Residue`` facts whose sites are path
addresses from the reducing end (see the module docstring of the theory).

The set covers the canonical mammalian pathway -- the high-mannose series Man9 to
Man5, the GnT-I and mannosidase II intermediates, the bi-, tri- and tetra-antennary
complex glycans, and their galactosylated, sialylated, core-fucosylated and
bisected forms. Two structures are deliberately included that the theory should
rule out as products, so that the axioms have something to fail on.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from tests.theorems.glycan_biosynthesis import Mono, ParentSite, Position, Residue, Site, Structure, StructureId
from typedlogic import FactMixin

ROOT_SITE: Site = "R"
"""Address of the reducing-end residue."""


@dataclass
class Node:
    """A residue and the residues hanging off it, keyed by linkage position."""

    mono: Mono
    children: Dict[Position, "Node"] = field(default_factory=dict)


def _n(mono: Mono, **children: Node) -> Node:
    """Build a residue; keyword arguments name child linkage positions as ``p<position>``."""
    return Node(mono, {int(name[1:]): child for name, child in children.items()})


def _man(**children: Node) -> Node:
    """Build a mannose residue."""
    return _n(Mono.MAN, **children)


def _glcnac(**children: Node) -> Node:
    """Build a GlcNAc residue."""
    return _n(Mono.GLCNAC, **children)


def _gal(**children: Node) -> Node:
    """Build a galactose residue."""
    return _n(Mono.GAL, **children)


def _sia() -> Node:
    """Build a terminal Neu5Ac residue."""
    return _n(Mono.NEU5AC)


def _core(*, fuc: bool = False, **arms: Node) -> Node:
    """Build the trimannosyl core GlcNAc2Man, optionally core-fucosylated; ``arms`` hang off the beta-mannose."""
    root = _glcnac(p4=_glcnac(p4=_man(**arms)))
    if fuc:
        root.children[6] = _n(Mono.FUC)
    return root


# The high-mannose series. Each step removes exactly one alpha1-2 mannose.
MAN9 = _core(p3=_man(p2=_man(p2=_man())), p6=_man(p3=_man(p2=_man()), p6=_man(p2=_man())))
MAN8 = _core(p3=_man(p2=_man()), p6=_man(p3=_man(p2=_man()), p6=_man(p2=_man())))
MAN7 = _core(p3=_man(), p6=_man(p3=_man(p2=_man()), p6=_man(p2=_man())))
MAN6 = _core(p3=_man(), p6=_man(p3=_man(), p6=_man(p2=_man())))
MAN5 = _core(p3=_man(), p6=_man(p3=_man(), p6=_man()))

# GnT-I product and the mannosidase II intermediates leading to the trimannosyl core.
GLCNAC_MAN5 = _core(p3=_man(p2=_glcnac()), p6=_man(p3=_man(), p6=_man()))
GLCNAC_MAN4 = _core(p3=_man(p2=_glcnac()), p6=_man(p6=_man()))
GLCNAC_MAN3 = _core(p3=_man(p2=_glcnac()), p6=_man())

# Negative control: mannosidase II matches the linkage of the alpha1-6 arm mannose itself,
# so only the rule forbidding removal of a core arm root keeps this off the network.
GLCNAC_MAN2 = _core(p3=_man(p2=_glcnac()))

# Complex biantennary glycans and their elaborations.
A2 = _core(p3=_man(p2=_glcnac()), p6=_man(p2=_glcnac()))
A2F = _core(fuc=True, p3=_man(p2=_glcnac()), p6=_man(p2=_glcnac()))
A2B = _core(p3=_man(p2=_glcnac()), p4=_glcnac(), p6=_man(p2=_glcnac()))
A2G1 = _core(p3=_man(p2=_glcnac(p4=_gal())), p6=_man(p2=_glcnac()))
A2G2 = _core(p3=_man(p2=_glcnac(p4=_gal())), p6=_man(p2=_glcnac(p4=_gal())))
A2G2S1 = _core(p3=_man(p2=_glcnac(p4=_gal(p6=_sia()))), p6=_man(p2=_glcnac(p4=_gal())))
A2G2S2 = _core(p3=_man(p2=_glcnac(p4=_gal(p6=_sia()))), p6=_man(p2=_glcnac(p4=_gal(p6=_sia()))))

# Tri- and tetra-antennary glycans from GnT-IV and GnT-V, and the bisected triantennary.
A3 = _core(p3=_man(p2=_glcnac(), p4=_glcnac()), p6=_man(p2=_glcnac()))
A3B = _core(p3=_man(p2=_glcnac(), p4=_glcnac()), p4=_glcnac(), p6=_man(p2=_glcnac()))
A4 = _core(p3=_man(p2=_glcnac(), p4=_glcnac()), p6=_man(p2=_glcnac(), p6=_glcnac()))

# Core fucosylation requires the GnT-I product, so MAN5F should never be produced
# even though FUT8 is active and the structure is otherwise one residue from MAN5.
MAN5F = _core(fuc=True, p3=_man(), p6=_man(p3=_man(), p6=_man()))
GLCNAC_MAN5F = _core(fuc=True, p3=_man(p2=_glcnac()), p6=_man(p3=_man(), p6=_man()))

LIBRARY: Dict[StructureId, Node] = {
    "Man9": MAN9,
    "Man8": MAN8,
    "Man7": MAN7,
    "Man6": MAN6,
    "Man5": MAN5,
    "Man5F": MAN5F,
    "GlcNAcMan5": GLCNAC_MAN5,
    "GlcNAcMan5F": GLCNAC_MAN5F,
    "GlcNAcMan4": GLCNAC_MAN4,
    "GlcNAcMan3": GLCNAC_MAN3,
    "GlcNAcMan2": GLCNAC_MAN2,
    "A2": A2,
    "A2F": A2F,
    "A2B": A2B,
    "A2G1": A2G1,
    "A2G2": A2G2,
    "A2G2S1": A2G2S1,
    "A2G2S2": A2G2S2,
    "A3": A3,
    "A3B": A3B,
    "A4": A4,
}
"""Every candidate structure, keyed by name."""

PRECURSOR: StructureId = "Man9"
"""The structure delivered to the Golgi by the ER."""


def _walk(node: Node, site: Site, residues: List[Tuple[Site, Mono]], links: List[Tuple[Site, Site, Position]]) -> None:
    """Flatten a residue tree into (site, mono) pairs and (parent, child, position) links."""
    residues.append((site, node.mono))
    for position, child in sorted(node.children.items()):
        child_site = f"{site}-{position}"
        links.append((site, child_site, position))
        _walk(child, child_site, residues, links)


def structure_facts() -> List[FactMixin]:
    """Return ``Structure``, ``Residue`` and ``ParentSite`` facts for the whole library."""
    facts: List[FactMixin] = []
    links: Dict[Tuple[Site, Site, Position], None] = {}
    for name, root in LIBRARY.items():
        residues: List[Tuple[Site, Mono]] = []
        structure_links: List[Tuple[Site, Site, Position]] = []
        _walk(root, ROOT_SITE, residues, structure_links)
        facts.append(Structure(structure=name))
        facts.extend(Residue(structure=name, site=site, mono=mono) for site, mono in residues)
        links.update({link: None for link in structure_links})
    facts.extend(ParentSite(parent=parent, child=child, position=position) for parent, child, position in links)
    return facts
