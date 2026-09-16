"""
N-glycan biosynthesis as a declarative logic theory.

Systems glycobiology has a mature body of *rule-based* models of glycan
biosynthesis (Krambeck's KB2005/K2014, the Glycosylation Network Analysis
Toolbox, RING), but the rules are invariably embedded in imperative MATLAB or
Python code. This module states the same kind of model as axioms, so that
network construction, enzyme-knockout prediction and pathway reachability all
fall out of a single least-fixpoint computation rather than a bespoke graph
walker.

Structure encoding
------------------
A glycan is a rooted tree of monosaccharides. Every residue is addressed by the
path of linkage positions from the reducing end, so the reducing-end GlcNAc of
every N-glycan is ``R``, the second GlcNAc is ``R-4``, the core beta-mannose is
``R-4-4``, and the two core arms are ``R-4-4-3`` and ``R-4-4-6``. A site holds at
most one residue, because in a glycan tree the pair (parent residue, linkage
position) identifies a child uniquely. A structure is then simply the *set* of
its ``Residue`` facts, which makes structural comparison ordinary set reasoning:
one glycan extends another when it has every residue of the other plus exactly
one more.

What the axioms buy you
-----------------------
Facts about enzymes are stated once, as substrate specificities, and the
consequences are derived:

* ``Converts`` -- the biosynthetic network, derived by comparing structures
  rather than by generating them.
* ``Producible`` -- reachability from the ER precursor, under whichever enzymes
  are active. This is recursive.
* Knockouts -- negation as failure over ``KnockedOut``, so removing an enzyme
  silently removes every structure that depended on it. MGAT1 is the classic
  gateway: knock it out and the cell is stuck at Man5 (the Lec1 phenotype).
* Ordering constraints that rule-based codes usually hard-wire are here derived
  from structure. MGAT5 cannot act until MAN2 has vacated the site it needs;
  FUT8 and MAN2 require the GnT-I product; a bisecting GlcNAc placed by MGAT3
  blocks MAN2, MGAT2, MGAT4 and MGAT5 from acting on that structure at all.

The candidate structures themselves are supplied as data -- as they would be
from GlyTouCan or a glycomics experiment -- because deriving the *edges* of the
network needs no term invention, while generating new structures would.
"""

from dataclasses import dataclass
from enum import Enum

from typedlogic import FactMixin, axiom

Site = str
"""Path address of a residue: linkage positions from the reducing end, e.g. ``R-4-4-3``."""

StructureId = str
"""Name of a glycan structure."""

Position = int
"""A linkage position (2, 3, 4 or 6). 0 is reserved to mean 'the core beta-mannose itself'."""


class Mono(str, Enum):
    """Monosaccharides occurring in mammalian N-glycans."""

    # Values match member names: typedlogic resolves an enum constant in an axiom to the
    # member name, while a fact built at runtime carries the member value.
    GLCNAC = "GLCNAC"
    MAN = "MAN"
    GAL = "GAL"
    NEU5AC = "NEU5AC"
    FUC = "FUC"


class Enzyme(str, Enum):
    """Golgi glycosyltransferases and glycosidases acting on N-glycans."""

    MAN1 = "MAN1"  # Golgi alpha-1,2-mannosidase I
    MGAT1 = "MGAT1"  # GnT-I
    MAN2 = "MAN2"  # alpha-mannosidase II
    MGAT2 = "MGAT2"  # GnT-II
    MGAT3 = "MGAT3"  # GnT-III, bisecting GlcNAc
    MGAT4 = "MGAT4"  # GnT-IV
    MGAT5 = "MGAT5"  # GnT-V
    B4GALT1 = "B4GALT1"  # beta-1,4-galactosyltransferase
    ST6GAL1 = "ST6GAL1"  # alpha-2,6-sialyltransferase
    FUT8 = "FUT8"  # core alpha-1,6-fucosyltransferase


# --- Structural facts ---


@dataclass
class Structure(FactMixin):
    """A candidate glycan structure."""

    structure: StructureId


