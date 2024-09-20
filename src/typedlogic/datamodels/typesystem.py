from enum import Enum
from typing import Dict, Any, Optional, Union


class BaseType(Enum):
    """
    Enum for base types in the type system.
    """
    STR = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    LIST = "list"
    DICT = "dict"
    TUPLE = "tuple"
    SET = "set"

# Mapping dictionaries
python_type_mapping: Dict[BaseType, Any] = {
    BaseType.STR: str,
    BaseType.INT: int,
    BaseType.FLOAT: float,
    BaseType.BOOL: bool,
    BaseType.LIST: list,
    BaseType.DICT: dict,
    BaseType.TUPLE: tuple,
    BaseType.SET: set,
}

json_schema_mapping: Dict[BaseType, str] = {
    BaseType.STR: "string",
    BaseType.INT: "integer",
    BaseType.FLOAT: "number",
    BaseType.BOOL: "boolean",
    BaseType.LIST: "array",
    BaseType.DICT: "object",
    BaseType.TUPLE: "array",
    BaseType.SET: "array",
}

# Reverse mappings for lookup; prioritize first entry in case of duplicates
python_type_to_base_type: Dict[Any, BaseType] = {v: k for k, v in reversed(python_type_mapping.items())}
json_schema_to_base_type: Dict[str, BaseType] = {v: k for k, v in reversed(json_schema_mapping.items())}

def get_python_type(base_type: Union[BaseType, str]) -> Optional[Any]:
    """
    Get the corresponding Python type for a given BaseType.

    Args:
        base_type (BaseType): The BaseType enum value.

    Returns:
        Any: The corresponding Python type.

    Raises:
        KeyError: If no matching Python type is found.

    Examples:
        >>> get_python_type(BaseType.STR)
        <class 'str'>
        >>> get_python_type(BaseType.INT)
        <class 'int'>
        >>> get_python_type(BaseType.FLOAT)
        <class 'float'>
    """
    if isinstance(base_type, str):
        try:
            base_type = BaseType(base_type)
        except ValueError:
            # TODO: ensure types dereferenced previously
            return None
    return python_type_mapping.get(base_type)

def get_json_schema_type(base_type: BaseType) -> str:
    """
    Get the corresponding JSON Schema type for a given BaseType.

    Args:
        base_type (BaseType): The BaseType enum value.

    Returns:
        str: The corresponding JSON Schema type.

    Raises:
        KeyError: If no matching JSON Schema type is found.

    Examples:
        >>> get_json_schema_type(BaseType.STR)
        'string'
        >>> get_json_schema_type(BaseType.INT)
        'integer'
        >>> get_json_schema_type(BaseType.FLOAT)
        'number'
    """
    return json_schema_mapping[base_type]

def from_python_type(py_type: Any) -> BaseType:
    """
    Get the corresponding BaseType for a given Python type.

    Args:
        py_type (Any): The Python type.

    Returns:
        BaseType: The corresponding BaseType enum value.

    Raises:
        ValueError: If no matching BaseType is found.

    Examples:
        >>> from_python_type(str)
        <BaseType.STR: 'str'>
        >>> from_python_type(int)
        <BaseType.INT: 'int'>
        >>> from_python_type(float)
        <BaseType.FLOAT: 'float'>
        >>> from_python_type(complex)
        Traceback (most recent call last):
            ...
        ValueError: No matching BaseType for Python type: <class 'complex'>
    """
    if py_type in python_type_to_base_type:
        return python_type_to_base_type[py_type]
    raise ValueError(f"No matching BaseType for Python type: {py_type}")

def from_json_schema_type(json_type: str) -> BaseType:
    """
    Get the corresponding BaseType for a given JSON Schema type.

    Args:
        json_type (str): The JSON Schema type.

    Returns:
        BaseType: The corresponding BaseType enum value.

    Raises:
        ValueError: If no matching BaseType is found.

    Examples:
        >>> from_json_schema_type("string")
        <BaseType.STR: 'str'>
        >>> from_json_schema_type("integer")
        <BaseType.INT: 'int'>
        >>> from_json_schema_type("number")
        <BaseType.FLOAT: 'float'>
        >>> from_json_schema_type("array")
        <BaseType.LIST: 'list'>
        >>> from_json_schema_type("unknown")
        Traceback (most recent call last):
            ...
        ValueError: No matching BaseType for JSON Schema type: unknown
    """
    if json_type in json_schema_to_base_type:
        return json_schema_to_base_type[json_type]
    raise ValueError(f"No matching BaseType for JSON Schema type: {json_type}")
