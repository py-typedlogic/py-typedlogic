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

pred element_parent(element: ElementID, parent: ElementID).
pred element_ancestor(element: ElementID, ancestor: ElementID).
pred class_parent(cls: ElementID, parent: ElementID).
pred class_ancestor(cls: ElementID, ancestor: ElementID).
pred range_ancestor(element: ElementID, ancestor: ElementID).
pred slot_ancestor(slot: SlotID, ancestor: SlotID).
pred effective_class_slot(cls: ElementID, slot: SlotID).
pred range_definition(id: ElementID).
pred effective_range(cls: ElementID, slot: SlotID, range: ElementID).
pred effective_required(cls: ElementID, slot: SlotID).
pred effective_singlevalued(cls: ElementID, slot: SlotID).
pred effective_multivalued(cls: ElementID, slot: SlotID).
pred effective_minimum_cardinality(cls: ElementID, slot: SlotID, count: Count).
pred effective_maximum_cardinality(cls: ElementID, slot: SlotID, count: Count).
pred effective_exact_cardinality(cls: ElementID, slot: SlotID, count: Count).
pred effective_identifier(cls: ElementID, slot: SlotID).
pred effective_key(cls: ElementID, slot: SlotID).
pred effective_equals_string(cls: ElementID, slot: SlotID, value: str).
pred effective_equals_number(cls: ElementID, slot: SlotID, value: Count).
pred effective_equals_string_in(cls: ElementID, slot: SlotID, value: str).
pred has_equals_string_in_constraint(cls: ElementID, slot: SlotID).
```

## Element Closure And Schema Validity

The `is_a`/`mixin` hierarchy is closed over all element kinds and then
projected per kind: `class_ancestor` drives slot inheritance and `slot_usage`
propagation, while `range_ancestor` (classes, types, and enums) and
`slot_ancestor` are the interface consumed by the ABox compile-away layer.
Parents must be declared and of the same element kind as the child, and the
hierarchy must be acyclic.

```tlog
range_definition(r) :- class_definition(r).
range_definition(r) :- type_definition(r).
range_definition(r) :- enum_definition(r).

slot_definition(s) :- attribute(c, s).
class_slot(c, s) :- attribute(c, s).

element_parent(e, p) :- is_a(e, p).
element_parent(e, p) :- mixin(e, p).
element_ancestor(e, p) :- element_parent(e, p).
element_ancestor(e, a) :- element_parent(e, p), element_ancestor(p, a).

class_parent(c, p) :- class_definition(c), element_parent(c, p).
class_ancestor(c, a) :- class_definition(c), element_ancestor(c, a).
range_ancestor(e, a) :- range_definition(e), element_ancestor(e, a).
slot_ancestor(s, a) :- slot_definition(s), element_ancestor(s, a).

invalid_parent_cycle(e) :- element_ancestor(e, e).
invalid_parent_reference(c, p) :- class_definition(c), element_parent(c, p), not class_definition(p).
invalid_parent_reference(s, p) :- slot_definition(s), element_parent(s, p), not slot_definition(p).
invalid_parent_reference(t, p) :- type_definition(t), element_parent(t, p), not type_definition(p).
invalid_parent_reference(e, p) :- enum_definition(e), element_parent(e, p), not enum_definition(p).
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

applicable_slot_usage_identifier(c, s) :- slot_usage_identifier(c, s).
applicable_slot_usage_identifier(c, s) :- class_parent(c, p), applicable_slot_usage_identifier(p, s).

applicable_slot_usage_key(c, s) :- slot_usage_key(c, s).
applicable_slot_usage_key(c, s) :- class_parent(c, p), applicable_slot_usage_key(p, s).

applicable_slot_usage_equals_string(c, s, v) :- slot_usage_equals_string(c, s, v).
applicable_slot_usage_equals_string(c, s, v) :- class_parent(c, p), applicable_slot_usage_equals_string(p, s, v).

