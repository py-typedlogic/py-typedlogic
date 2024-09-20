from dataclasses import dataclass

from typedlogic import Fact

ElementID = str
ClassDefinitionID = ElementID
SlotDefinitionID = ElementID

@dataclass(frozen=True)
class Element(Fact):
    id: ElementID

@dataclass(frozen=True)
class ClassDefinition(Element):
    pass

@dataclass(frozen=True)
class TypeDefinition(Element):
    pass

@dataclass(frozen=True)
class EnumDefinition(Element):
    pass

@dataclass(frozen=True)
class SlotDefinition(Element):
    pass

@dataclass(frozen=True)
class SchemaDefinition(Element):
    pass

@dataclass(frozen=True)
class TreeRoot(Fact):
    cls: ElementID

@dataclass(frozen=True)
class ClassSlot(Fact):
    """
    Maps to class.slots
    """

    cls: ElementID
    slot: ElementID

@dataclass(frozen=True)
class Identifier(Fact):
    cls: ElementID
    slot_expression: ElementID

@dataclass(frozen=True)
class Multivalued(Fact):
    slot_expression: ElementID

@dataclass(frozen=True)
class Required(Fact):
    slot_expression: ElementID

@dataclass(frozen=True)
class IsA(Fact):
    element: ElementID
    parent: ElementID

@dataclass(frozen=True)
class Mixin(Fact):
    element: ElementID
    parent: ElementID

@dataclass(frozen=True)
class Attribute(Fact):
    cls: ElementID
    slot_expression: ElementID

@dataclass(frozen=True)
class SlotUsage(Fact):
    # instead make specific?
    cls: ElementID
    slot_expression: ElementID