@dataclass
class Residue(FactMixin):
    """A monosaccharide occupying a site in a structure."""

    structure: StructureId
    site: Site
    mono: Mono


@dataclass
class ParentSite(FactMixin):
    """Site ``child`` hangs off site ``parent`` at linkage ``position``."""

    parent: Site
    child: Site
    position: Position


@dataclass
class Precursor(FactMixin):
    """The ER-derived structure entering the Golgi."""

    structure: StructureId


# --- Enzyme facts ---


@dataclass
class GlycoEnzyme(FactMixin):
    """An enzyme in the repertoire."""

    enzyme: Enzyme


@dataclass
class KnockedOut(FactMixin):
    """An enzyme removed from the repertoire."""

    enzyme: Enzyme


@dataclass
class Transferase(FactMixin):
    """A glycosyltransferase adding ``donor`` at ``position`` onto an ``acceptor`` residue."""

    enzyme: Enzyme
    acceptor: Mono
    position: Position
    donor: Mono


@dataclass
class Glycosidase(FactMixin):
    """An exoglycosidase removing a terminal ``target`` residue attached at ``position``."""

    enzyme: Enzyme
    target: Mono
    position: Position


@dataclass
class AcceptorArm(FactMixin):
    """Restricts an enzyme to residues on a given core arm (0 = the core beta-mannose itself)."""

    enzyme: Enzyme
    arm: Position


@dataclass
class ReducingEndOnly(FactMixin):
    """An enzyme acting only on the reducing-end residue."""

    enzyme: Enzyme


@dataclass
class RequiresAntennaGlcNAc(FactMixin):
    """An enzyme requiring the GnT-I product (a GlcNAc beta1-2 on the alpha1-3 arm)."""

    enzyme: Enzyme


@dataclass
class BisectSensitive(FactMixin):
    """An enzyme that cannot act on a structure carrying a bisecting GlcNAc."""

    enzyme: Enzyme


# --- Derived predicates ---


@dataclass
class ActiveEnzyme(FactMixin):
    """An enzyme present and not knocked out."""

    enzyme: Enzyme


@dataclass
class Occupied(FactMixin):
    """Some residue occupies this site in this structure."""

    structure: StructureId
    site: Site


@dataclass
class HasChild(FactMixin):
    """A residue that carries at least one child residue."""

    structure: StructureId
    site: Site


@dataclass
class Terminal(FactMixin):
    """A residue with no children: the only kind an exoglycosidase can remove."""

    structure: StructureId
    site: Site


@dataclass
class HasParent(FactMixin):
    """A residue that hangs off another residue of the same structure."""

    structure: StructureId
    site: Site


@dataclass
class ReducingEnd(FactMixin):
    """The root residue of a structure."""

    structure: StructureId
    site: Site


@dataclass
class CoreMan(FactMixin):
    """The core beta-mannose: a mannose attached beta1-4 to a GlcNAc."""

    structure: StructureId
    site: Site


@dataclass
class ArmRoot(FactMixin):
    """A residue attached directly to the core beta-mannose."""

    structure: StructureId
    site: Site


@dataclass
class OnArm(FactMixin):
    """A residue on the core arm reached by leaving the beta-mannose at ``arm``."""

    structure: StructureId
    site: Site
    arm: Position


@dataclass
class Bisected(FactMixin):
    """A structure carrying a bisecting GlcNAc on the core beta-mannose."""

    structure: StructureId


@dataclass
class HasAntennaGlcNAc(FactMixin):
    """A structure carrying the GnT-I product."""

    structure: StructureId


@dataclass
class NotSubset(FactMixin):
    """Some residue of ``sub`` is absent from ``sup``."""

    sub: StructureId
    sup: StructureId


@dataclass
class Subset(FactMixin):
    """Every residue of ``sub`` is present in ``sup``."""

    sub: StructureId
    sup: StructureId


@dataclass
class NewResidue(FactMixin):
    """A residue present in ``sup`` but absent from ``sub``."""

    sub: StructureId
    sup: StructureId
    site: Site
    mono: Mono


