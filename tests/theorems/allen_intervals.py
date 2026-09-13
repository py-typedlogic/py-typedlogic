"""
Allen's interval calculus over developmental stages, with numeric anchoring.

This theory shows how qualitative temporal reasoning (Allen 1983) and numeric
endpoint data can share one vocabulary. It follows the *junction-based* formulation
of Mungall (2014, "Formalization of Genome Interval Relations"): an interval is
related to two named **points** (its start and end), every interval relation is a
conjunction of order constraints between those points, and a point may or may not
carry a numeric position.

Three layers, one vocabulary:

1. **Points.** ``Before`` is a strict order, ``SamePoint`` an equivalence that
   substitutes into ``Before`` and ``At``. This is the point algebra, which is
   tractable, unlike full Allen.
2. **Numeric anchoring.** Where two points both have an ``At`` position, their
   order is decided by integer comparison. A point with no position is simply
   unconstrained by this layer.
3. **Interval relations.** The 13 Allen atoms and the compound relations used by the
   OBO Relation Ontology (``starts during``, ``ends after``, ...) are each defined
   *both ways* as an endpoint conjunction. Asserting a relation adds point
   constraints; point constraints yield relations.

Because relations are defined through points, the composition table is never
asserted: ``x meets y`` and ``y meets z`` give ``end(x) = start(y) < end(y) = start(z)``,
hence ``x precedes z``. Likewise, two assertions about the same pair intersect for
free: ``starts during`` and ``ends during`` together yield ``during``. Neither
inference is available to OWL property chains.

Positions are integers (the Datalog backends compare integers natively; ASP has no
floats). Choose the unit per frame, e.g. hours post coitum for mouse Theiler stages.

The proposed RO axiom ``develops_from ⊑ starts_after`` is included, so that a
``DevelopsFrom`` assertion whose existence windows contradict it makes the theory
unsatisfiable.

References:
- Allen, J.F. (1983). Maintaining Knowledge about Temporal Intervals. CACM 26(11).
- Mungall, C.J. (2014). Formalization of Genome Interval Relations. bioRxiv 10.1101/006650.
- Osumi-Sutherland, D. (2026). A composition-closed Allen extension for RO.
  https://github.com/dosumis/dev_reasoning_experiments

"""

from dataclasses import dataclass

from typedlogic import FactMixin, axiom

Interval = str
Point = str
Position = int


# ---------------------------------------------------------------------------
# Points (junctions)
# ---------------------------------------------------------------------------


@dataclass
class HasStart(FactMixin):
    """Links an interval to the named point at which it starts."""

    interval: Interval
    point: Point


@dataclass
class HasEnd(FactMixin):
    """Links an interval to the named point at which it ends."""

    interval: Interval
    point: Point


@dataclass
class At(FactMixin):
    """Numeric position of a point, as an integer in the unit of the reference frame."""

    point: Point
    position: Position


@dataclass
class Before(FactMixin):
    """Strict order on points: ``point`` is earlier than ``other``."""

    point: Point
    other: Point


@dataclass
class SamePoint(FactMixin):
    """Two names for the same point."""

    point: Point
    other: Point


# ---------------------------------------------------------------------------
# The 13 Allen atoms. ``x R y`` with x as the first argument.
# ---------------------------------------------------------------------------


@dataclass
class Precedes(FactMixin):
    """Allen ``p``: end(x) < start(y). RO has no term for this ("strictly precedes")."""

    x: Interval
    y: Interval


@dataclass
class Meets(FactMixin):
    """Allen ``m``: end(x) = start(y). RO:0002090 immediately precedes."""

    x: Interval
    y: Interval


@dataclass
class Overlaps(FactMixin):
    """Allen ``o``: start(x) < start(y) < end(x) < end(y). Asymmetric, unlike colloquial "overlaps"."""

    x: Interval
    y: Interval


@dataclass
class FinishedBy(FactMixin):
    """Allen ``F``: start(x) < start(y), end(x) = end(y)."""

    x: Interval
    y: Interval


@dataclass
class Contains(FactMixin):
    """Allen ``D``: start(x) < start(y), end(y) < end(x). RO:0002085 encompasses."""

    x: Interval
    y: Interval


@dataclass
class Starts(FactMixin):
    """Allen ``s``: start(x) = start(y), end(x) < end(y)."""

    x: Interval
    y: Interval


@dataclass
class Equals(FactMixin):
    """Allen ``e``: same start and same end."""

    x: Interval
    y: Interval


@dataclass
class StartedBy(FactMixin):
    """Allen ``S``: start(x) = start(y), end(y) < end(x)."""

    x: Interval
    y: Interval


@dataclass
class During(FactMixin):
    """Allen ``d``: start(y) < start(x), end(x) < end(y). RO:0002092 happens during."""

    x: Interval
    y: Interval


@dataclass
class Finishes(FactMixin):
    """Allen ``f``: start(y) < start(x), end(x) = end(y)."""

    x: Interval
    y: Interval


