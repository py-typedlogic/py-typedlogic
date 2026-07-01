# LinkML Schema Reasoning Rules

These rules operate on reified LinkML schema/TBox facts such as
`class_definition/1`, `slot_definition/1`, and `class_slot/2`.  This layer is
intended to be compiled directly to clingo.

The semantics of this layer is deliberately *monotonic*: slot-level
constraints and `slot_usage` refinements accumulate down the class hierarchy
and are never retracted, so overrides are intentionally not possible.  A
refinement may only tighten what is already there:

- Ranges are *intersected*.  Every applicable range constraint applies, so a
  value must satisfy the slot-level range and every inherited `slot_usage`
  range simultaneously.
- Cardinality intervals are intersected.  The effective minimum is the
  largest applicable minimum and the effective maximum is the smallest
  applicable maximum; an empty intersection is a schema error.
- `required: true` and `multivalued: false` add constraints;
  `required: false` and `multivalued: true` add none, so they cannot cancel a
  constraint declared elsewhere.

Negation-as-failure is reserved for pre-processing defaults, which fill in a
value only when nothing is declared anywhere: the default range (`"string"`)
and the default single-valued interpretation.

Input predicates for individual metaslots (`slot_range/2`, `slot_required/1`,
`slot_usage_range/3`, and so on) are emitted by the loader layer and declared
in `reasoning.py`.

```tlog
type ElementID: str.
type SlotID: str.
type Count: int.

pred class_definition(id: ElementID).
pred slot_definition(id: SlotID).
pred type_definition(id: ElementID).
pred enum_definition(id: ElementID).
pred is_a(element: ElementID, parent: ElementID).
pred mixin(element: ElementID, parent: ElementID).
pred class_slot(cls: ElementID, slot: SlotID).
pred attribute(cls: ElementID, slot: SlotID).
pred slot_usage(cls: ElementID, slot: SlotID).

pred class_parent(cls: ElementID, parent: ElementID).
pred class_ancestor(cls: ElementID, ancestor: ElementID).
pred effective_class_slot(cls: ElementID, slot: SlotID).
pred range_definition(id: ElementID).
pred effective_range(cls: ElementID, slot: SlotID, range: ElementID).
pred effective_required(cls: ElementID, slot: SlotID).
pred effective_singlevalued(cls: ElementID, slot: SlotID).
pred effective_multivalued(cls: ElementID, slot: SlotID).
pred effective_minimum_cardinality(cls: ElementID, slot: SlotID, count: Count).
pred effective_maximum_cardinality(cls: ElementID, slot: SlotID, count: Count).
pred effective_exact_cardinality(cls: ElementID, slot: SlotID, count: Count).
```

## Element Closure And Schema Validity

```tlog
range_definition(r) :- class_definition(r).
range_definition(r) :- type_definition(r).
range_definition(r) :- enum_definition(r).

slot_definition(s) :- attribute(c, s).
class_slot(c, s) :- attribute(c, s).

class_parent(c, p) :- is_a(c, p).
class_parent(c, p) :- mixin(c, p).
class_ancestor(c, p) :- class_parent(c, p).
class_ancestor(c, a) :- class_parent(c, p), class_ancestor(p, a).

invalid_parent_cycle(c) :- class_ancestor(c, c).
invalid_parent_reference(c, p) :- class_definition(c), class_parent(c, p), not class_definition(p).
invalid_class_slot(c, s) :- class_slot(c, s), not class_definition(c).
invalid_class_slot(c, s) :- class_slot(c, s), not slot_definition(s).

effective_class_slot(c, s) :- class_slot(c, s).
effective_class_slot(c, s) :- class_parent(c, p), effective_class_slot(p, s).

invalid_slot_usage(c, s) :- slot_usage(c, s), not effective_class_slot(c, s).

:- invalid_parent_cycle(c).
:- invalid_parent_reference(c, p).
:- invalid_class_slot(c, s).
:- invalid_slot_usage(c, s).
```

## Slot Usage Propagation

`slot_usage` refinements apply to the declaring class and all of its
descendants.  Propagation is unconditional: a descendant's own `slot_usage`
never shadows an inherited one, it just contributes additional constraints.