@dataclass
class OtherNewResidue(FactMixin):
    """``sup`` has a residue absent from ``sub`` at a site other than ``site``."""

    sub: StructureId
    sup: StructureId
    site: Site


@dataclass
class Extends(FactMixin):
    """``sup`` is exactly ``sub`` plus one residue: ``mono`` at ``site``."""

    sub: StructureId
    sup: StructureId
    site: Site
    mono: Mono


@dataclass
class ArmOk(FactMixin):
    """``site`` lies on one of the arms this enzyme accepts."""

    enzyme: Enzyme
    structure: StructureId
    site: Site


@dataclass
class WrongArm(FactMixin):
    """An arm-restricted enzyme paired with a site on none of its arms."""

    enzyme: Enzyme
    structure: StructureId
    site: Site


@dataclass
class WrongEnd(FactMixin):
    """A reducing-end-only enzyme paired with a site that is not the reducing end."""

    enzyme: Enzyme
    structure: StructureId
    site: Site


@dataclass
class BlockedOn(FactMixin):
    """An enzyme that cannot act on the given structure at all."""

    enzyme: Enzyme
    structure: StructureId


@dataclass
class CanTransfer(FactMixin):
    """An active transferase turns ``source`` into ``target`` by adding one residue."""

    source: StructureId
    enzyme: Enzyme
    target: StructureId


@dataclass
class CanTrim(FactMixin):
    """An active glycosidase turns ``source`` into ``target`` by removing one terminal residue."""

    source: StructureId
    enzyme: Enzyme
    target: StructureId


@dataclass
class Converts(FactMixin):
    """An edge of the biosynthetic network."""

    source: StructureId
    enzyme: Enzyme
    target: StructureId


@dataclass
class Producible(FactMixin):
    """A structure reachable from the precursor under the active enzymes."""

    structure: StructureId


# --- Axioms: enzyme repertoire ---


@axiom
def enzyme_repertoire():
    """Declare the enzymes under consideration."""
    assert GlycoEnzyme(enzyme=Enzyme.MAN1)
    assert GlycoEnzyme(enzyme=Enzyme.MGAT1)
    assert GlycoEnzyme(enzyme=Enzyme.MAN2)
    assert GlycoEnzyme(enzyme=Enzyme.MGAT2)
    assert GlycoEnzyme(enzyme=Enzyme.MGAT3)
    assert GlycoEnzyme(enzyme=Enzyme.MGAT4)
    assert GlycoEnzyme(enzyme=Enzyme.MGAT5)
    assert GlycoEnzyme(enzyme=Enzyme.B4GALT1)
    assert GlycoEnzyme(enzyme=Enzyme.ST6GAL1)
    assert GlycoEnzyme(enzyme=Enzyme.FUT8)


@axiom
def transferase_specificity():
    """Donor, acceptor and linkage position for each glycosyltransferase."""
    # GnT-I and GnT-II both add GlcNAc beta1-2 to a mannose; only the arm tells them apart.
    assert Transferase(enzyme=Enzyme.MGAT1, acceptor=Mono.MAN, position=2, donor=Mono.GLCNAC)
    assert Transferase(enzyme=Enzyme.MGAT2, acceptor=Mono.MAN, position=2, donor=Mono.GLCNAC)
    # GnT-III bisects the core mannose; GnT-IV uses the same linkage on the alpha1-3 arm.
    assert Transferase(enzyme=Enzyme.MGAT3, acceptor=Mono.MAN, position=4, donor=Mono.GLCNAC)
    assert Transferase(enzyme=Enzyme.MGAT4, acceptor=Mono.MAN, position=4, donor=Mono.GLCNAC)
    assert Transferase(enzyme=Enzyme.MGAT5, acceptor=Mono.MAN, position=6, donor=Mono.GLCNAC)
    assert Transferase(enzyme=Enzyme.B4GALT1, acceptor=Mono.GLCNAC, position=4, donor=Mono.GAL)
    assert Transferase(enzyme=Enzyme.ST6GAL1, acceptor=Mono.GAL, position=6, donor=Mono.NEU5AC)
    assert Transferase(enzyme=Enzyme.FUT8, acceptor=Mono.GLCNAC, position=6, donor=Mono.FUC)


