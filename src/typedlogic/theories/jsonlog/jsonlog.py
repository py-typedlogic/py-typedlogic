"""
jsonlog is an interpretation of JSON objects as ground terms in a logic theory.

No semantics are assumed -- jsonlog is intended to be used in conjunction with a logic theory.


"""
from dataclasses import dataclass

from typedlogic import Fact

NodeID = str
Key = str


@dataclass(frozen=True)
class Node(Fact):
    """
    A node is a pointer to a location in a JSON object tree.

    A node has a value, but it is not itself a value.

    TODO: check if this is necessary - can be inferred
    """

    loc: NodeID


@dataclass(frozen=True)
class ArrayPointerHasMember(Fact):
    """True if the node is a list and has the specified member at the given index.

    Example:
        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object([1, "foo"]))
        NodeIsList('/')
        ArrayPointerHasMember('/', 0, '/[0]')
        NodeIsLiteral('/[0]')
        NodeIntValue('/[0]', 1)
        ArrayPointerHasMember('/', 1, '/[1]')
        NodeIsLiteral('/[1]')
        NodeStringValue('/[1]', 'foo')
    """

    loc: NodeID
    offset: int
    member: NodeID


@dataclass(frozen=True)
class ObjectPointerHasProperty(Fact):
    """True if loc is an object and has the specified key with the given value reference.

    Example:

        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object({"a": 1, "b": "foo"}))
        NodeIsObject('/')
        ObjectPointerHasProperty('/', 'a', '/a/')
        NodeIsLiteral('/a/')
        NodeIntValue('/a/', 1)
        ObjectPointerHasProperty('/', 'b', '/b/')
        NodeIsLiteral('/b/')
        NodeStringValue('/b/', 'foo')
    """

    loc: NodeID
    key: Key
    member: NodeID


@dataclass(frozen=True)
class NodeStringValue(Fact):
    """The node is a terminal node with a string value.

    Example:
        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object("hello"))
        NodeIsLiteral('/')
        NodeStringValue('/', 'hello')
    """

    loc: NodeID
    value: str


@dataclass(frozen=True)
class NodeIntValue(Fact):
    """The node is a terminal node with an integer value.

    Example:

        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object(5))
        NodeIsLiteral('/')
        NodeIntValue('/', 5)

    Note: JSON does not distinguish between integers and floats, but having this distinction here
    may help with type systems that do not allow conflation.
    """

    loc: NodeID
    value: int


@dataclass(frozen=True)
class NodeFloatValue(Fact):
    """The node is a terminal node with a float value.

    Example:

        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object(5.0))
        NodeIsLiteral('/')
        NodeFloatValue('/', 5.0)

    Note: JSON does not distinguish between integers and floats, but having this distinction here
    may help with type systems that do not allow conflation.
    """

    loc: NodeID
    value: float


@dataclass(frozen=True)
class NodeBooleanValue(Fact):
    """The node is a terminal node with a boolean value.

    Example:
        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object(True))
        NodeIsLiteral('/')
        NodeBooleanValue('/', True)
    """

    loc: NodeID
    value: bool


@dataclass(frozen=True)
class NodeNullValue(Fact):
    """The node is a terminal node with a null value.

    Example:

        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object(None))
        NodeIsLiteral('/')
        NodeNullValue('/')

    """

    loc: NodeID


@dataclass(frozen=True)
class NodeIsList(Fact):
    """
    True if the node is a list.

    Example:

        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object([]))
        NodeIsList('/')


    """
    loc: NodeID


@dataclass(frozen=True)
class NodeIsObject(Fact):
    """
    True if the node is an object.

    Example:
        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object({}))
        NodeIsObject('/')
    """

    loc: NodeID


@dataclass(frozen=True)
class NodeIsLiteral(Fact):
    """True if the node is a terminal value (string, int, float, bool, or null).

    Example:

        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object("hello"))
        NodeIsLiteral('/')
        NodeStringValue('/', 'hello')
    """
    loc: NodeID
