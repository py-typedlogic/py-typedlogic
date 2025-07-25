%% Predicate Definitions
% Element(id: str)
% ClassDefinition(id: str)
% TypeDefinition(id: str)
% EnumDefinition(id: str)
% SlotDefinition(id: str)
% SchemaDefinition(id: str)
% TreeRoot(cls: str)
% ClassSlot(cls: str, slot: str)
% Identifier(cls: str, slot_expression: str)
% Multivalued(slot_expression: str)
% Required(slot_expression: str)
% IsA(element: str, parent: str)
% Mixin(element: str, parent: str)
% Attribute(cls: str, slot_expression: str)
% SlotUsage(cls: str, slot_expression: str)

%% Sentences

element(Id) :- classdefinition(Id).

%% Sentences

element(Id) :- typedefinition(Id).

%% Sentences

element(Id) :- enumdefinition(Id).

%% Sentences

element(Id) :- slotdefinition(Id).

%% Sentences

element(Id) :- schemadefinition(Id).