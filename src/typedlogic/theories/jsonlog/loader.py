import json
from pathlib import Path
from typing import Any, Iterator, Union

from typedlogic import Fact
from typedlogic.theories.jsonlog.jsonlog import (
    ListNodeHasMember,
    NodeBooleanValue,
    NodeFloatValue,
    NodeIntValue,
    NodeIsList,
    NodeIsLiteral,
    NodeIsObject,
    NodeNullValue,
    NodeStringValue,
    ObjectNodeLookup,
)


def generate_from_source(source: Union[Path, str, Any]) -> Iterator[Fact]:
    """
    Generates ground logical sentences from a JSON source, conforming to the JSONLog schema
    (NodeIsObject/1, ObjectNodeLookup/3, NodeIsLiteral/1, NodeIntValue/2, etc.).

        >>> from typedlogic.compiler import write_sentences
        >>> write_sentences(generate_from_source('''
        ... {"id": 1,
        ... "name": "a",
        ... "children": [{"id": 2, "name": "b"}]
        ... }
        ... '''))
        NodeIsObject('/')
        ObjectNodeLookup('/', 'id', '/id/')
        NodeIsLiteral('/id/')
        NodeIntValue('/id/', 1)
        ObjectNodeLookup('/', 'name', '/name/')
        NodeIsLiteral('/name/')
        NodeStringValue('/name/', 'a')
        ObjectNodeLookup('/', 'children', '/children/')
        NodeIsList('/children/')
        ListNodeHasMember('/children/', 0, '/children/[0]')
        NodeIsObject('/children/[0]')
        ObjectNodeLookup('/children/[0]', 'id', '/children/[0]id/')
        NodeIsLiteral('/children/[0]id/')
        NodeIntValue('/children/[0]id/', 2)
        ObjectNodeLookup('/children/[0]', 'name', '/children/[0]name/')
        NodeIsLiteral('/children/[0]name/')
        NodeStringValue('/children/[0]name/', 'b')


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
        NodeIsLiteral('/')
        NodeIntValue('/', 5)
        >>> write_sentences(generate_from_object("a"))
        NodeIsLiteral('/')
        NodeStringValue('/', 'a')

    Note that each node gets a jsonpath ID corresponding to its location in the JSON structure.

    Object nodes:

    An empty object generates a tree with a single root node:

        >>> from typedlogic.compiler import write_sentences
        >>> write_sentences(generate_from_object({}))
        NodeIsObject('/')

    A simple object generates two nodes (one object, one literal); the first is connected to the second
    voa ObjectNodeLookup/2, and the second is connected to a literal via NodeIntValue/2:

        >>> write_sentences(generate_from_object({"a": 1}))
        NodeIsObject('/')
        ObjectNodeLookup('/', 'a', '/a/')
        NodeIsLiteral('/a/')
        NodeIntValue('/a/', 1)

    Arrays

        >>> write_sentences(generate_from_object([]))
        NodeIsList('/')

    ListNodeHasMember/3 is used to provide an index for each member of the list:

        >>> write_sentences(generate_from_object([1]))
        NodeIsList('/')
        ListNodeHasMember('/', 0, '/[0]')
        NodeIsLiteral('/[0]')
        NodeIntValue('/[0]', 1)

    :param obj:
    :param jsonpath:
    :return:
    """
    if isinstance(obj, dict):
        yield NodeIsObject(jsonpath)
        for k, v in obj.items():
            child = jsonpath + k + "/"
            yield ObjectNodeLookup(jsonpath, k, child)
            yield from generate_from_object(v, child)
    elif isinstance(obj, list):
        yield NodeIsList(jsonpath)
        for i, v in enumerate(obj):
            child = jsonpath + f"[{i}]"
            yield ListNodeHasMember(jsonpath, i, child)
            yield from generate_from_object(v, child)
    else:
        yield NodeIsLiteral(jsonpath)
        if obj is None:
            yield NodeNullValue(jsonpath)
        elif isinstance(obj, str):
            yield NodeStringValue(jsonpath, obj)
        elif isinstance(obj, bool):
            yield NodeBooleanValue(jsonpath, obj)
        elif isinstance(obj, int):
            yield NodeIntValue(jsonpath, obj)
        elif isinstance(obj, float):
            yield NodeFloatValue(jsonpath, obj)
            # TODO: other numbers
        else:
            raise ValueError(f"Unexpected object type: {type(obj)}")
