# Example usage
from typing import List, Iterator

from pydantic import BaseModel

from typedlogic import Fact, FactMixin, axiom, gen1, gen3, goal, Variable, Sentence, Term, Implies, Forall

NameType = str


class Person(BaseModel, FactMixin):
    name: NameType


class Mortal(BaseModel, Fact):
    name: NameType

    @classmethod
    def rules(cls) -> Iterator[Sentence]:
        x = Variable("x")
        yield Person.p(name=x) >> Mortal.p(name=x)


class AncestorOf(BaseModel, Fact):
    ancestor: NameType
    descendant: NameType

    @classmethod
    def rules(cls) -> Iterator[Sentence]:
        x, y, z = Variable.create("x y z")
        yield Forall(
            [x, y, z],
                Implies(
                    AncestorOf.p(ancestor=x, descendant=y) & AncestorOf.p(ancestor=y, descendant=z),
                    AncestorOf.p(ancestor=x, descendant=z),
                )
        )
        yield ~ (AncestorOf.p(ancestor=x, descendant=y) and AncestorOf.p(ancestor=y, descendant=x))



@goal
def check_transitivity():
    assert (AncestorOf(ancestor="p1", descendant="p2") & AncestorOf(ancestor="p2", descendant="p3")) >> AncestorOf(
        ancestor="p1", descendant="p3"
    )
