"""
jsonlog is an interpretation of JSON objects as ground terms in a logic theory.

No semantics are assumed -- jsonlog is intended to be used in conjunction with a logic theory.


"""
from dataclasses import dataclass

from typedlogic import Fact

PointerID = str # A pointer ID is a string that uniquely identifies a location in a JSON object tree.
Property = str


@dataclass(frozen=True)
class Pointer(Fact):
    """
    A pointer is a pointer to a location in a JSON object tree.

    A pointer has a value, but it is not itself a value.

    TODO: check if this is necessary - can be inferred
    """

    pointer: PointerID


@dataclass(frozen=True)
class ArrayPointerHasMember(Fact):
    """True if the pointer is an array and has the specified member at the given index.

    Example:
        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object([1, "foo"]))
        PointerIsArray('/')
        ArrayPointerHasMember('/', 0, '/[0]')
        PointerIsLiteral('/[0]')
        PointerIntValue('/[0]', 1)
        ArrayPointerHasMember('/', 1, '/[1]')
        PointerIsLiteral('/[1]')
        PointerStringValue('/[1]', 'foo')
    """

    pointer: PointerID
    offset: int
    member: PointerID


@dataclass(frozen=True)
class ObjectPointerHasProperty(Fact):
    """True if loc is an object and has the specified key with the given value reference.

    Example:

        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object({"a": 1, "b": "foo"}))
        PointerIsObject('/')
        ObjectPointerHasProperty('/', 'a', '/a/')
        PointerIsLiteral('/a/')
        PointerIntValue('/a/', 1)
        ObjectPointerHasProperty('/', 'b', '/b/')
        PointerIsLiteral('/b/')
        PointerStringValue('/b/', 'foo')
    """

    pointer: PointerID
    property: Property
    member: PointerID


@dataclass(frozen=True)
class PointerStringValue(Fact):
    """The pointer is a terminal pointer with a string value.

    Example:
        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object("hello"))
        PointerIsLiteral('/')
        PointerStringValue('/', 'hello')
    """

    pointer: PointerID
    value: str


@dataclass(frozen=True)
class PointerIntValue(Fact):
    """The pointer is a terminal pointer with an integer value.

    Example:

        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object(5))
        PointerIsLiteral('/')
        PointerIntValue('/', 5)

    Note: JSON does not distinguish between integers and floats, but having this distinction here
    may help with type systems that do not allow conflation.
    """

    pointer: PointerID
    value: int


@dataclass(frozen=True)
class PointerFloatValue(Fact):
    """The pointer is a terminal pointer with a float value.

    Example:

        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object(5.0))
        PointerIsLiteral('/')
        PointerFloatValue('/', 5.0)

    Note: JSON does not distinguish between integers and floats, but having this distinction here
    may help with type systems that do not allow conflation.
    """

    pointer: PointerID
    value: float


@dataclass(frozen=True)
class PointerBooleanValue(Fact):
    """The pointer is a terminal pointer with a boolean value.

    Example:
        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object(True))
        PointerIsLiteral('/')
        PointerBooleanValue('/', True)
    """

    pointer: PointerID
    value: bool


@dataclass(frozen=True)
class PointerNullValue(Fact):
    """The pointer is a terminal pointer with a null value.

    Example:

        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object(None))
        PointerIsLiteral('/')
        PointerNullValue('/')

    """

    pointer: PointerID


@dataclass(frozen=True)
class PointerIsArray(Fact):
    """
    True if the pointer is an array.

    Example:

        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object([]))
        PointerIsArray('/')


    """
    pointer: PointerID


@dataclass(frozen=True)
class PointerIsObject(Fact):
    """
    True if the pointer is an object.

    Example:
        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object({}))
        PointerIsObject('/')
    """

    pointer: PointerID


@dataclass(frozen=True)
class PointerIsLiteral(Fact):
    """True if the pointer has a terminal value (string, int, float, bool, or null).

    Example:

        >>> from typedlogic.compiler import write_sentences
        >>> from typedlogic.theories.jsonlog.loader import generate_from_object
        >>> write_sentences(generate_from_object("hello"))
        PointerIsLiteral('/')
        PointerStringValue('/', 'hello')
    """
    pointer: PointerID
