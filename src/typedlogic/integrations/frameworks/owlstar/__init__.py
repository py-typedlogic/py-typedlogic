"""OWLStar framework integration."""

from typedlogic import axiom
from typedlogic.integrations.frameworks.owlstar.owlstar import (
    DisjointClasses,
    DisjointOver,
    Edge,
    EdgeAllNone,
    EdgeAllOne,
    EdgeAllSome,
    NodeID,
    PredicateCharacteristic,
    PredicateID,
    TransitivePredicate,
)


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


__all__ = [
    "DisjointClasses",
    "DisjointOver",
    "Edge",
    "EdgeAllNone",
    "EdgeAllOne",
    "EdgeAllSome",
    "NodeID",
    "PredicateCharacteristic",
    "PredicateID",
    "TransitivePredicate",
    "disjointness",
    "transitivity",
    "unary_rules",
]
