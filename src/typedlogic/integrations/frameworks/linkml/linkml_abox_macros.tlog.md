# LinkML ABox Compile-Away Macros

This document is intentionally written as parseable TLog but not as a direct
clingo target.  The `@predicate(...)` form denotes variable predicate position:
schema terms are expanded away before a concrete ABox theory is sent to clingo.

Convention:

- TBox predicates such as `effective_required/2` are ordinary clingo predicates
  materialized by the schema rules layer.
- ABox predicates such as `Person/1` and `name/2` are generated from LinkML
  class, type, enum, and slot names.
- The Python compile-away step only substitutes concrete predicate names; it
  does not implement LinkML schema semantics directly.

The schema layer is monotonic (see `linkml_schema_rules.tlog.md`): every
applicable constraint materializes as its own TBox fact, so a class/slot pair
may carry several `effective_range` facts and several cardinality bounds.  The
macros expand each fact to its own ABox constraint, and the conjunction of
those constraints realizes the intersection semantics — a value must satisfy
every applicable range, and slot counts must fall inside every applicable
cardinality interval.

Metaslots not yet expanded by this layer: `pattern` (clingo has no regular
expression matching), `recommended` (warning-level, not a hard constraint),
and the serialization-oriented `inlined`, `inlined_as_list`, and
`designates_type`.  `slot_usage_transitive` is also ignored: transitivity is a
property of the slot predicate itself and cannot be scoped to one class.

```tlog
type ElementID: str.
type SlotID: str.
type Count: int.

pred range_ancestor(element: ElementID, ancestor: ElementID).
pred slot_ancestor(slot: SlotID, ancestor: SlotID).
pred permissible_value(enum: ElementID, value: str).
pred slot_transitive(slot: SlotID).
pred effective_range(cls: ElementID, slot: SlotID, range: ElementID).
pred effective_minimum_cardinality(cls: ElementID, slot: SlotID, count: Count).
pred effective_maximum_cardinality(cls: ElementID, slot: SlotID, count: Count).
pred effective_identifier(cls: ElementID, slot: SlotID).
pred effective_key(cls: ElementID, slot: SlotID).
pred effective_equals_string(cls: ElementID, slot: SlotID, value: str).
pred effective_equals_number(cls: ElementID, slot: SlotID, value: Count).
pred effective_equals_string_in(cls: ElementID, slot: SlotID, value: str).
pred has_equals_string_in_constraint(cls: ElementID, slot: SlotID).
```

## Intended Macro Semantics

```tlog
/// Class, type, and enum hierarchy materialization:
/// range_ancestor(E, P) + E(I) expands to P(I).
all e, p, i | range_ancestor(e, p) & @e(i) -> @p(i).

/// Slot hierarchy materialization (subproperty semantics):
/// slot_ancestor(S, T) + S(I, V) expands to T(I, V).
all s, t, i, v | slot_ancestor(s, t) & @s(i, v) -> @t(i, v).

/// Enum membership:
/// permissible_value(E, V) expands to the ground fact E(V).
all e, v | permissible_value(e, v) -> @e(v).

/// Range checks:
/// effective_range(C, S, R) expands to an ABox constraint over C/1, S/2, and R/1.
all c, s, r, i, v | effective_range(c, s, r) & @c(i) & @s(i, v) & not @r(v) -> false.

/// Minimum cardinality:
/// effective_minimum_cardinality(C, S, N) expands to a closed-world aggregate constraint.
all c, s, n, i | effective_minimum_cardinality(c, s, n) & @c(i) -> has_at_least(i, s, n).

/// Maximum cardinality:
/// effective_maximum_cardinality(C, S, N) expands to a closed-world aggregate constraint.
all c, s, n, i | effective_maximum_cardinality(c, s, n) & @c(i) -> has_at_most(i, s, n).

/// Identifier uniqueness:
/// effective_identifier(C, S) expands to a per-class uniqueness constraint.
all c, s, i1, i2, v | effective_identifier(c, s) & @c(i1) & @c(i2) & @s(i1, v) & @s(i2, v) & i1 != i2 -> false.

/// Key uniqueness:
/// effective_key(C, S) expands the same way as effective_identifier.
all c, s, i1, i2, v | effective_key(c, s) & @c(i1) & @c(i2) & @s(i1, v) & @s(i2, v) & i1 != i2 -> false.

/// Fixed string values:
/// effective_equals_string(C, S, W) expands to a fixed-value constraint.
all c, s, w, i, v | effective_equals_string(c, s, w) & @c(i) & @s(i, v) & v != w -> false.

/// Fixed numeric values:
/// effective_equals_number(C, S, W) expands to a fixed-value constraint.
all c, s, w, i, v | effective_equals_number(c, s, w) & @c(i) & @s(i, v) & v != w -> false.

/// Allowed value sets:
/// the intersected effective_equals_string_in values become the only allowed values.
all c, s, i, v | has_equals_string_in_constraint(c, s) & @c(i) & @s(i, v) & not effective_equals_string_in(c, s, v) -> false.

/// Transitivity:
/// slot_transitive(S) expands to a transitive closure rule over S/2.
all s, x, y, z | slot_transitive(s) & @s(x, y) & @s(y, z) -> @s(x, z).
```
