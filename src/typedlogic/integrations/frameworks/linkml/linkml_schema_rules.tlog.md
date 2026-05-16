# LinkML Schema Reasoning Rules

These rules operate on reified LinkML schema/TBox facts such as
`class_definition/1`, `slot_definition/1`, and `class_slot/2`.  This layer is
intended to be compiled directly to clingo.

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
pred is_a_path(cls: ElementID, ancestor: ElementID).
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

is_a_path(c, p) :- is_a(c, p).
is_a_path(c, a) :- is_a(c, p), is_a_path(p, a).

invalid_is_a_cycle(c) :- is_a_path(c, c).
invalid_parent_reference(c, p) :- class_definition(c), class_parent(c, p), not class_definition(p).
invalid_class_slot(c, s) :- class_slot(c, s), not class_definition(c).
invalid_class_slot(c, s) :- class_slot(c, s), not slot_definition(s).

effective_class_slot(c, s) :- class_slot(c, s).
effective_class_slot(c, s) :- class_parent(c, p), effective_class_slot(p, s).

invalid_slot_usage(c, s) :- slot_usage(c, s), not effective_class_slot(c, s).

:- invalid_is_a_cycle(c).
:- invalid_parent_reference(c, p).
:- invalid_class_slot(c, s).
:- invalid_slot_usage(c, s).
```

## Slot Defaults And Overrides

```tlog
has_slot_range(s) :- slot_range(s, r).
has_slot_usage_range(c, s) :- slot_usage_range(c, s, r).
has_applicable_slot_usage_range(c, s) :- slot_usage_range(c, s, r).
has_applicable_slot_usage_range(c, s) :- class_parent(c, p), has_applicable_slot_usage_range(p, s), not has_slot_usage_range(c, s).

slot_effective_range(s, r) :- slot_range(s, r).
slot_effective_range(s, "string") :- slot_definition(s), not has_slot_range(s).

effective_range(c, s, r) :- slot_usage_range(c, s, r).
effective_range(c, s, r) :- class_parent(c, p), effective_range(p, s, r), has_applicable_slot_usage_range(p, s), effective_class_slot(c, s), not has_slot_usage_range(c, s).
effective_range(c, s, r) :- effective_class_slot(c, s), slot_effective_range(s, r), not has_applicable_slot_usage_range(c, s).

invalid_range(c, s, r) :- effective_range(c, s, r), not range_definition(r).
:- invalid_range(c, s, r).

effective_required(c, s) :- effective_class_slot(c, s), slot_required(s), not slot_usage_required_false(c, s).
effective_required(c, s) :- slot_usage_required(c, s).
effective_required(c, s) :- class_parent(c, p), effective_required(p, s), effective_class_slot(c, s), not slot_usage_required_false(c, s), not slot_usage_required(c, s).

has_applicable_multivalued(c, s) :- effective_class_slot(c, s), slot_multivalued(s), not slot_usage_multivalued_false(c, s).
has_applicable_multivalued(c, s) :- slot_usage_multivalued(c, s).
has_applicable_multivalued(c, s) :- class_parent(c, p), has_applicable_multivalued(p, s), effective_class_slot(c, s), not slot_usage_multivalued_false(c, s), not slot_usage_multivalued(c, s).
effective_multivalued(c, s) :- has_applicable_multivalued(c, s).
effective_singlevalued(c, s) :- effective_class_slot(c, s), not has_applicable_multivalued(c, s).
effective_singlevalued(c, s) :- slot_usage_multivalued_false(c, s).
```

## Cardinality Normalization

```tlog
explicit_minimum_cardinality(c, s, n) :- effective_class_slot(c, s), slot_minimum_cardinality(s, n), not has_slot_usage_minimum_cardinality(c, s).
explicit_minimum_cardinality(c, s, n) :- slot_usage_minimum_cardinality(c, s, n).
explicit_minimum_cardinality(c, s, n) :- effective_class_slot(c, s), slot_exact_cardinality(s, n), not has_slot_usage_exact_cardinality(c, s).
explicit_minimum_cardinality(c, s, n) :- slot_usage_exact_cardinality(c, s, n).
explicit_minimum_cardinality(c, s, n) :- class_parent(c, p), explicit_minimum_cardinality(p, s, n), effective_class_slot(c, s), not has_slot_usage_minimum_cardinality(c, s), not has_slot_usage_exact_cardinality(c, s).

explicit_maximum_cardinality(c, s, n) :- effective_class_slot(c, s), slot_maximum_cardinality(s, n), not has_slot_usage_maximum_cardinality(c, s).
explicit_maximum_cardinality(c, s, n) :- slot_usage_maximum_cardinality(c, s, n).
explicit_maximum_cardinality(c, s, n) :- effective_class_slot(c, s), slot_exact_cardinality(s, n), not has_slot_usage_exact_cardinality(c, s).
explicit_maximum_cardinality(c, s, n) :- slot_usage_exact_cardinality(c, s, n).
explicit_maximum_cardinality(c, s, n) :- class_parent(c, p), explicit_maximum_cardinality(p, s, n), effective_class_slot(c, s), not has_slot_usage_maximum_cardinality(c, s), not has_slot_usage_exact_cardinality(c, s).

effective_exact_cardinality(c, s, n) :- effective_class_slot(c, s), slot_exact_cardinality(s, n), not has_slot_usage_exact_cardinality(c, s).
effective_exact_cardinality(c, s, n) :- slot_usage_exact_cardinality(c, s, n).
effective_exact_cardinality(c, s, n) :- effective_minimum_cardinality(c, s, n), effective_maximum_cardinality(c, s, n).

has_slot_usage_minimum_cardinality(c, s) :- slot_usage_minimum_cardinality(c, s, n).
has_slot_usage_maximum_cardinality(c, s) :- slot_usage_maximum_cardinality(c, s, n).
has_slot_usage_exact_cardinality(c, s) :- slot_usage_exact_cardinality(c, s, n).
has_explicit_minimum_cardinality(c, s) :- explicit_minimum_cardinality(c, s, n).
has_explicit_maximum_cardinality(c, s) :- explicit_maximum_cardinality(c, s, n).

effective_minimum_cardinality(c, s, n) :- explicit_minimum_cardinality(c, s, n).
effective_minimum_cardinality(c, s, 1) :- effective_required(c, s), not has_explicit_minimum_cardinality(c, s).

effective_maximum_cardinality(c, s, n) :- explicit_maximum_cardinality(c, s, n).
effective_maximum_cardinality(c, s, 1) :- effective_singlevalued(c, s), not has_explicit_maximum_cardinality(c, s).

invalid_cardinality_bounds(c, s, min, max) :- effective_minimum_cardinality(c, s, min), effective_maximum_cardinality(c, s, max), min > max.
invalid_exact_minimum(c, s, exact, min) :- effective_exact_cardinality(c, s, exact), explicit_minimum_cardinality(c, s, min), exact != min.
invalid_exact_maximum(c, s, exact, max) :- effective_exact_cardinality(c, s, exact), explicit_maximum_cardinality(c, s, max), exact != max.

:- invalid_cardinality_bounds(c, s, min, max).
:- invalid_exact_minimum(c, s, exact, min).
:- invalid_exact_maximum(c, s, exact, max).
```
