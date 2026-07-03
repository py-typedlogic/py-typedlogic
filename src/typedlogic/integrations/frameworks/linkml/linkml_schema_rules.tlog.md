# LinkML Schema Reasoning Rules

## Metamodel Reasoning

### Core Metamodel types

```tlog
type ElementID: str.      ## should be a curie string
type SlotID: ElementID.       ## conventions: p, q, r
type ClassID: ElementID.      ## conventions: c, d
type TypeID: ElementID.      ## conventions: t, u
type EnumID: ElementID.       ## conventions: none
type Count: integer.
```

### Metamodel Elements

```tlog
pred class_definition(element: ElementID).
pred slot_definition(element: SlotID).
pred type_definition(element: ElementID).
pred enum_definition(element: ElementID).
pred is_a(element: ElementID, parent: ElementID).
pred mixin(element: ElementID, parent: ElementID).
pred mixins(element: ElementID, parent: ElementID).
```

```tlog
type ElementType: str.
pred element_type(element: ElementID, typ: ElementType).

all e: ElementID | class_definition(e) -> element_type(e, "ClassDefinition").
all e: ElementID | slot_definition(e) -> element_type(e, "SlotDefinition").
all e: ElementID | type_definition(e) -> element_type(e, "TypeDefinition").
all e: ElementID | enum_definition(e) -> element_type(e, "EnumDefinition").

all e: ElementID, t1: ElementType, t2: ElementType | element_type(e, t1), element_type(e, t2) -> t1 = t2.
```

### Parentage

```tlog
pred parent(element: ElementID, parent: ElementID).

all e: ElementID, p: ElementID | mixin(e, p) -> mixins(e, p).
all e: ElementID, p: ElementID | is_a(e, p) -> parent(e, p).
all e: ElementID, p: ElementID | mixins(e, p) -> parent(e, p).
```

types must not be crossed:

```tlog
all e: ElementID, p: ElementID, et: ElementType, pt: ElementType | parent(e, p), element_type(e, et), element_type(p, pt) -> et = pt.
```

### Ancestry

```tlog
pred proper_ancestor(element: ElementID, parent: ElementID).

all e: ElementID, p: ElementID | parent(e, p) -> proper_ancestor(e, p).
all e: ElementID, p: ElementID, a: ElementID | parent(e, p), proper_ancestor(p, a) -> proper_ancestor(e, a).
```

```tlog
lemma(
  "grandparent_implies_ancestor",
  that(all x, y, z | parent(x, y) & parent(y, z) -> proper_ancestor(x, z))
).
```

```tlog
lemma(
  "ancestry_can_cross_mixins_and_isas",
  that(all x, y, z | mixins(x, y) & is_a(y, z) -> proper_ancestor(x, z))
).
```

Cycles are forbidden (proper ancestor is irreflexive)

```tlog
all e: ElementID, p: ElementID | proper_ancestor(e, p) -> e != p.
```

```tlog
test_case(
  "cycle",
  given(that(is_a(A,B),is_a(B,C),is_a(C,A))),
  expect(that(not satisfiable()))
).
```

```tlog
pred ancestor(element: ElementID, parent: ElementID).

all e: ElementID, p: ElementID | proper_ancestor(e, p) -> ancestor(e, p).
```

### Slots

```tlog
pred class_slot(cls: ElementID, slot: SlotID).
```

Constraints.

TODO: Any

```tlog
pred class_slot_range(cls: ClassID, slot: SlotID, element: ElementID).
pred class_slot_multivalued(cls: ClassID, slot: SlotID).
pred class_slot_required(cls: ClassID, slot: SlotID).
pred class_slot_multivalued(cls: ClassID, slot: SlotID).
```

## Schema Closure And Validation

These rules operate on reified LinkML schema/TBox facts such as
`class_definition/1`, `slot_definition/1`, and `class_slot/2`. This layer is
intended to be compiled directly to clingo and materialized before ABox rules
are generated.

```tlog
pred attribute(cls: ElementID, slot: SlotID).
pred slot_usage(cls: ElementID, slot: SlotID).
pred slot_range(slot: SlotID, range: ElementID).
pred slot_required(slot: SlotID).
pred slot_required_false(slot: SlotID).
pred slot_multivalued(slot: SlotID).
pred slot_multivalued_false(slot: SlotID).
pred slot_minimum_cardinality(slot: SlotID, count: Count).
pred slot_maximum_cardinality(slot: SlotID, count: Count).
pred slot_exact_cardinality(slot: SlotID, count: Count).
pred slot_usage_range(cls: ElementID, slot: SlotID, range: ElementID).
pred slot_usage_required(cls: ElementID, slot: SlotID).
pred slot_usage_required_false(cls: ElementID, slot: SlotID).
pred slot_usage_multivalued(cls: ElementID, slot: SlotID).
pred slot_usage_multivalued_false(cls: ElementID, slot: SlotID).
pred slot_usage_minimum_cardinality(cls: ElementID, slot: SlotID, count: Count).
pred slot_usage_maximum_cardinality(cls: ElementID, slot: SlotID, count: Count).
pred slot_usage_exact_cardinality(cls: ElementID, slot: SlotID, count: Count).

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

### Element Closure And Schema Validity

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

### Slot Defaults And Overrides

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

### Cardinality Normalization

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


## LinkML ABox Definitions

### Instances

```tlog
type Node: str.   ## conventions: i, j, k, ...

/// Example: I("/persons/p1").
pred I(inst: Node).
```

### Direct Types (Elements)

```tlog
/// Example: DirectInstantiation(my:Person, p1Loc).
/// Example: DirectInstantiation(linkml:integer, "v.int:22").
/// Note p1Loc is not the same as the ID, if it has an identifier
pred DirectInstantiation(el: ElementID, inst: Node).
```

Every instance is an instance of at most one element

```tlog
all i: Node, e1: ElementID, e2: ElementID | DirectInstantiation(e1, i), DirectInstantiation(e2, i) -> e1 = e2.
```

### Inferred Types

```tlog
pred EntailedInstantiation(el: ElementID, inst: Node).

all i, e | DirectInstantiation(e, i) -> EntailedInstantiation(e, i).
all i, e, p | parent(e, p) & EntailedInstantiation(e, i) -> EntailedInstantiation(p, i).
```

### Slot Values

```tlog
/// Example:  DirectAssertion(my:age, p1Loc, "v.int:22")
pred  DirectAssertion(slot: SlotID, inst: Node, valLoc: Node).

pred  EntailedAssertion(slot: SlotID, inst: Node, valLoc: Node).
all s, i, v | DirectAssertion(s, i, v) -> EntailedAssertion(s, i, v).
all s, s2, i, v | DirectAssertion(s, i, v), ancestor(s, s2) -> EntailedAssertion(s2, i, v).
```

```tlog
/// Example: V_int"v.int:22", 22).
pred V_int(valLoc: Node, val: int).
pred V_float(valLoc: Node, val: float).
pred V_str(valLoc: Node, val: str).
```

### Any

```tlog
all i | I(i) -> DirectInstantiation("linkml:Any", i).
```

### ABox Rules

#### Ranges

Ranges 

```tlog
all c, s, r | class_slot_range(c, s, r) ->
  (all i, j | EntailedInstantiation(c, i) &  EntailedAssertion(s, i, j)-> EntailedInstantiation(r, j)).
```

TODO: entailed S

```tlog
all c, s | class_slot_required(c, s) ->
  (all i | EntailedInstantiation(c, i) -> (exists j, s2 | ancestor(s2, s) & DirectAssertion(s2, i, j))).
```
