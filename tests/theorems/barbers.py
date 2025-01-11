# Example usage
from typing import List

from pydantic import BaseModel
from typedlogic import Fact, FactMixin, axiom, gen1, gen3, goal

NameType = str


class Person(BaseModel, FactMixin):
    name: NameType


class Barber(Person):
    pass

class Shaves(BaseModel, Fact):
    shaver: NameType
    customer: NameType


@axiom
def shaves(shaver: NameType, customer: NameType):
    """
    All persons are mortal
    """
    if Barber(name=shaver) and Person(name=customer) and not Shaves(shaver=customer, customer=customer):
        assert Shaves(shaver=shaver, customer=customer)