@dataclass
class OverlappedBy(FactMixin):
    """Allen ``O``: start(y) < start(x) < end(y) < end(x)."""

    x: Interval
    y: Interval


@dataclass
class MetBy(FactMixin):
    """Allen ``M``: start(x) = end(y). RO:0002087 immediately preceded by."""

    x: Interval
    y: Interval


@dataclass
class PrecededBy(FactMixin):
    """Allen ``P``: end(y) < start(x). RO has no term for this ("strictly preceded by")."""

    x: Interval
    y: Interval


# ---------------------------------------------------------------------------
# Compound relations, named as in RO. Each is a single endpoint invariant shared
# by all of its Allen disjuncts.
# ---------------------------------------------------------------------------


@dataclass
class StartsDuring(FactMixin):
    """Allen ``dfO``: start(y) < start(x) < end(y). RO:0002091."""

    x: Interval
    y: Interval


@dataclass
class EndsDuring(FactMixin):
    """Allen ``osd``: start(y) < end(x) < end(y). RO:0002093."""

    x: Interval
    y: Interval


@dataclass
class StartsBefore(FactMixin):
    """Allen ``pmoFD``: start(x) < start(y). RO:0002089."""

    x: Interval
    y: Interval


@dataclass
class StartsAfter(FactMixin):
    """Allen ``dfOMP``: start(y) < start(x). Not in RO; needed for ``develops_from``."""

    x: Interval
    y: Interval


@dataclass
class EndsBefore(FactMixin):
    """Allen ``pmosd``: end(x) < end(y)."""

    x: Interval
    y: Interval


@dataclass
class EndsAfter(FactMixin):
    """Allen ``DSOMP``: end(y) < end(x). RO:0002086."""

    x: Interval
    y: Interval


@dataclass
class StartsWith(FactMixin):
    """Allen ``seS``: start(x) = start(y)."""

    x: Interval
    y: Interval


@dataclass
class EndsWith(FactMixin):
    """Allen ``Fef``: end(x) = end(y)."""

    x: Interval
    y: Interval


@dataclass
class TemporallyOverlaps(FactMixin):
    """Allen ``oFDseSdfO``: start(x) < end(y) and start(y) < end(x). Symmetric."""

    x: Interval
    y: Interval


@dataclass
class DevelopsFrom(FactMixin):
    """RO:0002202. x arises from y; y need not cease when x appears, but y begins first."""

    x: Interval
    y: Interval


# ---------------------------------------------------------------------------
# Point algebra
# ---------------------------------------------------------------------------


@axiom
def point_order(p: Point, q: Point, r: Point):
    """``Before`` is a strict order: transitive and asymmetric."""
    assert (Before(p, q) & Before(q, r)) >> Before(p, r)
    assert ~(Before(p, q) & Before(q, p))


@axiom
def point_identity(p: Point, q: Point, r: Point, t: Position):
    """``SamePoint`` is an equivalence that substitutes into ``Before`` and ``At``."""
    assert SamePoint(p, q) >> SamePoint(q, p)
    assert (SamePoint(p, q) & SamePoint(q, r)) >> SamePoint(p, r)
    assert (SamePoint(p, q) & Before(q, r)) >> Before(p, r)
    assert (SamePoint(p, q) & Before(r, q)) >> Before(r, p)
    assert (SamePoint(p, q) & At(q, t)) >> At(p, t)
    assert ~(SamePoint(p, q) & Before(p, q))


@axiom
def point_reflexivity(i: Interval, p: Point):
    """Every endpoint is the same point as itself."""
    assert HasStart(i, p) >> SamePoint(p, p)
    assert HasEnd(i, p) >> SamePoint(p, p)


@axiom
def proper_interval(i: Interval, s: Point, e: Point):
    """Intervals are proper: the start is strictly before the end. Zero-width intervals are inconsistent."""
    assert (HasStart(i, s) & HasEnd(i, e)) >> Before(s, e)


# ---------------------------------------------------------------------------
# Numeric anchoring
# ---------------------------------------------------------------------------


@axiom
def numeric_anchoring(p: Point, q: Point, a: Position, b: Position):
    """Where both positions are known, point order is decided by comparing the numbers."""
    assert (At(p, a) & At(q, b) & (a < b)) >> Before(p, q)
    assert (At(p, a) & At(q, a)) >> SamePoint(p, q)


# ---------------------------------------------------------------------------
# Allen atoms as endpoint conjunctions (both directions)
# ---------------------------------------------------------------------------


