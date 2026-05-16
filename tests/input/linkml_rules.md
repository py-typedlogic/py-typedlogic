# LinkML Rule Expansion Sketch

This document keeps the explanatory prose outside the parsed theory. Only fenced
`tlog` blocks are interpreted by the Markdown wrapper parser.

```tlog
type PointerID: str.
type ElementID: str.

pred pointer_type(id: PointerID, element: ElementID).
pred class_slot(cls: ElementID, slot: str).
pred required(slot: str).
```

The rule block can use symbolic quantifiers when that reads better in prose.

```tlog
/// Required slots must have at least one observed value.
:- pointer_type(i, c), class_slot(c, s), required(s), not has_slot_value(i, s).

∀ i, c | pointer_type(i, c) -> instance(i).

∃ witness | observed(witness).
```
