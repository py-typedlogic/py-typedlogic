# LinkML ABox Compile-Away Macros

This document is intentionally written as parseable TLog but not as a direct
clingo target.  The `@predicate(...)` form denotes variable predicate position:
schema terms are expanded away before a concrete ABox theory is sent to clingo.

Convention:

- TBox predicates such as `effective_required/2` are ordinary clingo predicates.
- ABox predicates such as `Person/1` and `name/2` are generated from LinkML
  class, type, enum, and slot names.
- The Python compile-away step only substitutes concrete predicate names; it
  does not implement LinkML schema semantics directly.

```tlog
type ElementID: str.
type SlotID: str.
type PointerID: str.

pred class_ancestor(cls: ElementID, ancestor: ElementID).
pred effective_range(cls: ElementID, slot: SlotID, range: ElementID).
pred effective_minimum_cardinality(cls: ElementID, slot: SlotID, count: int).
pred effective_maximum_cardinality(cls: ElementID, slot: SlotID, count: int).
```

## Intended Macro Semantics

```tlog
/// Class hierarchy materialization:
/// class_ancestor(C, P) + C(I) expands to P(I).
all c, p, i | class_ancestor(c, p) & @c(i) -> @p(i).

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
