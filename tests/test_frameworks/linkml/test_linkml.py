"""Tests for LinkML schema reasoning and ABox compile-away."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from typedlogic import Term, Theory
from typedlogic.cli import app
from typedlogic.compilers.tlog_compiler import TLogCompiler
from typedlogic.integrations.frameworks.linkml import loader
from typedlogic.integrations.frameworks.linkml.linkml_parser import LinkMLParser
from typedlogic.integrations.frameworks.linkml.reasoning import (
    check_schema,
    compile_schema_to_abox,
    load_abox_macro_rules,
    load_schema_rules,
    materialize_schema,
    schema_theory_from_object,
    validate_abox,
)
from typedlogic.integrations.frameworks.linkml.validator import validate as validate_with_legacy_entrypoint
from typedlogic.integrations.solvers.clingo.clingo_solver import ClingoSolver

runner = CliRunner()


def has_term(terms: list[Term] | tuple[Term, ...] | set[Term], predicate: str, *values: Any) -> bool:
    """Return whether terms contain the requested ground term."""
    return Term(predicate, *values) in terms


def solve_with_facts(theory: Theory, *facts: Term) -> bool:
    """Return clingo satisfiability after adding facts to a theory."""
    theory.ground_terms.extend(facts)
    solver = ClingoSolver()
    solver.add(theory)
    return bool(solver.check().satisfiable)


PERSON_SCHEMA = {
    "id": "https://example.org/person",
    "slots": {
        "id": {"identifier": True, "range": "string", "required": True},
        "name": {"range": "string", "required": True},
        "age": {"range": "integer", "required": False},
        "aliases": {"range": "string", "multivalued": True, "minimum_cardinality": 1, "maximum_cardinality": 2},
    },
    "classes": {
        "NamedThing": {"slots": ["id"]},
        "Person": {
            "is_a": "NamedThing",
            "slots": ["name", "age", "aliases"],
            "slot_usage": {"age": {"required": True}},
        },
        "Employee": {
            "is_a": "Person",
            "attributes": {
                "employee_id": {"range": "string", "required": True},
            },
        },
    },
}


def test_loader_emits_reified_tbox_facts_only() -> None:
    """The LinkML loader emits classic schema predicates, not Python-expanded ABox rules."""
    facts = list(loader.generate_from_object(PERSON_SCHEMA))

    assert has_term(facts, "schema_definition", "https://example.org/person")
    assert has_term(facts, "class_definition", "Person")
    assert has_term(facts, "slot_definition", "name")
    assert has_term(facts, "class_slot", "Person", "name")
    assert has_term(facts, "attribute", "Employee", "employee_id")
    assert has_term(facts, "slot_required", "name")
    assert has_term(facts, "slot_required_false", "age")
    assert has_term(facts, "slot_usage_required", "Person", "age")
    assert not any(term.predicate == "InstSlotRequired" for term in facts)


def test_loader_emits_type_enum_and_boolean_slot_expression_facts() -> None:
    """Types, enums, and explicit false slot-expression values are represented as TBox facts."""
    schema = {
        "types": {"PositiveInteger": {"typeof": "integer"}},
        "enums": {"Status": {"permissible_values": {"ACTIVE": {}, "INACTIVE": {}}}},
        "slots": {"status": {"range": "Status", "required": False, "multivalued": False}},
        "classes": {"Sample": {"slots": ["status"]}},
    }

    facts = list(loader.generate_from_object(schema))

    assert has_term(facts, "type_definition", "PositiveInteger")
    assert has_term(facts, "enum_definition", "Status")
    assert has_term(facts, "is_a", "PositiveInteger", "integer")
    assert has_term(facts, "slot_required_false", "status")
    assert has_term(facts, "slot_multivalued_false", "status")


def test_schema_rules_and_macro_rules_are_parseable_tlog_markdown() -> None:
    """Both LinkML rule documents are authored outside Python as literate TLog."""
    schema_rules = load_schema_rules()
    macro_rules = load_abox_macro_rules()

    assert schema_rules.predicate_definition_map["effective_class_slot"].arguments == {
        "cls": "ElementID",
        "slot": "SlotID",
    }
    assert len(schema_rules.sentences) > 30
    assert len(macro_rules.sentences) == 4
    assert "@c(" in TLogCompiler().compile(macro_rules)


def test_schema_reasoning_materializes_inheritance_defaults_and_overrides() -> None:
    """Clingo preprocessing derives effective LinkML schema facts."""
    check = materialize_schema(PERSON_SCHEMA)
    facts = set(check.materialized_facts)

    assert check.valid
    assert has_term(facts, "class_ancestor", "Employee", "Person")
    assert has_term(facts, "effective_class_slot", "Employee", "id")
    assert has_term(facts, "effective_class_slot", "Employee", "employee_id")
    assert has_term(facts, "effective_required", "Person", "age")
    assert has_term(facts, "effective_range", "Employee", "employee_id", "string")
    assert has_term(facts, "effective_maximum_cardinality", "Person", "name", 1)
    assert has_term(facts, "effective_minimum_cardinality", "Person", "aliases", 1)
    assert has_term(facts, "effective_maximum_cardinality", "Person", "aliases", 2)


def test_schema_reasoning_rejects_is_a_cycles() -> None:
    """The schema reasoning layer catches class is_a cycles."""
    schema = {"classes": {"A": {"is_a": "B"}, "B": {"is_a": "A"}}}

    assert not check_schema(schema)


def test_schema_reasoning_rejects_missing_slot_definitions() -> None:
    """Class slots must refer to declared or inline LinkML slots."""
    schema = {"classes": {"Person": {"slots": ["name"]}}}

    assert not check_schema(schema)


def test_schema_reasoning_rejects_missing_parent_classes() -> None:
    """Parent references are closed-world checked against declared classes."""
    schema = {"classes": {"Person": {"is_a": "MissingParent"}}}

    assert not check_schema(schema)


def test_schema_reasoning_rejects_inconsistent_cardinality() -> None:
    """Cardinality constraints are normalized and checked before ABox compilation."""
    schema = {
        "slots": {"name": {"minimum_cardinality": 2, "maximum_cardinality": 1}},
        "classes": {"Person": {"slots": ["name"]}},
    }

    assert not check_schema(schema)


def test_schema_reasoning_rejects_unknown_ranges() -> None:
    """Slot ranges must refer to a declared class, type, enum, or primitive type."""
    schema = {
        "slots": {"status": {"range": "MissingEnum"}},
        "classes": {"Sample": {"slots": ["status"]}},
    }

    assert not check_schema(schema)


def test_schema_reasoning_materializes_mixin_slots_and_abox_hierarchy() -> None:
    """Mixins participate in schema closure and direct ABox class materialization."""
    schema = {
        "slots": {"label": {"range": "string", "required": True}},
        "classes": {
            "NamedMixin": {"slots": ["label"]},
            "Person": {"mixins": ["NamedMixin"]},
        },
    }
    materialized = set(materialize_schema(schema).materialized_facts)

    assert has_term(materialized, "class_parent", "Person", "NamedMixin")
    assert has_term(materialized, "class_ancestor", "Person", "NamedMixin")
    assert has_term(materialized, "effective_class_slot", "Person", "label")
    assert not validate_abox(schema, [Term("Person", "p1")])
    assert validate_abox(
        schema,
        [
            Term("Person", "p1"),
            Term("label", "p1", "l1"),
            Term("string", "l1"),
        ],
    )


def test_compile_schema_to_abox_rejects_required_slot_absence() -> None:
    """Required slots compile to closed-world ABox aggregate constraints."""
    theory = compile_schema_to_abox(PERSON_SCHEMA)
    valid_facts = [
        Term("Person", "p1"),
        Term("id", "p1", "id1"),
        Term("name", "p1", "n1"),
        Term("age", "p1", "age1"),
        Term("aliases", "p1", "a1"),
        Term("string", "id1"),
        Term("string", "n1"),
        Term("integer", "age1"),
        Term("string", "a1"),
    ]

    assert not solve_with_facts(theory, Term("Person", "p1"))
    assert validate_abox(PERSON_SCHEMA, valid_facts)


def test_compile_schema_to_abox_materializes_class_hierarchy() -> None:
    """The compile-away layer generates direct unary class rules."""
    theory = compile_schema_to_abox(PERSON_SCHEMA)
    theory.ground_terms.extend(
        [
            Term("Employee", "e1"),
            Term("id", "e1", "id1"),
            Term("name", "e1", "n1"),
            Term("employee_id", "e1", "eid1"),
            Term("age", "e1", "age1"),
            Term("aliases", "e1", "a1"),
            Term("string", "id1"),
            Term("string", "n1"),
            Term("string", "eid1"),
            Term("integer", "age1"),
            Term("string", "a1"),
        ]
    )

    solver = ClingoSolver()
    solver.add(theory)
    assert solver.check().satisfiable
    model = next(solver.models())
    assert Term("Person", "e1") in model.ground_terms
    assert Term("NamedThing", "e1") in model.ground_terms


def test_compile_schema_to_abox_rejects_range_violations() -> None:
    """Slot ranges compile to constraints over direct unary range predicates."""
    facts = [
        Term("Person", "p1"),
        Term("id", "p1", "id1"),
        Term("name", "p1", "n1"),
        Term("age", "p1", "age1"),
        Term("aliases", "p1", "a1"),
        Term("string", "id1"),
        Term("string", "n1"),
        Term("string", "age1"),
        Term("string", "a1"),
    ]

    assert not validate_abox(PERSON_SCHEMA, facts)


def test_slot_usage_range_overrides_global_slot_range() -> None:
    """Class-local slot usage refinements override global slot expressions."""
    schema = {
        "slots": {"value": {"range": "string"}},
        "classes": {
            "Measurement": {
                "slots": ["value"],
                "slot_usage": {"value": {"range": "integer", "required": True}},
            }
        },
    }
    materialized = set(materialize_schema(schema).materialized_facts)

    assert has_term(materialized, "effective_range", "Measurement", "value", "integer")
    assert not has_term(materialized, "effective_range", "Measurement", "value", "string")
    assert validate_abox(
        schema,
        [
            Term("Measurement", "m1"),
            Term("value", "m1", "v1"),
            Term("integer", "v1"),
        ],
    )
    assert not validate_abox(
        schema,
        [
            Term("Measurement", "m1"),
            Term("value", "m1", "v1"),
            Term("string", "v1"),
        ],
    )


def test_subclass_inherits_parent_slot_usage_range_and_required() -> None:
    """Subclass induced slots inherit parent slot_usage refinements."""
    schema = {
        "slots": {"value": {"range": "string"}},
        "classes": {
            "Measurement": {
                "slots": ["value"],
                "slot_usage": {"value": {"range": "integer", "required": True}},
            },
            "DerivedMeasurement": {"is_a": "Measurement"},
        },
    }
    materialized = set(materialize_schema(schema).materialized_facts)

    assert has_term(materialized, "effective_range", "DerivedMeasurement", "value", "integer")
    assert not has_term(materialized, "effective_range", "DerivedMeasurement", "value", "string")
    assert has_term(materialized, "effective_required", "DerivedMeasurement", "value")
    assert not validate_abox(schema, [Term("DerivedMeasurement", "m1")])
    assert validate_abox(
        schema,
        [
            Term("DerivedMeasurement", "m1"),
            Term("value", "m1", "v1"),
            Term("integer", "v1"),
        ],
    )
    assert not validate_abox(
        schema,
        [
            Term("DerivedMeasurement", "m1"),
            Term("value", "m1", "v1"),
            Term("string", "v1"),
        ],
    )


def test_subclass_inherits_parent_slot_usage_multivalued_cardinality() -> None:
    """Subclass induced slots inherit parent slot_usage cardinality and multivalued refinements."""
    schema = {
        "slots": {"code": {"range": "string"}},
        "classes": {
            "Sample": {
                "slots": ["code"],
                "slot_usage": {"code": {"multivalued": True, "minimum_cardinality": 2, "maximum_cardinality": 3}},
            },
            "DerivedSample": {"is_a": "Sample"},
        },
    }
    materialized = set(materialize_schema(schema).materialized_facts)

    assert has_term(materialized, "effective_multivalued", "DerivedSample", "code")
    assert has_term(materialized, "effective_minimum_cardinality", "DerivedSample", "code", 2)
    assert has_term(materialized, "effective_maximum_cardinality", "DerivedSample", "code", 3)
    assert validate_abox(
        schema,
        [
            Term("DerivedSample", "s1"),
            Term("code", "s1", "c1"),
            Term("code", "s1", "c2"),
            Term("string", "c1"),
            Term("string", "c2"),
        ],
    )
    assert not validate_abox(
        schema,
        [
            Term("DerivedSample", "s1"),
            Term("code", "s1", "c1"),
            Term("string", "c1"),
        ],
    )


def test_compile_schema_to_abox_rejects_singlevalued_and_max_cardinality_violations() -> None:
    """Default single-valued slots and explicit maximum cardinalities become ABox constraints."""
    too_many_names = [
        Term("Person", "p1"),
        Term("id", "p1", "id1"),
        Term("name", "p1", "n1"),
        Term("name", "p1", "n2"),
        Term("age", "p1", "age1"),
        Term("aliases", "p1", "a1"),
        Term("string", "id1"),
        Term("string", "n1"),
        Term("string", "n2"),
        Term("integer", "age1"),
        Term("string", "a1"),
    ]
    too_many_aliases = [
        Term("Person", "p1"),
        Term("id", "p1", "id1"),
        Term("name", "p1", "n1"),
        Term("age", "p1", "age1"),
        Term("aliases", "p1", "a1"),
        Term("aliases", "p1", "a2"),
        Term("aliases", "p1", "a3"),
        Term("string", "id1"),
        Term("string", "n1"),
        Term("integer", "age1"),
        Term("string", "a1"),
        Term("string", "a2"),
        Term("string", "a3"),
    ]

    assert not validate_abox(PERSON_SCHEMA, too_many_names)
    assert not validate_abox(PERSON_SCHEMA, too_many_aliases)


def test_compile_schema_to_abox_supports_type_and_enum_ranges() -> None:
    """ABox range checks work for LinkML type and enum definitions."""
    schema = {
        "types": {"PositiveInteger": {"typeof": "integer"}},
        "enums": {"Status": {"permissible_values": {"ACTIVE": {}, "INACTIVE": {}}}},
        "slots": {
            "score": {"range": "PositiveInteger", "required": True},
            "status": {"range": "Status", "required": True},
        },
        "classes": {"Sample": {"slots": ["score", "status"]}},
    }

    assert validate_abox(
        schema,
        [
            Term("Sample", "s1"),
            Term("score", "s1", "score1"),
            Term("status", "s1", "status1"),
            Term("PositiveInteger", "score1"),
            Term("Status", "status1"),
        ],
    )
    assert not validate_abox(
        schema,
        [
            Term("Sample", "s1"),
            Term("score", "s1", "score1"),
            Term("status", "s1", "status1"),
            Term("integer", "score1"),
            Term("string", "status1"),
        ],
    )


def test_compile_schema_to_abox_dump_contains_closed_world_aggregate_constraints() -> None:
    """Generated ABox rules are concrete clingo constraints, not schema-level macros."""
    schema = {
        "slots": {"code": {"range": "string", "exact_cardinality": 2, "multivalued": True}},
        "classes": {"Sample": {"slots": ["code"]}},
    }
    solver = ClingoSolver()
    solver.add(compile_schema_to_abox(schema))
    program = solver.dump()

    assert ":- sample(I), {code(I, V) : code(I, V)} <= 1." in program
    assert ":- sample(I), 3 <= {code(I, V) : code(I, V)}." in program


def test_compile_schema_to_abox_enforces_exact_cardinality() -> None:
    """Exact cardinality is normalized to matching minimum and maximum ABox constraints."""
    schema = {
        "slots": {"code": {"range": "string", "exact_cardinality": 2, "multivalued": True}},
        "classes": {"Sample": {"slots": ["code"]}},
    }
    materialized = set(materialize_schema(schema).materialized_facts)

    assert has_term(materialized, "effective_exact_cardinality", "Sample", "code", 2)
    assert has_term(materialized, "effective_minimum_cardinality", "Sample", "code", 2)
    assert has_term(materialized, "effective_maximum_cardinality", "Sample", "code", 2)
    assert not validate_abox(
        schema,
        [
            Term("Sample", "s1"),
            Term("code", "s1", "c1"),
            Term("string", "c1"),
        ],
    )
    assert validate_abox(
        schema,
        [
            Term("Sample", "s1"),
            Term("code", "s1", "c1"),
            Term("code", "s1", "c2"),
            Term("string", "c1"),
            Term("string", "c2"),
        ],
    )
    assert not validate_abox(
        schema,
        [
            Term("Sample", "s1"),
            Term("code", "s1", "c1"),
            Term("code", "s1", "c2"),
            Term("code", "s1", "c3"),
            Term("string", "c1"),
            Term("string", "c2"),
            Term("string", "c3"),
        ],
    )


def test_compile_schema_to_abox_rejects_invalid_predicate_names() -> None:
    """ABox compilation requires LinkML names that can be used as predicate identifiers."""
    schema = {"slots": {"bad-slot": {"required": True}}, "classes": {"Person": {"slots": ["bad-slot"]}}}

    with pytest.raises(ValueError, match="valid predicate identifiers"):
        compile_schema_to_abox(schema)


def test_validator_entrypoint_accepts_direct_abox_facts() -> None:
    """The legacy validator module delegates to the direct ABox validation layer."""
    schema = {"slots": {"name": {"required": True}}, "classes": {"Person": {"slots": ["name"]}}}

    assert validate_with_legacy_entrypoint(
        schema,
        [
            Term("Person", "p1"),
            Term("name", "p1", "n1"),
            Term("string", "n1"),
        ],
    )
    assert not validate_with_legacy_entrypoint(schema, [Term("Person", "p1")])


def test_linkml_parser_returns_schema_theory_with_rules(tmp_path: Path) -> None:
    """The generic LinkML parser exposes schema facts and TLog schema rules."""
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        """
id: https://example.org/parser
slots:
  name:
    required: true
classes:
  Person:
    slots:
      - name
""",
        encoding="utf-8",
    )

    theory = LinkMLParser().parse(schema_path)

    assert Term("class_definition", "Person") in theory.ground_terms
    assert Term("slot_required", "name") in theory.ground_terms
    assert "effective_required" in theory.predicate_definition_map
    assert len(theory.sentences) > 30


def test_generic_dump_cli_accepts_linkml_input_format(tmp_path: Path) -> None:
    """The generic dump command can force LinkML parsing for .yaml schemas."""
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        """
id: https://example.org/cli
slots:
  name:
    required: true
classes:
  Person:
    slots:
      - name
""",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["dump", str(schema_path), "-f", "linkml", "-t", "tlog"])

    assert result.exit_code == 0, result.stdout
    assert "class_definition('Person')" in result.stdout
    assert "effective_required" in result.stdout


def test_schema_theory_without_rules_is_facts_only() -> None:
    """Callers can request just the TBox fact layer."""
    theory = schema_theory_from_object(PERSON_SCHEMA, include_schema_rules=False)

    assert theory.sentences == []
    assert Term("class_definition", "Person") in theory.ground_terms
