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

Metaslots not yet expanded by this layer include `pattern`, `identifier`,
`key`, and the `equals_*` family.

```tlog
type ElementID: str.
type SlotID: str.
type Count: int.

pred range_ancestor(element: ElementID, ancestor: ElementID).
pred slot_ancestor(slot: SlotID, ancestor: SlotID).
pred permissible_value(enum: ElementID, value: str).
pred effective_range(cls: ElementID, slot: SlotID, range: ElementID).
pred effective_minimum_cardinality(cls: ElementID, slot: SlotID, count: Count).
pred effective_maximum_cardinality(cls: ElementID, slot: SlotID, count: Count).
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
```
