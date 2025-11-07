import json
from pathlib import Path
from typing import Any, Iterator, Union

from typedlogic import Fact
from typedlogic.theories.jsonlog.jsonlog import (
    ArrayPointerHasMember,
    PointerBooleanValue,
    PointerFloatValue,
    PointerIntValue,
    PointerIsArray,
    PointerIsLiteral,
    PointerIsObject,
    PointerNullValue,
    PointerStringValue,
    ObjectPointerHasProperty,
)


def generate_from_source(source: Union[Path, str, Any]) -> Iterator[Fact]:
    """
    Generates ground logical sentences from a JSON source, conforming to the JSONLog schema
    (PointerIsObject/1, ObjectPointerHasProperty/3, PointerIsLiteral/1, PointerIntValue/2, etc.).

        >>> from typedlogic.compiler import write_sentences
        >>> write_sentences(generate_from_source('''
        ... {"id": 1,
        ... "name": "a",
        ... "children": [{"id": 2, "name": "b"}]
        ... }
        ... '''))
        PointerIsObject('/')
        ObjectPointerHasProperty('/', 'id', '/id/')
        PointerIsLiteral('/id/')
        PointerIntValue('/id/', 1)
        ObjectPointerHasProperty('/', 'name', '/name/')
        PointerIsLiteral('/name/')
        PointerStringValue('/name/', 'a')
        ObjectPointerHasProperty('/', 'children', '/children/')
        PointerIsArray('/children/')
        ArrayPointerHasMember('/children/', 0, '/children/[0]')
        PointerIsObject('/children/[0]')
        ObjectPointerHasProperty('/children/[0]', 'id', '/children/[0]id/')
        PointerIsLiteral('/children/[0]id/')
        PointerIntValue('/children/[0]id/', 2)
        ObjectPointerHasProperty('/children/[0]', 'name', '/children/[0]name/')
        PointerIsLiteral('/children/[0]name/')
        PointerStringValue('/children/[0]name/', 'b')


    :param source:
    :return:
    """
    if isinstance(source, Path):
        obj = json.load(source.open())
    elif isinstance(source, str):
        obj = json.loads(source)
    else:
        obj = source
    yield from generate_from_object(obj)


def generate_from_object(obj: Any, jsonpath: str = "/") -> Iterator[Fact]:
    """
    Generates logical sentences from a JSON-like object structure.

    literal nodes:

        >>> from typedlogic.compiler import write_sentences
        >>> write_sentences(generate_from_object(5))
        PointerIsLiteral('/')
        PointerIntValue('/', 5)
        >>> write_sentences(generate_from_object("a"))
        PointerIsLiteral('/')
        PointerStringValue('/', 'a')

    Note that each node gets a jsonpath ID corresponding to its location in the JSON structure.

    Object nodes:

    An empty object generates a tree with a single root node:

        >>> from typedlogic.compiler import write_sentences
        >>> write_sentences(generate_from_object({}))
        PointerIsObject('/')

    A simple object generates two nodes (one object, one literal); the first is connected to the second
    voa ObjectPointerHasProperty/2, and the second is connected to a literal via PointerIntValue/2:

        >>> write_sentences(generate_from_object({"a": 1}))
        PointerIsObject('/')
        ObjectPointerHasProperty('/', 'a', '/a/')
        PointerIsLiteral('/a/')
        PointerIntValue('/a/', 1)

    Arrays

        >>> write_sentences(generate_from_object([]))
        PointerIsArray('/')

    ArrayPointerHasMember/3 is used to provide an index for each member of the list:

        >>> write_sentences(generate_from_object([1]))
        PointerIsArray('/')
        ArrayPointerHasMember('/', 0, '/[0]')
        PointerIsLiteral('/[0]')
        PointerIntValue('/[0]', 1)

    :param obj:
    :param jsonpath:
    :return:
    """
    if isinstance(obj, dict):
        yield PointerIsObject(jsonpath)
        for k, v in obj.items():
            child = jsonpath + k + "/"
            yield ObjectPointerHasProperty(jsonpath, k, child)
            yield from generate_from_object(v, child)
    elif isinstance(obj, list):
        yield PointerIsArray(jsonpath)
        for i, v in enumerate(obj):
            child = jsonpath + f"[{i}]"
            yield ArrayPointerHasMember(jsonpath, i, child)
            yield from generate_from_object(v, child)
    else:
        yield PointerIsLiteral(jsonpath)
        if obj is None:
            yield PointerNullValue(jsonpath)
        elif isinstance(obj, str):
            yield PointerStringValue(jsonpath, obj)
        elif isinstance(obj, bool):
            yield PointerBooleanValue(jsonpath, obj)
        elif isinstance(obj, int):
            yield PointerIntValue(jsonpath, obj)
        elif isinstance(obj, float):
            yield PointerFloatValue(jsonpath, obj)
            # TODO: other numbers
        else:
            raise ValueError(f"Unexpected object type: {type(obj)}")
