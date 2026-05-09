"""
OWLStar predicates and inference rules.

The rules in this module are intentionally Horn-friendly. They expose positive
consequences such as derived ``EdgeAllSome`` and ``EdgeAllNone`` facts. Solvers
that preserve negation or constraints can additionally use the ``EdgeAllSome``
and ``EdgeAllNone`` disjointness rule to detect inconsistent theories.
"""

from abc import ABC
from dataclasses import dataclass

from typedlogic import Fact, axiom

NodeID = str
PredicateID = NodeID


@dataclass(frozen=True)
class Edge(Fact, ABC):
    """A directed edge between two node identifiers."""

    subject: NodeID
    predicate: PredicateID
    object: NodeID


@dataclass(frozen=True)
class EdgeAllSome(Edge):
    """An edge whose subject has some predicate successor in the object class."""

    pass


@dataclass(frozen=True)
class EdgeAllNone(Edge):
    """An edge whose subject has no predicate successor in the object class."""

    pass


@dataclass(frozen=True)
class EdgeAllOne(Edge):
    """
    Every instance of the subject s stands in relation p to exactly one instance of object o.

    E.g. every instance of a Finger is part of exactly one instance of a Hand.

    The current rules expose only the existential consequence of this restriction:
    an ``EdgeAllOne`` fact entails ``EdgeAllSome``. Cardinality/uniqueness checking is
    intentionally left to solvers or future OWLStar rules that support it directly.
    """

    pass


@dataclass(frozen=True)
class PredicateCharacteristic(Fact, ABC):
    """A characteristic attached to a predicate."""

    predicate: PredicateID


@dataclass(frozen=True)
class TransitivePredicate(PredicateCharacteristic):
    """A predicate declared as transitive."""

    pass


@dataclass(frozen=True)
class DisjointClasses(Fact):
    """A pair of disjoint classes whose same-predicate all-some edges are incompatible."""

    class1: NodeID
    class2: NodeID


@dataclass(frozen=True)
class DisjointOver(Fact):
    """A pair of classes disjoint over a predicate."""

    class1: NodeID
    class2: NodeID
    predicate: PredicateID


@axiom
def unary_rules(
    s: NodeID,
    p: PredicateID,
    o: NodeID,
):
    """Infer unary OWLStar edge constraints."""
    if EdgeAllSome(s, p, o):
        assert ~EdgeAllNone(s, p, o)  # noqa: S101
    if EdgeAllOne(s, p, o):
        assert EdgeAllSome(s, p, o)  # noqa: S101


@axiom
def disjointness(
    s: NodeID,
    p: PredicateID,
    c1: NodeID,
    c2: NodeID,
):
    """Infer all-none edges from class and predicate-scoped disjointness."""
    if DisjointOver(c1, c2, p) and EdgeAllSome(s, p, c1):
        assert EdgeAllNone(s, p, c2)  # noqa: S101
    if DisjointOver(c2, c1, p) and EdgeAllSome(s, p, c1):
        assert EdgeAllNone(s, p, c2)  # noqa: S101
    if DisjointClasses(c1, c2) and EdgeAllSome(s, p, c1):
        assert EdgeAllNone(s, p, c2)  # noqa: S101
    if DisjointClasses(c2, c1) and EdgeAllSome(s, p, c1):
        assert EdgeAllNone(s, p, c2)  # noqa: S101


@axiom
def transitivity(
    s: NodeID,
    p: PredicateID,
    z: NodeID,
    o: NodeID,
):
    """Infer transitive all-some edges."""
    if TransitivePredicate(p) and EdgeAllSome(s, p, z) and EdgeAllSome(z, p, o):
        assert EdgeAllSome(s, p, o)  # noqa: S101
