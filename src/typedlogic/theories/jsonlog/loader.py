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
    if isinstance(source, Path):
        obj = json.load(source.open())
    elif isinstance(source, str):
        obj = json.loads(source)
    else:
        obj = source
    yield from generate_from_object(obj)

def generate_from_object(obj: Any, jsonpath: str = "/") -> Iterator[Fact]:
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


