"""OWLStar predicates and inference rules."""

from abc import ABC
from dataclasses import dataclass
from typing import Iterator

from typedlogic import Fact, Sentence, Variable, axiom

NodeID = str
PredicateID = NodeID

S = Variable("S", domain=NodeID.__name__)
C1 = Variable("C1", domain=NodeID.__name__)
C2 = Variable("C2", domain=NodeID.__name__)
P = Variable("P", domain=PredicateID.__name__)


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

    We also want to infer that is LeftHand is a Hand that is part of exactly one LeftSide,
    and LeftFinger is part of exactly one LeftHand, then LeftFinger is part of exactly one LeftHand.
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
    """A pair of disjoint classes."""

    class1: NodeID
    class2: NodeID


@dataclass(frozen=True)
class DisjointOver(Fact):
    """A pair of classes disjoint over a predicate."""

    class1: NodeID
    class2: NodeID
    predicate: PredicateID

    @classmethod
    def rules(cls) -> Iterator[Sentence]:
        """Yield class-level rules for disjoint-over constraints."""
        yield (EdgeAllSome.p(S, P, C1) & EdgeAllSome.p(S, P, C2) & DisjointOver.p(C1, C2, P)) >> False


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
def transitivity(
    s: NodeID,
    p: PredicateID,
    z: NodeID,
    o: NodeID,
):
    """Infer transitive all-some edges."""
    if TransitivePredicate(p) and EdgeAllSome(s, p, z) and EdgeAllSome(z, p, o):
        assert EdgeAllSome(s, p, o)  # noqa: S101
