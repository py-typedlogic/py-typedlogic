%% Predicate Definitions
% Attribute(cls: str, slot_expression: str)
% ClassDefinition(id: str)
% ClassSlot(cls: str, slot: str)
% IsA(element: str, parent: str)
% Mixin(element: str, parent: str)
% SlotDefinition(id: str)
% SlotUsage(cls: str, slot_expression: str)
% InvalidClassSlot(cls: str, slot: str)
% Disjoint(lhs: str, rhs: str)
% SlotUsageOrAttribute(cls: str, slot_expression: str)
% Parent(cls: str, parent: str)

%% disjoint

disjoint(Lhs, Rhs) :- parent(Lhs, Parent), parent(Rhs, Parent), Lhs != Rhs.

%% invalid_class_slot

invalidclassslot(Cls, Slot) :- classdefinition(Cls), slotdefinition(Slot), \+ (classslot(Cls, Slot)).

%% slot_usage_or_attribute

parent(Cls, Slot_expression) :- slotusage(Cls, Slot_expression).
parent(Cls, Slot_expression) :- attribute(Cls, Slot_expression).

%% parent

parent(Element, Parent) :- isa(Element, Parent).
parent(Element, Parent) :- mixin(Element, Parent).

%% class_slot

parent(Cls, Slot) :- parent(Cls, Parent), classslot(Parent, Slot).