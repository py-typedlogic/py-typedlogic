"""
Assumed pre-processing:

- defaults:
    - if an axiom refers to the metaproperty P of a slot S, then defaults are NOT applied
        - default_range
        - multivalued
        - inlined (false)

closed-world reasoning for required=True

if we place this on the LHS it doesn't act as a constraint; so we need to treat it the same as range etc
where we have separate disjointness constraints; e.g.

ExpectedAssoc(i, "s") ; ... : - cls(i),

# then

:- ExpectedAssoc(i, s), {...}=0.

"""

from typing import Any, Dict, Iterator, List, Union

from typedlogic import And, Exists, Forall, Implies, Or, PredicateDefinition, Sentence, Term, Variable, Xor, \
    NegationAsFailure
from typedlogic.datamodel import CardinalityConstraint
from typedlogic.integrations.frameworks.linkml.instance import (
    Association,
    InlinedObject,
    InstanceMemberType,
    NodeIsMultiValued,
    NodeIsSingleValued, InstSlotRequired,
)
from typedlogic.integrations.frameworks.linkml.meta import (
    ClassDefinition,
    ClassSlot,
    Identifier,
    IsA,
    Mixin,
    TreeRoot,
    TypeDefinition,
)
from typedlogic.theories.jsonlog.jsonlog import NodeIsList, ObjectNodeLookup

Result = Union[Sentence, PredicateDefinition]

SchemaDict = Dict[str, Any]

