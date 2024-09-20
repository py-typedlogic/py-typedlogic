"""
Assumed pre-processing:

- defaults:
    - if an axiom refers to the metaproperty P of a slot S, then defaults are NOT applied
        - default_range
        - multivalued
        - inlined (false)
"""

from typing import Any, Dict, Iterator, List, Union

from typedlogic import And, Exists, Forall, Implies, Or, PredicateDefinition, Sentence, Term, Variable, Xor
from typedlogic.integrations.frameworks.linkml.instance import (
    Association,
    InlinedObject,
    InstanceMemberType,
    NodeIsMultiValued,
    NodeIsSingleValued,
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

def generate_from_object(obj: SchemaDict) -> Iterator[Sentence]:
    for k, v in obj.items():
        if k == "classes":
            for class_name, class_defn in v.items():
                yield from generate_class_definition(class_name, class_defn)
        elif k == "types":
            for type_name, type_defn in v.items():
                yield from generate_type_definition(type_name, type_defn)
    return

def generate_class_definition(class_name: str, class_defn: Dict) -> Iterator[Sentence]:
    """
    Implements mapping of a class definition to a set of sentences.

    Each class definition is treated as a collection of universally quantified sentences, of the form
    for all i, if i is an instance of class_name, then i satisfies the following conditions <...>

    This also yields tbox sentences for the class definition etc.

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
                    if attr_k == "identifier":
                        yield Identifier(class_name, slot_name)
                for conj in conjunctions_from_slot_expression(inst_var, slot_name, slot_defn):
                    conjs.append(conj)
        if k == "slots":
            for slot_name in v:
                yield ClassSlot(class_name, slot_name)
        if k == "is_a":
            yield IsA(class_name, v)
            yield Forall([inst_var],
                         Implies(Term(InstanceMemberType.__name__, inst_var, class_name),
                                 Term(InstanceMemberType.__name__, inst_var, v)))
        if k == "mixins":
            for v1 in v:
                yield Mixin(class_name, v1)
                yield Forall([inst_var],
                             Implies(Term(InstanceMemberType.__name__, inst_var, class_name),
                                     Term(InstanceMemberType.__name__, inst_var, v1)))
        if k == "tree_root":
            yield TreeRoot(class_name)
            yield InstanceMemberType("/", class_name)
    if conjs:
        yield Forall([inst_var],
                     Implies(Term(InstanceMemberType.__name__, inst_var, class_name),
                             And(*conjs)))
    return

def generate_type_definition(type_name: str, type_defn: Dict) -> Iterator[Sentence]:
    yield TypeDefinition(type_name)
    inst_var = Variable("i")
    conjs: List[Sentence] = []
    for k, v in type_defn.items():
        if k == "typeof":
            yield IsA(type_name, v)
            yield Forall([inst_var],
                         Implies(Term(InstanceMemberType.__name__, inst_var, type_name),
                                 Term(InstanceMemberType.__name__, inst_var, v)))
        if k == "mixins":
            for v1 in v:
                yield Forall([inst_var],
                             Implies(Term(InstanceMemberType.__name__, inst_var, type_name),
                                     Term(InstanceMemberType.__name__, inst_var, v1)))
        #for conj in conjunctions_from_type_expression(inst_var, type_name, type_defn):
        #    conjs.append(conj)
    if conjs:
        yield Forall([inst_var],
                     Implies(Term(InstanceMemberType.__name__, inst_var, type_name),
                             And(*conjs)))
    return


def conjunctions_from_slot_expression(inst_var: Variable, slot_name: str, slot_expr: Dict) -> Iterator[Sentence]:
    """
    Generate a set of conjunctions from a slot expression

    >>> inst_var = Variable("I")
    >>> slot_name = "age"
    >>> slot_expr = {"required": True}
    >>> list(conjunctions_from_slot_expression(inst_var, slot_name, slot_expr))
    [InstanceSlotRequired(I, age)]

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
                yield Exists([val_var], Term(Association.__name__, inst_var, slot_name, val_var))
        #elif k == "identifier":
        #    yield Identifier(class_name, slot_name)
        elif k == "range":
            # assumes pre-processing has decorated the range with the appropriate type
            # TODO: linkml:Any
            yield Forall([val_var], Implies(Term(Association.__name__, inst_var, slot_name, val_var),
                                            Term(InstanceMemberType.__name__, val_var, v)))
        elif k == "multivalued" and v is not None:
            if v is True:
                pred = NodeIsMultiValued.__name__
            else:
                pred = NodeIsSingleValued.__name__
            yield Forall([val_var], Implies(Term(ObjectNodeLookup.__name__, inst_var, slot_name, val_var),
                                            Term(pred, val_var)))
        elif k == "inlined_as_list" and v is True:
            yield Forall([val_var], Implies(Term(ObjectNodeLookup.__name__, inst_var, slot_name, val_var),
                                            Term(NodeIsList.__name__, val_var)))
            yield Forall([val_var], Implies(Term(ObjectNodeLookup.__name__, inst_var, slot_name, val_var),
                                            Term(InlinedObject.__name__, val_var, v)))
        elif k == "inlined" and v is True:
            yield Forall([val_var], Implies(Term(ObjectNodeLookup.__name__, inst_var, slot_name, val_var),
                                            Term(InlinedObject.__name__, val_var, v)))




