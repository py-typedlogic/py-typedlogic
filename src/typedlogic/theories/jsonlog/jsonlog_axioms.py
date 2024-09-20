from dataclasses import dataclass

from typedlogic import Fact, axiom
from typedlogic.theories.jsonlog.jsonlog import Key, ListNodeHasMember, Node, NodeID, ObjectNodeLookup


@dataclass(frozen=True)
class ParentChildRelationship(Fact):
    parent: NodeID
    child: NodeID


@axiom
def list_parent_child(p: NodeID, c: NodeID, ix: int):
    if ListNodeHasMember(p, ix, c):
        assert ParentChildRelationship(p, c)


@axiom
def dict_parent_child(p: NodeID, c: NodeID, k: Key):
    if ObjectNodeLookup(p, k, c):
        assert ParentChildRelationship(p, c)


@axiom
def node(p: NodeID, c: NodeID):
    if ParentChildRelationship(p, c):
        assert Node(c) and Node(p)
