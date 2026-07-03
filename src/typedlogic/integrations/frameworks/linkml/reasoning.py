"""Reasoning utilities for LinkML schemas and generated ABox constraints."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Union

from typedlogic import And, Forall, Implies, NegationAsFailure, Or, PredicateDefinition, Term, Theory, Variable
from typedlogic.datamodel import CardinalityConstraint, Sentence
from typedlogic.integrations.frameworks.linkml import loader
from typedlogic.parsers.tlog_parser import TLogMarkdownParser

SchemaSource = Union[Mapping[str, Any], Theory]

SCHEMA_RULES_RESOURCE = "linkml_schema_rules.tlog.md"
ABOX_MACROS_RESOURCE = "linkml_abox_macros.tlog.md"

PREDICATE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class LinkMLSchemaCheck:
    """Result of running the LinkML schema reasoning layer."""

    satisfiable: bool
    theory: Theory
    materialized_facts: tuple[Term, ...] = ()
    program: str = ""

    @property
    def valid(self) -> bool:
        """Return whether the schema passed the closed-world schema constraints."""
        return self.satisfiable


def schema_rules_path() -> Path:
    """Return the packaged schema preprocessing rule document path."""
    return Path(str(files("typedlogic.integrations.frameworks.linkml").joinpath(SCHEMA_RULES_RESOURCE)))


def abox_macro_rules_path() -> Path:
    """Return the packaged ABox macro rule document path."""
    return Path(str(files("typedlogic.integrations.frameworks.linkml").joinpath(ABOX_MACROS_RESOURCE)))


def load_schema_rules() -> Theory:
    """Load the clingo-compatible LinkML schema preprocessing rules."""
    return TLogMarkdownParser().parse(schema_rules_path())


def load_abox_macro_rules() -> Theory:
    """
    Load the HiLog-style LinkML ABox macro rules.

    These rules document the compile-away layer and are parseable TLog, but they
    are intentionally not sent directly to first-order/clingo targets because
    they use variable predicate position.
    """
    return TLogMarkdownParser().parse(abox_macro_rules_path())


def schema_theory_from_object(schema: Mapping[str, Any], include_schema_rules: bool = True) -> Theory:
    """Build a theory containing LinkML TBox facts and, optionally, schema rules."""
    theory = Theory(name="linkml_schema")
    _merge_predicate_definitions(theory, _schema_predicate_definitions())
    theory.ground_terms.extend(loader.generate_from_object(schema))
    if include_schema_rules:
        _merge_theory(theory, load_schema_rules())
    return theory


def materialize_schema(schema: SchemaSource, include_schema_rules: bool = True) -> LinkMLSchemaCheck:
    """Run the LinkML schema reasoning layer and return materialized facts."""
    from typedlogic.integrations.solvers.clingo.clingo_solver import ClingoSolver

    theory = schema if isinstance(schema, Theory) else schema_theory_from_object(schema, include_schema_rules)
    solver = ClingoSolver()
    solver.add(theory)
    program = solver.dump()
    models = list(solver.models())
    if not models:
        return LinkMLSchemaCheck(satisfiable=False, theory=theory, program=program)
    return LinkMLSchemaCheck(
        satisfiable=True,
        theory=theory,
        materialized_facts=tuple(sorted(models[0].ground_terms, key=repr)),
        program=program,
    )


def check_schema(schema: SchemaSource) -> bool:
    """Return whether a LinkML schema satisfies the schema-level rules."""
    return materialize_schema(schema).valid


def compile_schema_to_abox(schema: SchemaSource) -> Theory:
    """
    Compile a LinkML schema into direct ABox rules.

    The returned theory assumes ABox data is already represented using unary
    class/type predicates and binary slot predicates, for example
    ``Person(i)`` and ``name(i, v)``.
    """
    check = materialize_schema(schema)
    if not check.valid:
        raise ValueError("LinkML schema failed schema-level reasoning constraints")

    facts = _facts_by_predicate(check.materialized_facts)
    _validate_abox_predicate_names(facts)

    theory = Theory(name="linkml_abox_constraints")
    _merge_predicate_definitions(theory, _abox_predicate_definitions(facts))
    _add_schema_metadata(theory, check)

    for child, parent in sorted(_tuples(facts, "range_ancestor")):
        _add_once(theory, _unary_rule(child, parent))

    for child, parent in sorted(_tuples(facts, "slot_ancestor")):
        _add_once(theory, _binary_rule(child, parent))

    for enum_name, value in sorted(_tuples(facts, "permissible_value")):
        term = Term(str(enum_name), str(value))
        if term not in theory.ground_terms:
            theory.ground_terms.append(term)

    for cls, slot, range_name in sorted(_tuples(facts, "effective_range")):
        _add_once(theory, _range_constraint(cls, slot, range_name))

    for cls, slot, minimum in sorted(_tuples(facts, "effective_minimum_cardinality")):
        minimum_int = int(minimum)
        if minimum_int > 0:
            _add_once(theory, _minimum_cardinality_constraint(cls, slot, minimum_int))

    for cls, slot, maximum in sorted(_tuples(facts, "effective_maximum_cardinality")):
        maximum_int = int(maximum)
        if maximum_int >= 0:
            _add_once(theory, _maximum_cardinality_constraint(cls, slot, maximum_int))

    for predicate in ("effective_identifier", "effective_key"):
        for cls, slot in sorted(_tuples(facts, predicate)):
            _add_once(theory, _uniqueness_constraint(cls, slot))

    for predicate in ("effective_equals_string", "effective_equals_number"):
        for cls, slot, value in sorted(_tuples(facts, predicate)):
            _add_once(theory, _allowed_values_constraint(cls, slot, [value]))

    allowed_values: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for cls, slot, value in sorted(_tuples(facts, "effective_equals_string_in")):
        allowed_values[(cls, slot)].append(value)
    for (cls, slot), values in sorted(allowed_values.items()):
        _add_once(theory, _allowed_values_constraint(cls, slot, values))

    for (slot_name,) in sorted(_tuples(facts, "slot_transitive")):
        _add_once(theory, _transitive_rule(str(slot_name)))

    return theory


def validate_abox(schema: SchemaSource, facts: Iterable[Term]) -> bool:
    """Validate direct ABox facts against a LinkML schema using clingo."""
    from typedlogic.integrations.solvers.clingo.clingo_solver import ClingoSolver

    theory = compile_schema_to_abox(schema)
    theory.ground_terms.extend(facts)
    solver = ClingoSolver()
    solver.add(theory)
    return bool(solver.check().satisfiable)


def _facts_by_predicate(facts: Iterable[Term]) -> dict[str, set[tuple[Any, ...]]]:
    by_predicate: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
    for fact in facts:
        by_predicate[str(fact.predicate)].add(tuple(fact.values))
    return by_predicate


def _tuples(facts: Mapping[str, set[tuple[Any, ...]]], predicate: str) -> set[tuple[Any, ...]]:
    return facts.get(predicate, set())


def _unary_rule(child: str, parent: str) -> Sentence:
    instance = Variable("I")
    return Forall([instance], Implies(Term(child, instance), Term(parent, instance)))


def _binary_rule(child: str, parent: str) -> Sentence:
    instance = Variable("I")
    value = Variable("V")
    return Forall([instance, value], Implies(Term(child, instance, value), Term(parent, instance, value)))


def _transitive_rule(slot: str) -> Sentence:
    x = Variable("X")
    y = Variable("Y")
    z = Variable("Z")
    return Forall([x, y, z], Implies(And(Term(slot, x, y), Term(slot, y, z)), Term(slot, x, z)))


def _uniqueness_constraint(cls: str, slot: str) -> Sentence:
    first = Variable("I1")
    second = Variable("I2")
    value = Variable("V")
    return Forall(
        [first, second, value],
        Implies(
            And(
                Term(cls, first),
                Term(cls, second),
                Term(slot, first, value),
                Term(slot, second, value),
                Term("ne", first, second),
            ),
            Or(),
        ),
    )


def _allowed_values_constraint(cls: str, slot: str, values: Iterable[Any]) -> Sentence:
    instance = Variable("I")
    value = Variable("V")
    conditions = [Term(cls, instance), Term(slot, instance, value)]
    conditions.extend(Term("ne", value, allowed) for allowed in values)
    return Forall([instance, value], Implies(And(*conditions), Or()))


def _range_constraint(cls: str, slot: str, range_name: str) -> Sentence:
    instance = Variable("I")
    value = Variable("V")
    return Forall(
        [instance, value],
        Implies(
            And(Term(cls, instance), Term(slot, instance, value), NegationAsFailure(Term(range_name, value))),
            Or(),
        ),
    )


def _minimum_cardinality_constraint(cls: str, slot: str, minimum: int) -> Sentence:
    instance = Variable("I")
    value = Variable("V")
    slot_value = Term(slot, instance, value)
    cardinality = CardinalityConstraint(slot_value, slot_value, maximum_number=minimum - 1)
    return Forall(
        [instance],
        Implies(And(Term(cls, instance), cardinality), Or()),
    )


def _maximum_cardinality_constraint(cls: str, slot: str, maximum: int) -> Sentence:
    instance = Variable("I")
    value = Variable("V")
    slot_value = Term(slot, instance, value)
    cardinality = CardinalityConstraint(slot_value, slot_value, minimum_number=maximum + 1)
    return Forall(
        [instance],
        Implies(And(Term(cls, instance), cardinality), Or()),
    )


def _validate_abox_predicate_names(facts: Mapping[str, set[tuple[Any, ...]]]) -> None:
    names = set()
    for predicate in ("class_definition", "type_definition", "enum_definition", "slot_definition"):
        names.update(str(values[0]) for values in _tuples(facts, predicate))
    invalid = sorted(name for name in names if not PREDICATE_NAME_PATTERN.fullmatch(name))
    if invalid:
        raise ValueError(
            "LinkML class, type, enum, and slot names must be valid predicate identifiers for ABox compilation: "
            + ", ".join(invalid)
        )


def _abox_predicate_definitions(facts: Mapping[str, set[tuple[Any, ...]]]) -> list[PredicateDefinition]:
    definitions: list[PredicateDefinition] = []
    unary_predicates = set()
    for predicate in ("class_definition", "type_definition", "enum_definition"):
        unary_predicates.update(str(values[0]) for values in _tuples(facts, predicate))
    for predicate_name in sorted(unary_predicates):
        definitions.append(PredicateDefinition(predicate_name, {"id": "str"}))
    for slot_name, in sorted(_tuples(facts, "slot_definition")):
        definitions.append(PredicateDefinition(str(slot_name), {"id": "str", "value": "str"}))
    return definitions


def _schema_predicate_definitions() -> list[PredicateDefinition]:
    unary = [
        "schema_definition",
        "class_definition",
        "slot_definition",
        "type_definition",
        "enum_definition",
        "tree_root",
        "slot_required",
        "slot_required_false",
        "slot_recommended",
        "slot_recommended_false",
        "slot_multivalued",
        "slot_multivalued_false",
        "slot_identifier",
        "slot_identifier_false",
        "slot_key",
        "slot_key_false",
        "slot_designates_type",
        "slot_designates_type_false",
        "slot_inlined",
        "slot_inlined_false",
        "slot_inlined_as_list",
        "slot_inlined_as_list_false",
        "slot_transitive",
        "slot_transitive_false",
    ]
    binary = [
        "is_a",
        "mixin",
        "class_slot",
        "attribute",
        "permissible_value",
        "slot_range",
        "slot_pattern",
        "slot_minimum_cardinality",
        "slot_maximum_cardinality",
        "slot_exact_cardinality",
        "slot_equals_string",
        "slot_equals_number",
        "slot_equals_expression",
        "slot_equals_string_in",
    ]
    ternary = [
        "slot_usage_range",
        "slot_usage_pattern",
        "slot_usage_minimum_cardinality",
        "slot_usage_maximum_cardinality",
        "slot_usage_exact_cardinality",
        "slot_usage_equals_string",
        "slot_usage_equals_number",
        "slot_usage_equals_expression",
        "slot_usage_equals_string_in",
    ]
    class_slot_unary = [
        "slot_usage_required",
        "slot_usage_required_false",
        "slot_usage_recommended",
        "slot_usage_recommended_false",
        "slot_usage_multivalued",
        "slot_usage_multivalued_false",
        "slot_usage_identifier",
        "slot_usage_identifier_false",
        "slot_usage_key",
        "slot_usage_key_false",
        "slot_usage_designates_type",
        "slot_usage_designates_type_false",
        "slot_usage_inlined",
        "slot_usage_inlined_false",
        "slot_usage_inlined_as_list",
        "slot_usage_inlined_as_list_false",
        "slot_usage_transitive",
        "slot_usage_transitive_false",
        "slot_usage",
    ]
    definitions = [PredicateDefinition(name, {"id": "str"}) for name in unary]
    definitions.extend(PredicateDefinition(name, {"left": "str", "right": "str"}) for name in binary)
    definitions.extend(PredicateDefinition(name, {"left": "str", "middle": "str", "right": "str"}) for name in ternary)
    definitions.extend(PredicateDefinition(name, {"class": "str", "slot": "str"}) for name in class_slot_unary)
    return definitions


def _merge_theory(target: Theory, source: Theory) -> None:
    target.type_definitions.update(source.type_definitions)
    _merge_predicate_definitions(target, source.predicate_definitions)
    target.sentence_groups.extend(source.sentence_groups)
    target.ground_terms.extend(source.ground_terms)


def _merge_predicate_definitions(target: Theory, definitions: Iterable[PredicateDefinition]) -> None:
    existing = {definition.predicate for definition in target.predicate_definitions}
    for definition in definitions:
        if definition.predicate not in existing:
            target.predicate_definitions.append(definition)
            existing.add(definition.predicate)


def _add_once(theory: Theory, sentence: Sentence) -> None:
    if repr(sentence) not in {repr(existing) for existing in theory.sentences}:
        theory.add(sentence)


def _add_schema_metadata(theory: Theory, check: LinkMLSchemaCheck) -> None:
    if theory._annotations is None:
        theory._annotations = {}
    theory._annotations["linkml_schema_program"] = check.program
