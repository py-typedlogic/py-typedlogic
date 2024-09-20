from dataclasses import dataclass

from typedlogic import Fact

NodeID = str
Key = str


@dataclass(frozen=True)
class Node(Fact):
    """
    A node is a pointer to a location in a JSON object tree.

    A node has a value, but it is not itself a value.
    """

    loc: NodeID


@dataclass(frozen=True)
class ListNodeHasMember(Fact):
    """True if the node is a list and has the specified member at the given index."""

    loc: NodeID
    offset: int
    member: NodeID

@dataclass(frozen=True)
class ObjectNodeLookup(Fact):
    """True if the node is an object and has the specified key with the given value."""

    loc: NodeID
    key: Key
    member: NodeID

@dataclass(frozen=True)
class NodeStringValue(Fact):
    """The node is a terminal node with a string value."""

    loc: NodeID
    value: str

@dataclass(frozen=True)
class NodeIntValue(Fact):
    """The node is a terminal node with an integer value."""

    loc: NodeID
    value: int

@dataclass(frozen=True)
class NodeFloatValue(Fact):
    """The node is a terminal node with a float value."""

    loc: NodeID
    value: float

@dataclass(frozen=True)
class NodeBooleanValue(Fact):
    """The node is a terminal node with a boolean value."""

    loc: NodeID
    value: bool

@dataclass(frozen=True)
class NodeNullValue(Fact):
    """The node is a terminal node with a null value."""

    loc: NodeID


@dataclass(frozen=True)
class NodeIsList(Fact):
    loc: NodeID

@dataclass(frozen=True)
class NodeIsObject(Fact):
    loc: NodeID

@dataclass(frozen=True)
class NodeIsLiteral(Fact):
    loc: NodeID


