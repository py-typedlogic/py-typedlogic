"""
Axioms for the LinkML metamodel.

Note these are all purely tbox-level
"""
from dataclasses import dataclass

from typedlogic import Fact, axiom
from typedlogic.integrations.frameworks.linkml.meta import (
    Attribute,
    ClassDefinition,
    ClassSlot,
    ElementID,
    IsA,
    Mixin,
    SlotDefinition,
    SlotUsage,
)


@dataclass(frozen=True)
class InvalidClassSlot(Fact):
    cls: ElementID
    slot: ElementID


@dataclass(frozen=True)
class Disjoint(Fact):
    lhs: ElementID
    rhs: ElementID


@axiom
def disjoint(lhs: ElementID, rhs: ElementID, parent: ElementID):
    if Parent(lhs, parent) and Parent(rhs, parent) and lhs != rhs:
        assert Disjoint(lhs, rhs)


@axiom
def invalid_class_slot(cls: ElementID, slot: ElementID):
    """
    Closed world assumption rule for marking slots that are not allowed for a class

    :param cls:
    :param slot:
    :return:
    """
    if ClassDefinition(cls) and SlotDefinition(slot) and ~ClassSlot(cls, slot):
        assert InvalidClassSlot(cls, slot)


@dataclass(frozen=True)
class SlotUsageOrAttribute(Fact):
    cls: ElementID
    slot_expression: ElementID


@axiom
def slot_usage_or_attribute(cls: ElementID, slot_expression: ElementID):
    if SlotUsage(cls, slot_expression):
        assert Parent(cls, slot_expression)
    if Attribute(cls, slot_expression):
        assert Parent(cls, slot_expression)


@dataclass(frozen=True)
class Parent(Fact):
    """
    Maps to class.slots
    """

    cls: ElementID
    parent: ElementID


@axiom
def parent(element: ElementID, parent: ElementID):
    if IsA(element, parent):
        assert Parent(element, parent)
    if Mixin(element, parent):
        assert Parent(element, parent)


@axiom
def class_slot(cls: ElementID, slot: ElementID, parent: ElementID):
    if Parent(cls, parent) and ClassSlot(parent, slot):
        assert Parent(cls, slot)
