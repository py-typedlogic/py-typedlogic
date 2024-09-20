# Example usage
from typing import List

from pydantic import BaseModel
from typedlogic import Fact, FactMixin, axiom, gen1, gen3, goal

NameType = str

class Person(BaseModel, FactMixin):
    name: NameType

class Mortal(BaseModel, Fact):
    name: NameType

    @classmethod
    def axioms(cls) -> List[Fact]:
        """
        TODO: this is not yet used
        """
        return [
            Person(name=x) >> Mortal(name=x)
            for x in gen1(NameType)
        ]

TreeNodeType = str

class AncestorOf(BaseModel, Fact):
    ancestor: TreeNodeType
    descendant: TreeNodeType


@axiom
def all_persons_are_mortal_axiom():
    """
    All persons are mortal
    """
    assert all(
        Person(name=x) >> Mortal(name=x)
        for x in gen1(NameType)
    )

@axiom
def ancestor_transitivity_axiom() -> bool:
    return all(
        AncestorOf(ancestor=x, descendant=y)
        for x, y, z in gen3(TreeNodeType, TreeNodeType, TreeNodeType)
        if AncestorOf(ancestor=x, descendant=z) and AncestorOf(ancestor=z, descendant=y)
    )

# TODO:
@axiom
def acyclicity_axiom(x: TreeNodeType, y: TreeNodeType):
    assert not (AncestorOf(ancestor=x, descendant=y) and AncestorOf(ancestor=y, descendant=x))

@goal
def check_transitivity():
    assert ((AncestorOf(ancestor="p1", descendant="p2") &
             AncestorOf(ancestor="p2", descendant="p3")) >>
            AncestorOf(ancestor="p1", descendant="p3"))