@axiom
def glycosidase_specificity():
    """Residues each exoglycosidase removes."""
    # Mannosidase I trims the alpha1-2 mannoses of the high-mannose arms.
    assert Glycosidase(enzyme=Enzyme.MAN1, target=Mono.MAN, position=2)
    # Mannosidase II clears the alpha1-3 and alpha1-6 mannoses from the alpha1-6 arm.
    assert Glycosidase(enzyme=Enzyme.MAN2, target=Mono.MAN, position=3)
    assert Glycosidase(enzyme=Enzyme.MAN2, target=Mono.MAN, position=6)


@axiom
def enzyme_context_constraints():
    """Arm, position and prior-action constraints that specificity alone does not capture."""
    assert AcceptorArm(enzyme=Enzyme.MAN1, arm=3)
    assert AcceptorArm(enzyme=Enzyme.MAN1, arm=6)
    assert AcceptorArm(enzyme=Enzyme.MAN2, arm=6)
    assert AcceptorArm(enzyme=Enzyme.MGAT1, arm=3)
    assert AcceptorArm(enzyme=Enzyme.MGAT2, arm=6)
    assert AcceptorArm(enzyme=Enzyme.MGAT3, arm=0)  # the core beta-mannose itself
    assert AcceptorArm(enzyme=Enzyme.MGAT4, arm=3)
    assert AcceptorArm(enzyme=Enzyme.MGAT5, arm=6)
    # Galactose and sialic acid go onto antennae, never onto the bisecting GlcNAc.
    assert AcceptorArm(enzyme=Enzyme.B4GALT1, arm=3)
    assert AcceptorArm(enzyme=Enzyme.B4GALT1, arm=6)
    assert AcceptorArm(enzyme=Enzyme.ST6GAL1, arm=3)
    assert AcceptorArm(enzyme=Enzyme.ST6GAL1, arm=6)
    # Core fucosylation targets the reducing-end GlcNAc only.
    assert ReducingEndOnly(enzyme=Enzyme.FUT8)
    # These enzymes act only after GnT-I has installed the alpha1-3 arm GlcNAc.
    assert RequiresAntennaGlcNAc(enzyme=Enzyme.MAN2)
    assert RequiresAntennaGlcNAc(enzyme=Enzyme.MGAT2)
    assert RequiresAntennaGlcNAc(enzyme=Enzyme.MGAT3)
    assert RequiresAntennaGlcNAc(enzyme=Enzyme.MGAT4)
    assert RequiresAntennaGlcNAc(enzyme=Enzyme.MGAT5)
    assert RequiresAntennaGlcNAc(enzyme=Enzyme.FUT8)
    # A bisecting GlcNAc shuts these down, which is why GnT-III acts as a branch terminator.
    assert BisectSensitive(enzyme=Enzyme.MAN2)
    assert BisectSensitive(enzyme=Enzyme.MGAT2)
    assert BisectSensitive(enzyme=Enzyme.MGAT4)
    assert BisectSensitive(enzyme=Enzyme.MGAT5)


@axiom
def enzyme_activity(e: Enzyme):
    """Activate every enzyme that has not been knocked out."""
    if GlycoEnzyme(enzyme=e) and -KnockedOut(enzyme=e):
        assert ActiveEnzyme(enzyme=e)


# --- Axioms: structural properties ---


@axiom
def site_occupancy(g: StructureId, s: Site, m: Mono):
    """Mark a site occupied when any residue sits there."""
    if Residue(structure=g, site=s, mono=m):
        assert Occupied(structure=g, site=s)


@axiom
def child_and_parent(g: StructureId, s: Site, c: Site, p: Position):
    """Relate a residue to its children and its parent within one structure."""
    if Occupied(structure=g, site=s) and ParentSite(parent=s, child=c, position=p) and Occupied(structure=g, site=c):
        assert HasChild(structure=g, site=s)
        assert HasParent(structure=g, site=c)