applicable_slot_usage_equals_number(c, s, v) :- slot_usage_equals_number(c, s, v).
applicable_slot_usage_equals_number(c, s, v) :- class_parent(c, p), applicable_slot_usage_equals_number(p, s, v).
```

Each `equals_string_in` declaration is a *set* of allowed values, so its
propagation keeps the declaring class as a source: intersection needs to know
which values belong to which declaration.

```tlog
applicable_slot_usage_equals_string_in(c, s, c, v) :- slot_usage_equals_string_in(c, s, v).
applicable_slot_usage_equals_string_in(c, s, d, v) :- class_parent(c, p), applicable_slot_usage_equals_string_in(p, s, d, v).
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

## Identifier And Key Slots

`identifier` and `key` mark a slot whose value is unique across the instances
of a class; the ABox compile-away layer expands them to uniqueness
constraints.  Both imply that the slot is required and single-valued, which is
expressed monotonically by contributing the corresponding constraints.
`identifier: false` and `key: false` contribute nothing.

```tlog
effective_identifier(c, s) :- effective_class_slot(c, s), slot_identifier(s).
effective_identifier(c, s) :- effective_class_slot(c, s), applicable_slot_usage_identifier(c, s).

effective_key(c, s) :- effective_class_slot(c, s), slot_key(s).
effective_key(c, s) :- effective_class_slot(c, s), applicable_slot_usage_key(c, s).

effective_required(c, s) :- effective_identifier(c, s).
effective_required(c, s) :- effective_key(c, s).
effective_maximum_cardinality(c, s, 1) :- effective_identifier(c, s).
effective_maximum_cardinality(c, s, 1) :- effective_key(c, s).
```

## Fixed And Enumerated Values

`equals_string` and `equals_number` fix a slot's value.  Every applicable
declaration applies, so two applicable declarations with different values are
an unsatisfiable schema and are rejected.  `equals_string_in` declarations are
sets of allowed values and are *intersected*: a value is effective only if it
appears in the slot-level set (when one exists) and in every applicable
`slot_usage` set.  An empty intersection is a schema error.

```tlog
effective_equals_string(c, s, v) :- effective_class_slot(c, s), slot_equals_string(s, v).
effective_equals_string(c, s, v) :- effective_class_slot(c, s), applicable_slot_usage_equals_string(c, s, v).

effective_equals_number(c, s, v) :- effective_class_slot(c, s), slot_equals_number(s, v).
effective_equals_number(c, s, v) :- effective_class_slot(c, s), applicable_slot_usage_equals_number(c, s, v).

invalid_equals_string_conflict(c, s, v1, v2) :- effective_equals_string(c, s, v1), effective_equals_string(c, s, v2), v1 != v2.
invalid_equals_number_conflict(c, s, v1, v2) :- effective_equals_number(c, s, v1), effective_equals_number(c, s, v2), v1 != v2.

has_slot_equals_string_in(s) :- slot_equals_string_in(s, v).
equals_string_in_source(c, s, d) :- applicable_slot_usage_equals_string_in(c, s, d, v), effective_class_slot(c, s).

has_equals_string_in_constraint(c, s) :- effective_class_slot(c, s), has_slot_equals_string_in(s).
has_equals_string_in_constraint(c, s) :- equals_string_in_source(c, s, d).

candidate_equals_string_in(c, s, v) :- effective_class_slot(c, s), slot_equals_string_in(s, v).
candidate_equals_string_in(c, s, v) :- effective_class_slot(c, s), applicable_slot_usage_equals_string_in(c, s, d, v).

excluded_equals_string_in(c, s, v) :- candidate_equals_string_in(c, s, v), has_slot_equals_string_in(s), not slot_equals_string_in(s, v).
excluded_equals_string_in(c, s, v) :- candidate_equals_string_in(c, s, v), equals_string_in_source(c, s, d), not applicable_slot_usage_equals_string_in(c, s, d, v).

effective_equals_string_in(c, s, v) :- candidate_equals_string_in(c, s, v), not excluded_equals_string_in(c, s, v).

has_effective_equals_string_in(c, s) :- effective_equals_string_in(c, s, v).
invalid_equals_string_in_empty(c, s) :- has_equals_string_in_constraint(c, s), not has_effective_equals_string_in(c, s).

:- invalid_equals_string_conflict(c, s, v1, v2).
:- invalid_equals_number_conflict(c, s, v1, v2).
:- invalid_equals_string_in_empty(c, s).
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
