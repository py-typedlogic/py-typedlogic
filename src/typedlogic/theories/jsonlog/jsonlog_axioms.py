"""
Minimal logical theory for JSONLog, defining parent-child relationships

"""
from dataclasses import dataclass

from typedlogic import Fact, axiom
from typedlogic.theories.jsonlog.jsonlog import Property, ArrayPointerHasMember, Pointer, PointerID, ObjectPointerHasProperty


@dataclass(frozen=True)
class ParentChildRelationship(Fact):
    """
    A parent-child relationship between two nodes in a JSON object tree.

    Entailed for array nodes and object nodes.
    """
    parent: PointerID
    child: PointerID


@axiom
def list_parent_child(p: PointerID, c: PointerID, ix: int):
    if ArrayPointerHasMember(p, ix, c):
        assert ParentChildRelationship(p, c)


@axiom
def dict_parent_child(p: PointerID, c: PointerID, k: Property):
    if ObjectPointerHasProperty(p, k, c):
        assert ParentChildRelationship(p, c)


@axiom
def node(p: PointerID, c: PointerID):
    if ParentChildRelationship(p, c):
        assert Pointer(c) and Pointer(p)