@axiom
def terminal_and_root(g: StructureId, s: Site):
    """Residues with no children are terminal; the residue with no parent is the reducing end."""
    if Occupied(structure=g, site=s) and -HasChild(structure=g, site=s):
        assert Terminal(structure=g, site=s)
    if Occupied(structure=g, site=s) and -HasParent(structure=g, site=s):
        assert ReducingEnd(structure=g, site=s)


@axiom
def core_mannose(g: StructureId, s: Site, p: Site):
    """Identify the core beta-mannose: the mannose attached beta1-4 to a GlcNAc."""
    if (
        Residue(structure=g, site=s, mono=Mono.MAN)
        and ParentSite(parent=p, child=s, position=4)
        and Residue(structure=g, site=p, mono=Mono.GLCNAC)
    ):
        assert CoreMan(structure=g, site=s)


@axiom
def arm_membership(g: StructureId, core: Site, s: Site, p: Site, a: Position, pos: Position):
    """Assign every non-core residue to the core arm it descends from."""
    # The residues hanging directly off the core mannose root their arms.
    if (
        CoreMan(structure=g, site=core)
        and ParentSite(parent=core, child=s, position=a)
        and Occupied(structure=g, site=s)
    ):
        assert OnArm(structure=g, site=s, arm=a)
        assert ArmRoot(structure=g, site=s)
    # Everything below inherits the arm. The guard stops arm 0 leaking down from the core.
    if (
        OnArm(structure=g, site=p, arm=a)
        and -CoreMan(structure=g, site=p)
        and ParentSite(parent=p, child=s, position=pos)
        and Occupied(structure=g, site=s)
    ):
        assert OnArm(structure=g, site=s, arm=a)
    # The core mannose is its own arm, so GnT-III can be given an arm constraint like the rest.
    if CoreMan(structure=g, site=core):
        assert OnArm(structure=g, site=core, arm=0)


@axiom
def bisecting_glcnac(g: StructureId, c: Site, s: Site):
    """Detect the bisecting GlcNAc: a GlcNAc attached beta1-4 to the core mannose."""
    if (
        CoreMan(structure=g, site=c)
        and ParentSite(parent=c, child=s, position=4)
        and Residue(structure=g, site=s, mono=Mono.GLCNAC)
    ):
        assert Bisected(structure=g)


@axiom
def antenna_glcnac(g: StructureId, c: Site, a: Site, s: Site):
    """Detect the GnT-I product: GlcNAc beta1-2 on the alpha1-3 arm mannose."""
    if (
        CoreMan(structure=g, site=c)
        and ParentSite(parent=c, child=a, position=3)
        and Residue(structure=g, site=a, mono=Mono.MAN)
        and ParentSite(parent=a, child=s, position=2)
        and Residue(structure=g, site=s, mono=Mono.GLCNAC)
    ):
        assert HasAntennaGlcNAc(structure=g)


# --- Axioms: structural comparison ---


@axiom
def subset_of(g1: StructureId, g2: StructureId, s: Site, m: Mono):
    """One structure is a subset of another when it contributes no residue the other lacks."""
    if Residue(structure=g1, site=s, mono=m) and Structure(structure=g2) and -Residue(structure=g2, site=s, mono=m):
        assert NotSubset(sub=g1, sup=g2)
    if Structure(structure=g1) and Structure(structure=g2) and -NotSubset(sub=g1, sup=g2):
        assert Subset(sub=g1, sup=g2)


@axiom
def one_residue_difference(g1: StructureId, g2: StructureId, s: Site, s2: Site, m: Mono, m2: Mono):
    """``g2`` extends ``g1`` when it is a superset differing by exactly one residue."""
    if Structure(structure=g1) and Residue(structure=g2, site=s, mono=m) and -Residue(structure=g1, site=s, mono=m):
        assert NewResidue(sub=g1, sup=g2, site=s, mono=m)
    if NewResidue(sub=g1, sup=g2, site=s2, mono=m2) and Occupied(structure=g2, site=s) and s2 != s:
        assert OtherNewResidue(sub=g1, sup=g2, site=s)
    if (
        Subset(sub=g1, sup=g2)
        and Residue(structure=g2, site=s, mono=m)
        and -Occupied(structure=g1, site=s)
        and -OtherNewResidue(sub=g1, sup=g2, site=s)
    ):
        assert Extends(sub=g1, sup=g2, site=s, mono=m)


