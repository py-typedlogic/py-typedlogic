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
all i | I(I) -> DirectInstantiation("linkml:Any", i).
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
all c, s, r | class_slot_required(c, s) ->
  (all i | EntailedInstantiation(c, i) -> (exists j, s2 |  ancestor(s2, s) & DirectAssertion(s, i, j))).
```
