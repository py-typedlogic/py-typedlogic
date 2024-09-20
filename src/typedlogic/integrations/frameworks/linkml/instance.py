from typedlogic import axiom, gen1, gen3
from typedlogic.integrations.frameworks.linkml.meta import *
from typedlogic.integrations.frameworks.linkml.meta_axioms import Disjoint
from typedlogic.theories.jsonlog.jsonlog import *


@dataclass(frozen=True)
class Instance(Fact):
    """
    An instance of a ClassDefinition, TypeDefinition, EnumDefinition, Literal (Terminal), or Collection
    """

    __alias__ = "I"

    id: NodeID

@dataclass(frozen=True)
class CollectionNode(Fact):
    """
    An instance of a list or dict collection
    """

    __alias__ = "I"

    id: NodeID

@dataclass(frozen=True)
class InlinedObject(Fact):
    id: NodeID

@axiom
def node_classification(n: NodeID):
    if Node(n):
        assert CollectionNode(n) ^ Instance(n)
    if CollectionNode(n):
        assert NodeIsList(n) ^ NodeIsObject(n)

@dataclass(frozen=True)
class InstanceMember(Fact):
    __alias__ = "I"

    id: NodeID
    member: NodeID

@axiom
def instance_member():
    assert all(InstanceMember(i, m) for i, ix, m in gen3(NodeID, int, NodeID) if ListNodeHasMember(i, ix, m) and NodeIsMultiValued(i))
    assert all(InstanceMember(i, m) for i, ix, m in gen3(NodeID, Key, NodeID) if ObjectNodeLookup(i, ix, m) and NodeIsMultiValued(i))
    assert all(InstanceMember(i, i) for i in gen1(NodeID) if NodeIsSingleValued(i))

@dataclass(frozen=True)
class InstanceMemberType(Fact):
    """
    Maps an instance to a name of a ClassDefinition, TypeDefinition, EnumDefinition

    Examples
    --------
        >>> _ = InstanceMemberType("/persons/1/", "Person")
        >>> _ = InstanceMemberType("/persons/1/name/", "string")
        >>> _ = InstanceMemberType("/persons/1/vital_status/", "VitalStatusEnum")

    Distributes over members; if persons is a list, then this is true if true for all members

        >>> _ = InstanceMemberType("/persons/", "Person")

    This refers to the logical type; use in combination with InlinedObject to check whether the
    underlying tree structure is a terminal or an object

        >>> _ = [InstanceMemberType("/persons/1/friends/3", "Person"), InlinedObject("/persons/1/friends/3")]


    """

    __alias__ = "T"

    id: NodeID
    element: ElementID

@axiom
def instance_disjoints(i: NodeID, e: ElementID):
    assert TypeDefinition("string")
    if InstanceMemberType(i, e) and ClassDefinition(e):
        assert not TypeDefinition(e)

@axiom
def instance_type_entails_instance(i: NodeID, c: ElementID):
    if InstanceMemberType(i, c):
        assert Instance(i)
    #if InstanceMemberType(i, c):
    #    assert ExactlyOne(ClassDefinition(c), TypeDefinition(c), EnumDefinition(c), NodeIsLiteral(c))

@dataclass(frozen=True)
class Association(Fact):
    """
    Maps an instance to a slot and a value instance

    Examples
    --------
        >>> _ = Association("/persons/1/", "name", "/persons/1/name/")

    Note the last argument is a *reference*, which can be dereferenced to get the value.

        >>> _ = NodeStringValue("/persons/1/name/", "John Doe")

    The association never points to a collection, only memmbers of a collection.

        >>> _ = Association("/", "persons", "/persons/1/")
        >>> _ = Association("/", "persons", "/persons/2/")

    """

    id: NodeID
    slot_name: SlotDefinitionID
    value_instance: NodeID



@axiom
def association_from_list(i: NodeID, a: ElementID, j: NodeID, m: NodeID, ix: int):
    if ObjectNodeLookup(i, a, m) and NodeIsMultiValued(m) and ListNodeHasMember(m, ix, j):
        assert Association(i, a, j)

@axiom
def association_from_object(i: NodeID, a: ElementID, j: NodeID, m: NodeID, k: Key):
    if ObjectNodeLookup(i, a, m) and NodeIsMultiValued(m) and ObjectNodeLookup(m, k, j):
        assert Association(i, a, j)

@axiom
def association_from_scalar(i: NodeID, a: ElementID, j: NodeID,):
    if ObjectNodeLookup(i, a, j) and NodeIsSingleValued(j):
        assert Association(i, a, j)

@dataclass(frozen=True)
class NodeIsMultiValued(Fact):
    node: NodeID

@dataclass(frozen=True)
class NodeIsSingleValued(Fact):
    node: NodeID

@axiom
def multivalued(n: NodeID):
    if NodeIsList(n):
        assert NodeIsMultiValued(n)
    if NodeIsLiteral(n):
        assert NodeIsSingleValued(n)
    if Node(n):
        assert NodeIsMultiValued(n) ^ NodeIsSingleValued(n)

@axiom
def disjoint_instance_check(inst: NodeID, cls: ElementID, left_parent: ElementID, right_parent: ElementID):
    if Disjoint(left_parent, right_parent):
        assert not InstanceMemberType(inst, left_parent) and InstanceMemberType(inst, right_parent)

@axiom
def types():
    # TODO: move these
    assert TypeDefinition("string")

#@goals
#def atom_goals():
#    if Association("/", "persons", "/persons/1/"):
#       assert Instance("/persons/1/")

