# Example usage

from pydantic import BaseModel
from typedlogic import Fact, FactMixin, axiom

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
    A barber shaves everyone who does not shave themselves.

    Uses classical negation (``~``): the paradox is a classical-FOL one, and under
    negation-as-failure it would not arise.
    """
    if Barber(name=shaver) and Person(name=customer) and ~Shaves(shaver=customer, customer=customer):
        assert Shaves(shaver=shaver, customer=customer)
