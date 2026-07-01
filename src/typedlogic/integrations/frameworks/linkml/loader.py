"""
Load LinkML schemas as reified TBox facts.

The loader deliberately does not expand LinkML metamodel semantics into Python
rules.  It emits a compact relational representation of the schema; the schema
reasoning rules and the ABox compile-away layer live in :mod:`reasoning`.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Any

from typedlogic import Term

SchemaDict = Mapping[str, Any]

PRIMITIVE_TYPES = (
    "string",
    "integer",
    "float",
    "double",
    "decimal",
    "boolean",
    "date",
    "datetime",
    "uri",
    "uriorcurie",
)


def remove_empty_kvs(obj: Any) -> Any:
    """Remove ``None`` values from a schema-like object."""
    if isinstance(obj, dict):
        return {k: remove_empty_kvs(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [remove_empty_kvs(v) for v in obj]
    return obj


def generate_from_object(obj: SchemaDict) -> Iterator[Term]:
    """
    Generate reified LinkML TBox facts from a schema dictionary.

    Predicate names intentionally use the classic logic spelling used by the
    TLog rules, for example ``class_definition/1``, ``slot_definition/1``, and
    ``class_slot/2``.
    """
    schema = remove_empty_kvs(dict(obj))
    schema_id = schema.get("id") or schema.get("name")
    if schema_id:
        yield Term("schema_definition", str(schema_id))

    yielded_types = set()
    for type_name in PRIMITIVE_TYPES:
        yielded_types.add(type_name)
        yield Term("type_definition", type_name)

    for type_name, type_defn in _items(schema.get("types")):
        yielded_types.add(type_name)
        yield from generate_type_definition(type_name, type_defn or {})

    for enum_name, enum_defn in _items(schema.get("enums")):
        yield from generate_enum_definition(enum_name, enum_defn or {})

    for slot_name, slot_defn in _items(schema.get("slots")):
        yield from generate_slot_definition(slot_name, slot_defn or {})

    for class_name, class_defn in _items(schema.get("classes")):
        yield from generate_class_definition(class_name, class_defn or {})


def generate_class_definition(class_name: str, class_defn: Mapping[str, Any]) -> Iterator[Term]:
    """Generate facts for one LinkML class definition."""
    yield Term("class_definition", class_name)
    if class_defn.get("tree_root") is True:
        yield Term("tree_root", class_name)
    yield from _element_parent_facts(class_name, class_defn)

    for slot_name in _as_list(class_defn.get("slots")):
        yield Term("class_slot", class_name, str(slot_name))

    for slot_name, slot_expr in _items(class_defn.get("attributes")):
        yield Term("attribute", class_name, slot_name)
        yield Term("slot_definition", slot_name)
        yield Term("class_slot", class_name, slot_name)
        yield from _slot_expression_facts("slot", (slot_name,), slot_expr or {})

    for slot_name, slot_expr in _items(class_defn.get("slot_usage")):
        yield Term("slot_usage", class_name, slot_name)
        yield from _slot_expression_facts("slot_usage", (class_name, slot_name), slot_expr or {})


def generate_slot_definition(slot_name: str, slot_defn: Mapping[str, Any]) -> Iterator[Term]:
    """Generate facts for one LinkML slot definition."""
    yield Term("slot_definition", slot_name)
    yield from _element_parent_facts(slot_name, slot_defn)
    yield from _slot_expression_facts("slot", (slot_name,), slot_defn)


def generate_type_definition(type_name: str, type_defn: Mapping[str, Any]) -> Iterator[Term]:
    """Generate facts for one LinkML type definition."""
    yield Term("type_definition", type_name)
    if parent := type_defn.get("typeof"):
        yield Term("is_a", type_name, str(parent))
    yield from _element_parent_facts(type_name, type_defn)


def generate_enum_definition(enum_name: str, enum_defn: Mapping[str, Any]) -> Iterator[Term]:
    """Generate facts for one LinkML enum definition."""
    yield Term("enum_definition", enum_name)
    values = enum_defn.get("permissible_values")
    value_names = list(values) if isinstance(values, Mapping) else _as_list(values)
    for value_name in value_names:
        yield Term("permissible_value", enum_name, str(value_name))
    yield from _element_parent_facts(enum_name, enum_defn)


def _slot_expression_facts(prefix: str, args: tuple[str, ...], slot_expr: Mapping[str, Any]) -> Iterator[Term]:
    """Generate facts for the LinkML SlotExpression metaslots used by reasoning."""
    bool_slots = {
        "required",
        "recommended",
        "multivalued",
        "identifier",
        "key",
        "designates_type",
        "inlined",
        "inlined_as_list",
        "transitive",
    }
    value_slots = {
        "range",
        "pattern",
        "minimum_cardinality",
        "maximum_cardinality",
        "exact_cardinality",
        "equals_string",
        "equals_number",
        "equals_expression",
    }

    for key in sorted(bool_slots):
        if key in slot_expr:
            fact_name = f"{prefix}_{key}"
            if slot_expr[key] is True:
                yield Term(fact_name, *args)
            elif slot_expr[key] is False:
                yield Term(f"{fact_name}_false", *args)

    for key in sorted(value_slots):
        value = slot_expr.get(key)
        if value is not None:
            yield Term(f"{prefix}_{key}", *args, value)

    for value in _as_list(slot_expr.get("equals_string_in")):
        yield Term(f"{prefix}_equals_string_in", *args, str(value))

    for expression_kind in ("any_of", "all_of", "none_of", "exactly_one_of"):
        for index, expression in enumerate(_as_list(slot_expr.get(expression_kind))):
            expression_id = ":".join((*args, expression_kind, str(index)))
            yield Term(f"{prefix}_{expression_kind}", *args, expression_id)
            yield from _slot_expression_facts("anonymous_slot_expression", (expression_id,), expression or {})


def _element_parent_facts(element_name: str, definition: Mapping[str, Any]) -> Iterator[Term]:
    if parent := definition.get("is_a"):
        yield Term("is_a", element_name, str(parent))
    for mixin in _as_list(definition.get("mixins")):
        yield Term("mixin", element_name, str(mixin))


def _items(value: Any) -> Iterable[tuple[str, Mapping[str, Any]]]:
    if not value:
        return ()
    if not isinstance(value, Mapping):
        raise ValueError(f"Expected a mapping, got {type(value)}")
    return ((str(k), v or {}) for k, v in value.items())


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