def remove_empty_kvs(obj: Any) -> Any:
    """
    Remove empty values from a dictionary.

    :param obj: The dictionary to clean.
    :return: A new dictionary with empty values removed.
    """
    if isinstance(obj, dict):
        return {k: remove_empty_kvs(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [remove_empty_kvs(v) for v in obj]
    return obj


def closed_world_constraint(pre: Sentence, post: Sentence) -> Sentence:
    """
    Generate a closed-world constraint that states if pre is true, then post must also be true.

    Example:

        >>> from typedlogic.datamodel import Term
        >>> closed_world_constraint(Term("P"), Term("Q"))
        Implies(And(P, NegationAsFailure(Q)), Or())

    :param pre: The precondition sentence.
    :param post: The postcondition sentence.
    :return: A sentence representing the closed-world constraint.
    """
    return Implies(And(pre, NegationAsFailure(post)), Or())


def generate_from_object(obj: SchemaDict) -> Iterator[Sentence]:
    """
    Generates logical sentence in the LinkML predicate metamodel based on
    an object/dict representation.

    :param obj:
    :return:
    """
    obj = remove_empty_kvs(obj)
    print(obj)
    for k, v in obj.items():
        if k == "classes":
            for class_name, class_defn in v.items():
                yield from generate_class_definition(class_name, class_defn)
        elif k == "types":
            for type_name, type_defn in v.items():
                yield from generate_type_definition(type_name, type_defn)
        elif k == "slots":
            for slot_name, slot_defn in v.items():
                yield from generate_slot_definition(slot_name, slot_defn)
    # TODO: keep axioms in one place
    v_i = Variable("I")
    v_s = Variable("S")
    v_v = Variable("V")
    assoc = Term(Association.__name__, v_i, v_s, v_v)
    yield Implies(
        And(
            Term(InstSlotRequired.__name__, Variable("i"), Variable("s")),
            CardinalityConstraint(assoc, assoc, maximum_number=0)
        ),
        Or(),
    )
    return

def generate_slot_definition(slot_name: str, slot_defn: Dict) -> Iterator[Sentence]:
    inst_var = Variable("I")
    class_name = Variable("C")
    conjs = []
    for conj in conjunctions_from_slot_expression(inst_var, slot_name, slot_defn):
        conjs.append(conj)
    if conjs:
        yield Forall([inst_var, class_name], Implies(Term(InstanceMemberType.__name__, inst_var, class_name), And(*conjs)))



def generate_class_definition(class_name: str, class_defn: Dict) -> Iterator[Sentence]:
    """
    Maps an individual LinkML class definition to a set of sentences.

    Each class definition is treated as a collection of universally quantified sentences, of the form
    for all i, if i is an instance of class_name, then i satisfies the following conditions <...>

    Simple classes become ground unary terms:

        >>> from typedlogic.compiler import write_sentences
        >>> write_sentences(generate_class_definition("C", {}))
        ClassDefinition('C')

    For constructs such as inheritance, direct translations of the model are provided, in
    addition to horn rules

        >>> write_sentences(generate_class_definition("C", {"is_a": "D"}))
        ClassDefinition('C')
        IsA('C', 'D')
        ∀[I]. InstanceMemberType(I, 'C') → InstanceMemberType(I, 'D')

    i.e. if I instance an instance of C, it's a member of D

    Constraints:

        >>> write_sentences(generate_class_definition("C", {"attributes": {"a1": {"required": True}}}))
        ClassDefinition('C')
        ∀[I]. InstanceMemberType(I, 'C') → InstSlotRequired(I, 'a1')

        >>> write_sentences(generate_class_definition("C", {"attributes": {"a1": {"required": True, "range": "string"}}}))
        ClassDefinition('C')
        ∀[I]. InstanceMemberType(I, 'C') → InstSlotRequired(I, 'a1') ∧ ∀[v]. Association(I, 'a1', v) → InstanceMemberType(v, 'string')

        >>> write_sentences(generate_class_definition("C", {"attributes": {"a1": {"any_of": [{"required": True}, {"range": "string"}]}}}))
        ClassDefinition('C')
        ∀[I]. InstanceMemberType(I, 'C') → (InstSlotRequired(I, 'a1') ∨ ∀[v]. Association(I, 'a1', v) → InstanceMemberType(v, 'string'))

    Ranges:

        >>> write_sentences(generate_class_definition("C", {"attributes": {"a1": {"range": "integer"}}}))
        ClassDefinition('C')
        ∀[I]. InstanceMemberType(I, 'C') → ∀[v]. Association(I, 'a1', v) → InstanceMemberType(v, 'integer')

    Cardinality:

        >>> write_sentences(generate_class_definition("C", {"attributes": {"a1": {"multivalued": False}}}))
        ClassDefinition('C')
        ∀[I]. InstanceMemberType(I, 'C') → ∀[v]. ObjectNodeLookup(I, 'a1', v) → NodeIsSingleValued(v)


    :param class_name:
    :param class_defn:
    :return:
    """
    yield ClassDefinition(class_name)
    inst_var = Variable("I")
    conjs: List[Sentence] = []
    for k, v in class_defn.items():
        if k in ("slot_usage", "attributes"):
            for slot_name, slot_defn in v.items():
                for attr_k, attr_v in slot_defn.items():
                    # special case - not expanded
                    if attr_k == "identifier":
                        yield Identifier(class_name, slot_name)
                for conj in conjunctions_from_slot_expression(inst_var, slot_name, slot_defn):
                    conjs.append(conj)
        if k == "slots":
            for slot_name in v:
                yield ClassSlot(class_name, slot_name)
        if k == "is_a":
            yield IsA(class_name, v)
            yield Forall(
                [inst_var],
                Implies(
                    Term(InstanceMemberType.__name__, inst_var, class_name),
                    Term(InstanceMemberType.__name__, inst_var, v),
                ),
            )
        if k == "mixins":
            for v1 in v:
                yield Mixin(class_name, v1)
                yield Forall(
                    [inst_var],
                    Implies(
                        Term(InstanceMemberType.__name__, inst_var, class_name),
                        Term(InstanceMemberType.__name__, inst_var, v1),
                    ),
                )
        if k == "tree_root":
            yield TreeRoot(class_name)
            yield InstanceMemberType("/", class_name)
    if conjs:
        yield Forall([inst_var], Implies(Term(InstanceMemberType.__name__, inst_var, class_name), And(*conjs)))
    return


def generate_type_definition(type_name: str, type_defn: Dict) -> Iterator[Sentence]:
    """
    Maps an individual LinkML type definition to a set of sentences.

    Each type definition is treated as a collection of universally quantified sentences, of the form
    for all i, if i is an instance of class_name, then i satisfies the following conditions <...>

    Simple classes become ground unary terms:

        >>> from typedlogic.compiler import write_sentences
        >>> write_sentences(generate_type_definition("T", {}))
        TypeDefinition('T')

    For constructs such as inheritance, direct translations of the model are provided, in
    addition to horn rules

        >>> write_sentences(generate_type_definition("T", {"typeof": "U"}))
        TypeDefinition('T')
        IsA('T', 'U')
        ∀[i]. InstanceMemberType(i, 'T') → InstanceMemberType(i, 'U')


    TODO: complete this

    :param type_name:
    :param type_defn:
    :return:
    """
    yield TypeDefinition(type_name)
    inst_var = Variable("i")
    conjs: List[Sentence] = []
    for k, v in type_defn.items():
        if k == "typeof":
            yield IsA(type_name, v)
            yield Forall(
                [inst_var],
                Implies(
                    Term(InstanceMemberType.__name__, inst_var, type_name),
                    Term(InstanceMemberType.__name__, inst_var, v),
                ),
            )
        if k == "mixins":
            for v1 in v:
                yield Forall(
                    [inst_var],
                    Implies(
                        Term(InstanceMemberType.__name__, inst_var, type_name),
                        Term(InstanceMemberType.__name__, inst_var, v1),
                    ),
                )
        # for conj in conjunctions_from_type_expression(inst_var, type_name, type_defn):
        #    conjs.append(conj)
    if conjs:
        yield Forall([inst_var], Implies(Term(InstanceMemberType.__name__, inst_var, type_name), And(*conjs)))
    return


def conjunctions_from_slot_expression(inst_var: Variable, slot_name: str, slot_expr: Dict) -> Iterator[Sentence]:
    """
    Generate a set of conjunctions from a slot expression

        >>> from typedlogic.compiler import write_sentences
        >>> inst_var = Variable("I")
        >>> slot_name = "age"
        >>> slot_expr = {"required": True}
        >>> write_sentences(conjunctions_from_slot_expression(inst_var, slot_name, slot_expr))
        InstSlotRequired(I, 'age')


    :param inst_var:
    :param slot_name:
    :param slot_expr:
    :return:
    """
    val_var = Variable("v")
    assert val_var.name == "v"
    for k, v in slot_expr.items():
        if k == "any_of":
            or_exprs = []
            for sub_expr in v:
                or_exprs.extend(list(conjunctions_from_slot_expression(inst_var, slot_name, sub_expr)))
            yield Or(*or_exprs)
        elif k == "all_of":
            and_exprs = []
            for sub_expr in v:
                and_exprs.extend(list(conjunctions_from_slot_expression(inst_var, slot_name, sub_expr)))
            yield And(*and_exprs)
        elif k == "none_of":
            none_exprs = []
            for sub_expr in v:
                none_exprs.extend(list(conjunctions_from_slot_expression(inst_var, slot_name, sub_expr)))
            if len(none_exprs) == 1:
                yield ~none_exprs[0]
            else:
                yield ~And(*none_exprs)
        elif k == "exactly_one_of":
            or_exprs = []
            for sub_expr in v:
                or_exprs.extend(list(conjunctions_from_slot_expression(inst_var, slot_name, sub_expr)))
            yield Xor(*or_exprs)
        elif k == "required":
            if v:
                yield Term(InstSlotRequired.__name__, inst_var, slot_name)
        # elif k == "identifier":
        #    yield Identifier(class_name, slot_name)
        elif k == "range":
            # assumes pre-processing has decorated the range with the appropriate type
            # TODO: linkml:Any
            if v:
                yield Forall(
                    [val_var],
                    Implies(
                        Term(Association.__name__, inst_var, slot_name, val_var),
                        Term(InstanceMemberType.__name__, val_var, v),
                    ),
                )
        elif k == "multivalued" and v is not None:
            if v is True:
                pred = NodeIsMultiValued.__name__
            else:
                pred = NodeIsSingleValued.__name__
            yield Forall(
                [val_var], Implies(Term(ObjectNodeLookup.__name__, inst_var, slot_name, val_var), Term(pred, val_var))
            )
        elif k == "inlined_as_list" and v is True:
            yield Forall(
                [val_var],
                Implies(
                    Term(ObjectNodeLookup.__name__, inst_var, slot_name, val_var), Term(NodeIsList.__name__, val_var)
                ),
            )
            yield Forall(
                [val_var],
                Implies(
                    Term(ObjectNodeLookup.__name__, inst_var, slot_name, val_var),
                    Term(InlinedObject.__name__, val_var, v),
                ),
            )
        elif k == "inlined" and v is True:
            yield Forall(
                [val_var],
                Implies(
                    Term(ObjectNodeLookup.__name__, inst_var, slot_name, val_var),
                    Term(InlinedObject.__name__, val_var, v),
                ),
            )