```tlog
applicable_slot_usage_range(c, s, r) :- slot_usage_range(c, s, r).
applicable_slot_usage_range(c, s, r) :- class_parent(c, p), applicable_slot_usage_range(p, s, r).

applicable_slot_usage_required(c, s) :- slot_usage_required(c, s).
applicable_slot_usage_required(c, s) :- class_parent(c, p), applicable_slot_usage_required(p, s).

applicable_slot_usage_multivalued(c, s) :- slot_usage_multivalued(c, s).
applicable_slot_usage_multivalued(c, s) :- class_parent(c, p), applicable_slot_usage_multivalued(p, s).

applicable_slot_usage_multivalued_false(c, s) :- slot_usage_multivalued_false(c, s).
applicable_slot_usage_multivalued_false(c, s) :- class_parent(c, p), applicable_slot_usage_multivalued_false(p, s).

applicable_slot_usage_minimum_cardinality(c, s, n) :- slot_usage_minimum_cardinality(c, s, n).
applicable_slot_usage_minimum_cardinality(c, s, n) :- class_parent(c, p), applicable_slot_usage_minimum_cardinality(p, s, n).

applicable_slot_usage_maximum_cardinality(c, s, n) :- slot_usage_maximum_cardinality(c, s, n).
applicable_slot_usage_maximum_cardinality(c, s, n) :- class_parent(c, p), applicable_slot_usage_maximum_cardinality(p, s, n).

applicable_slot_usage_exact_cardinality(c, s, n) :- slot_usage_exact_cardinality(c, s, n).
applicable_slot_usage_exact_cardinality(c, s, n) :- class_parent(c, p), applicable_slot_usage_exact_cardinality(p, s, n).
```

## Ranges

Every applicable range materializes; the ABox compile-away layer emits one
constraint per range, so multiple ranges behave as an intersection.  The
`"string"` default is a pre-processing rule: it applies only when no range is
declared for the slot anywhere.

```tlog
has_slot_range(s) :- slot_range(s, r).
has_declared_range(c, s) :- effective_class_slot(c, s), has_slot_range(s).
has_declared_range(c, s) :- applicable_slot_usage_range(c, s, r).

effective_range(c, s, r) :- effective_class_slot(c, s), slot_range(s, r).
effective_range(c, s, r) :- effective_class_slot(c, s), applicable_slot_usage_range(c, s, r).
effective_range(c, s, "string") :- effective_class_slot(c, s), not has_declared_range(c, s).

invalid_range(c, s, r) :- effective_range(c, s, r), not range_definition(r).
:- invalid_range(c, s, r).
```

## Required And Multivalued

`required: true` is a constraint; `required: false` contributes nothing and
therefore cannot cancel a `required: true` declared at the slot level or on an
ancestor.  Likewise `multivalued: false` is a constraint (single-valued) while
`multivalued: true` merely opts out of the single-valued *default*: it cannot
cancel an explicit `multivalued: false` declared elsewhere.

```tlog
effective_required(c, s) :- effective_class_slot(c, s), slot_required(s).
effective_required(c, s) :- effective_class_slot(c, s), applicable_slot_usage_required(c, s).

declared_multivalued(c, s) :- effective_class_slot(c, s), slot_multivalued(s).
declared_multivalued(c, s) :- effective_class_slot(c, s), applicable_slot_usage_multivalued(c, s).
declared_singlevalued(c, s) :- effective_class_slot(c, s), slot_multivalued_false(s).
declared_singlevalued(c, s) :- effective_class_slot(c, s), applicable_slot_usage_multivalued_false(c, s).

effective_singlevalued(c, s) :- declared_singlevalued(c, s).
effective_singlevalued(c, s) :- effective_class_slot(c, s), not declared_multivalued(c, s).
effective_multivalued(c, s) :- effective_class_slot(c, s), not effective_singlevalued(c, s).
```

## Cardinality Normalization

All applicable bounds materialize.  The ABox compile-away layer emits one
constraint per bound, so the effective interval is the intersection of every
applicable interval; `required` contributes a minimum of 1 and single-valued
slots contribute a maximum of 1.  An empty intersection (some applicable
minimum above some applicable maximum) is a schema error.

```tlog
effective_minimum_cardinality(c, s, n) :- effective_class_slot(c, s), slot_minimum_cardinality(s, n).
effective_minimum_cardinality(c, s, n) :- effective_class_slot(c, s), applicable_slot_usage_minimum_cardinality(c, s, n).
effective_minimum_cardinality(c, s, n) :- effective_class_slot(c, s), slot_exact_cardinality(s, n).
effective_minimum_cardinality(c, s, n) :- effective_class_slot(c, s), applicable_slot_usage_exact_cardinality(c, s, n).
effective_minimum_cardinality(c, s, 1) :- effective_required(c, s).

effective_maximum_cardinality(c, s, n) :- effective_class_slot(c, s), slot_maximum_cardinality(s, n).
effective_maximum_cardinality(c, s, n) :- effective_class_slot(c, s), applicable_slot_usage_maximum_cardinality(c, s, n).
effective_maximum_cardinality(c, s, n) :- effective_class_slot(c, s), slot_exact_cardinality(s, n).
effective_maximum_cardinality(c, s, n) :- effective_class_slot(c, s), applicable_slot_usage_exact_cardinality(c, s, n).
effective_maximum_cardinality(c, s, 1) :- effective_singlevalued(c, s).

effective_exact_cardinality(c, s, n) :- effective_minimum_cardinality(c, s, n), effective_maximum_cardinality(c, s, n).

invalid_cardinality_bounds(c, s, min, max) :- effective_minimum_cardinality(c, s, min), effective_maximum_cardinality(c, s, max), min > max.

:- invalid_cardinality_bounds(c, s, min, max).
```