@axiom
def atoms_from_endpoints(x: Interval, y: Interval, sx: Point, ex: Point, sy: Point, ey: Point):
    """Point constraints yield the (unique) Allen atom between two intervals."""
    if HasStart(x, sx) & HasEnd(x, ex) & HasStart(y, sy) & HasEnd(y, ey):
        assert Before(ex, sy) >> Precedes(x, y)
        assert SamePoint(ex, sy) >> Meets(x, y)
        assert (Before(sx, sy) & Before(sy, ex) & Before(ex, ey)) >> Overlaps(x, y)
        assert (Before(sx, sy) & SamePoint(ex, ey)) >> FinishedBy(x, y)
        assert (Before(sx, sy) & Before(ey, ex)) >> Contains(x, y)
        assert (SamePoint(sx, sy) & Before(ex, ey)) >> Starts(x, y)
        assert (SamePoint(sx, sy) & SamePoint(ex, ey)) >> Equals(x, y)
        assert (SamePoint(sx, sy) & Before(ey, ex)) >> StartedBy(x, y)
        assert (Before(sy, sx) & Before(ex, ey)) >> During(x, y)
        assert (Before(sy, sx) & SamePoint(ex, ey)) >> Finishes(x, y)
        assert (Before(sy, sx) & Before(sx, ey) & Before(ey, ex)) >> OverlappedBy(x, y)
        assert SamePoint(sx, ey) >> MetBy(x, y)
        assert Before(ey, sx) >> PrecededBy(x, y)


@axiom
def endpoints_from_atoms(x: Interval, y: Interval, sx: Point, ex: Point, sy: Point, ey: Point):
    """Constrain the endpoints from an asserted Allen atom."""
    if HasStart(x, sx) & HasEnd(x, ex) & HasStart(y, sy) & HasEnd(y, ey):
        assert Precedes(x, y) >> Before(ex, sy)
        assert Meets(x, y) >> SamePoint(ex, sy)
        assert Overlaps(x, y) >> (Before(sx, sy) & Before(sy, ex) & Before(ex, ey))
        assert FinishedBy(x, y) >> (Before(sx, sy) & SamePoint(ex, ey))
        assert Contains(x, y) >> (Before(sx, sy) & Before(ey, ex))
        assert Starts(x, y) >> (SamePoint(sx, sy) & Before(ex, ey))
        assert Equals(x, y) >> (SamePoint(sx, sy) & SamePoint(ex, ey))
        assert StartedBy(x, y) >> (SamePoint(sx, sy) & Before(ey, ex))
        assert During(x, y) >> (Before(sy, sx) & Before(ex, ey))
        assert Finishes(x, y) >> (Before(sy, sx) & SamePoint(ex, ey))
        assert OverlappedBy(x, y) >> (Before(sy, sx) & Before(sx, ey) & Before(ey, ex))
        assert MetBy(x, y) >> SamePoint(sx, ey)
        assert PrecededBy(x, y) >> Before(ey, sx)


# ---------------------------------------------------------------------------
# Compound (RO) relations as endpoint invariants (both directions)
# ---------------------------------------------------------------------------


@axiom
def compounds_from_endpoints(x: Interval, y: Interval, sx: Point, ex: Point, sy: Point, ey: Point):
    """Point constraints yield the RO compound relations."""
    if HasStart(x, sx) & HasEnd(x, ex) & HasStart(y, sy) & HasEnd(y, ey):
        assert (Before(sy, sx) & Before(sx, ey)) >> StartsDuring(x, y)
        assert (Before(sy, ex) & Before(ex, ey)) >> EndsDuring(x, y)
        assert Before(sx, sy) >> StartsBefore(x, y)
        assert Before(sy, sx) >> StartsAfter(x, y)
        assert Before(ex, ey) >> EndsBefore(x, y)
        assert Before(ey, ex) >> EndsAfter(x, y)
        assert SamePoint(sx, sy) >> StartsWith(x, y)
        assert SamePoint(ex, ey) >> EndsWith(x, y)
        assert (Before(sx, ey) & Before(sy, ex)) >> TemporallyOverlaps(x, y)


@axiom
def endpoints_from_compounds(x: Interval, y: Interval, sx: Point, ex: Point, sy: Point, ey: Point):
    """Constrain the endpoints from an asserted compound relation."""
    if HasStart(x, sx) & HasEnd(x, ex) & HasStart(y, sy) & HasEnd(y, ey):
        assert StartsDuring(x, y) >> (Before(sy, sx) & Before(sx, ey))
        assert EndsDuring(x, y) >> (Before(sy, ex) & Before(ex, ey))
        assert StartsBefore(x, y) >> Before(sx, sy)
        assert StartsAfter(x, y) >> Before(sy, sx)
        assert EndsBefore(x, y) >> Before(ex, ey)
        assert EndsAfter(x, y) >> Before(ey, ex)
        assert StartsWith(x, y) >> SamePoint(sx, sy)
        assert EndsWith(x, y) >> SamePoint(ex, ey)
        assert TemporallyOverlaps(x, y) >> (Before(sx, ey) & Before(sy, ex))


# ---------------------------------------------------------------------------
# Developmental lineage
# ---------------------------------------------------------------------------


@axiom
def develops_from(x: Interval, y: Interval, z: Interval):
    """Proposed RO axiom: ``develops_from ⊑ starts_after``. Lineage is transitive."""
    assert DevelopsFrom(x, y) >> StartsAfter(x, y)
    assert (DevelopsFrom(x, y) & DevelopsFrom(y, z)) >> DevelopsFrom(x, z)
