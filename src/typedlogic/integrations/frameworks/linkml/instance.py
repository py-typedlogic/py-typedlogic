"""
LinkML instance model, layered on top of jsonlog.

Example:

    >>> facts = [
    ... Instance("/persons/1/"),
    ... ]

"""
from typing import Any, Iterator
from dataclasses import dataclass

from typedlogic import axiom, gen1, gen3
from typedlogic.datamodel import CardinalityConstraint, Term, Sentence, Variable
from typedlogic.integrations.frameworks.linkml.meta import *
from typedlogic.integrations.frameworks.linkml.meta_axioms import Disjoint
from typedlogic.theories.jsonlog.jsonlog import *


@dataclass(frozen=True)
class Instance(Fact):
    """
    An instance of a ClassDefinition, TypeDefinition, EnumDefinition, Literal (Terminal), or Collection
    """

    __alias__ = "I"

    id: PointerID


@dataclass(frozen=True)
class CollectionPointer(Fact):
    """
    An instance of a list or dict collection
    """

    __alias__ = "I"

    id: PointerID



@dataclass(frozen=True)
class InlinedObject(Fact):
    """
    An instance of a ClassDefinition that is inlined.
    """
    id: PointerID


@axiom
def node_classification_axiom(n: PointerID):
    """
    Axiom that classifies a node as an instance, collection, or inlined object.

    TODO: check if necessary

    :param n:
    :return:
    """
    # note: '^' is exclusive or, so this is true if exactly one of the two is true
    if Pointer(n):
        assert CollectionPointer(n) ^ Instance(n)
    if CollectionPointer(n):
        assert PointerIsArray(n) ^ PointerIsObject(n)


@dataclass(frozen=True)
class PointerType(Fact):
    """
    Maps an instance to a name of a ClassDefinition, TypeDefinition, EnumDefinition

    Examples
    --------
        >>> _ = PointerType("/persons/1/", "Person")
        >>> _ = PointerType("/persons/1/name/", "string")
        >>> _ = PointerType("/persons/1/vital_status/", "VitalStatusEnum")

    Distributes over members; if persons is a list, then this is true if true for all members

        >>> _ = PointerType("/persons/", "Person")

    This refers to the logical type; use in combination with InlinedObject to check whether the
    underlying tree structure is a terminal or an object

        >>> _ = [PointerType("/persons/1/friends/3", "Person"), InlinedObject("/persons/1/friends/3")]

    """

    __alias__ = "T"

    id: PointerID
    element: ElementID


@axiom
def instance_disjoints(i: PointerID, e: ElementID):
    assert TypeDefinition("string")
    if PointerType(i, e) and ClassDefinition(e):
        assert not TypeDefinition(e)


@axiom
def instance_type_entails_instance(i: PointerID, c: ElementID):
    if PointerType(i, c):
        assert Instance(i)
    # if PointerType(i, c):
    #    assert ExactlyOne(ClassDefinition(c), TypeDefinition(c), EnumDefinition(c), PointerIsLiteral(c))


@dataclass(frozen=True)
class ObjectPointerHasIdentifier(Fact):
    id: PointerID
    identifier_value: str


@dataclass(frozen=True)
class LiteralPointerIdentifierReference(Fact):
    id: PointerID
    identifier_value: str

@dataclass(frozen=True)
class ObjectPointerHasPropertyScalarized(Fact):
    """
    Maps an instance to a slot and a value instance

    Examples
    --------
        >>> _ = ObjectPointerHasPropertyScalarized("/persons/1/", "name", "/persons/1/name/")

    Note the last argument is a *reference*, which can be dereferenced to get the value.

        >>> _ = PointerStringValue("/persons/1/name/", "John Doe")

    The association never points to a collection, only members of a collection.

        >>> _ = ObjectPointerHasPropertyScalarized("/", "persons", "/persons/1/")
        >>> _ = ObjectPointerHasPropertyScalarized("/", "persons", "/persons/2/")


    """

    id: PointerID
    slot_name: SlotDefinitionID
    value_pointer: PointerID


@axiom
def scalarized_from_list(i: PointerID, a: ElementID, j: PointerID, m: PointerID, ix: int):
    if ObjectPointerHasProperty(i, a, m) and PointerIsCollection(m) and ArrayPointerHasMember(m, ix, j):
        assert ObjectPointerHasPropertyScalarized(i, a, j)


@axiom
def scalarized_from_dictionary(i: PointerID, a: ElementID, j: PointerID, m: PointerID, k: Property):
    # TODO: lookup identifiers.
    if ObjectPointerHasProperty(i, a, m) and PointerIsCollection(m) and ObjectPointerHasProperty(m, k, j):
        assert ObjectPointerHasPropertyScalarized(i, a, j)


@axiom
def scalarized_from_scalar(
    i: PointerID,
    a: ElementID,
    j: PointerID,
):
    if ObjectPointerHasProperty(i, a, j) and PointerIsScalar(j):
        assert ObjectPointerHasPropertyScalarized(i, a, j)


@dataclass(frozen=True)
class ObjectPointerHasPropertyNormalized(Fact):
    # TODO
    id: PointerID
    slot_name: SlotDefinitionID
    value_pointer: PointerID

@dataclass(frozen=True)
class InstSlotRequired(Fact):
    """
    Holds of ObjectPointerHasPropertyScalarized holds, for any value
    """

    id: PointerID
    slot_name: SlotDefinitionID

    @classmethod
    def rules(cls) -> Iterator[Sentence]:
        i = Variable("I")
        s = Variable("S")
        v = Variable("V")
        yield (
                InstSlotRequired.p(i, s) &
                CardinalityConstraint(
                    None,
                    ObjectPointerHasPropertyScalarized.p(i, s, v),
                    maximum_number=0,
                )
            ) >> False




@dataclass(frozen=True)
class PointerIsCollection(Fact):
    node: PointerID


@dataclass(frozen=True)
class PointerIsScalar(Fact):
    node: PointerID


@axiom
def infer_scalar_or_collection(n: PointerID):
    if PointerIsArray(n):
        assert PointerIsCollection(n)
    if PointerIsLiteral(n):
        assert PointerIsScalar(n)
    if Pointer(n):
        assert PointerIsCollection(n) ^ PointerIsScalar(n)


@axiom
def disjoint_instance_check(inst: PointerID, cls: ElementID, left_parent: ElementID, right_parent: ElementID):
    if Disjoint(left_parent, right_parent):
        assert not (PointerType(inst, left_parent) and PointerType(inst, right_parent))


@axiom
def types():
    # TODO: move these
    assert TypeDefinition("string")
    assert TypeDefinition("integer")
    assert TypeDefinition("float")
    assert TypeDefinition("boolean")
    assert Disjoint("string", "integer")
    assert Disjoint("string", "float")
    assert Disjoint("string", "boolean")
    assert Disjoint("integer", "float")
    assert Disjoint("integer", "boolean")
    assert Disjoint("float", "boolean")

@axiom
def literals(n: PointerID, v: Any):
    if PointerIntValue(n, v):
        assert PointerType(n, "integer")
    if PointerStringValue(n, v):
        assert PointerType(n, "string")
    if PointerFloatValue(n, v):
        assert PointerType(n, "float")
    if PointerBooleanValue(n, v):
        assert PointerType(n, "boolean")


# @goals
# def atom_goals():
#    if ObjectPointerHasPropertyScalarized("/", "persons", "/persons/1/"):
#       assert Instance("/persons/1/")