# --- Axioms: enzyme action ---


@axiom
def arm_and_end_constraints(e: Enzyme, g: StructureId, s: Site, a: Position):
    """Reject the sites that lie outside an arm-restricted or reducing-end-restricted enzyme's remit."""
    # An enzyme may accept several arms, so the site is wrong only if it is on none of them.
    if AcceptorArm(enzyme=e, arm=a) and OnArm(structure=g, site=s, arm=a):
        assert ArmOk(enzyme=e, structure=g, site=s)
    if AcceptorArm(enzyme=e, arm=a) and Occupied(structure=g, site=s) and -ArmOk(enzyme=e, structure=g, site=s):
        assert WrongArm(enzyme=e, structure=g, site=s)
    if ReducingEndOnly(enzyme=e) and Occupied(structure=g, site=s) and -ReducingEnd(structure=g, site=s):
        assert WrongEnd(enzyme=e, structure=g, site=s)


@axiom
def enzyme_blocking(e: Enzyme, g: StructureId):
    """Structure-level conditions that stop an enzyme acting at all."""
    if BisectSensitive(enzyme=e) and Bisected(structure=g):
        assert BlockedOn(enzyme=e, structure=g)
    if RequiresAntennaGlcNAc(enzyme=e) and Structure(structure=g) and -HasAntennaGlcNAc(structure=g):
        assert BlockedOn(enzyme=e, structure=g)


@axiom
def transfer(g1: StructureId, g2: StructureId, e: Enzyme, s: Site, p: Site, pos: Position, m: Mono, acc: Mono):
    """Fire a transferase when the new residue matches its specificity and its structural context."""
    if (
        Extends(sub=g1, sup=g2, site=s, mono=m)
        and ParentSite(parent=p, child=s, position=pos)
        and Residue(structure=g1, site=p, mono=acc)
        and Transferase(enzyme=e, acceptor=acc, position=pos, donor=m)
        and ActiveEnzyme(enzyme=e)
        and -WrongArm(enzyme=e, structure=g1, site=p)
        and -WrongEnd(enzyme=e, structure=g1, site=p)
    ):
        assert CanTransfer(source=g1, enzyme=e, target=g2)


@axiom
def trim(g1: StructureId, g2: StructureId, e: Enzyme, s: Site, p: Site, pos: Position, m: Mono):
    """Fire a glycosidase on a terminal residue that is not a core arm root."""
    if (
        Extends(sub=g2, sup=g1, site=s, mono=m)
        and Terminal(structure=g1, site=s)
        and -ArmRoot(structure=g1, site=s)
        and ParentSite(parent=p, child=s, position=pos)
        and Glycosidase(enzyme=e, target=m, position=pos)
        and ActiveEnzyme(enzyme=e)
        and -WrongArm(enzyme=e, structure=g1, site=s)
    ):
        assert CanTrim(source=g1, enzyme=e, target=g2)


@axiom
def network(g1: StructureId, g2: StructureId, e: Enzyme):
    """Collect every unblocked enzyme action into the biosynthetic network."""
    if CanTransfer(source=g1, enzyme=e, target=g2) and -BlockedOn(enzyme=e, structure=g1):
        assert Converts(source=g1, enzyme=e, target=g2)
    if CanTrim(source=g1, enzyme=e, target=g2) and -BlockedOn(enzyme=e, structure=g1):
        assert Converts(source=g1, enzyme=e, target=g2)


@axiom
def producibility(g1: StructureId, g2: StructureId, e: Enzyme):
    """Reachability from the ER precursor: the recursive core of the model."""
    if Precursor(structure=g1):
        assert Producible(structure=g1)
    if Producible(structure=g1) and Converts(source=g1, enzyme=e, target=g2):
        assert Producible(structure=g2)
