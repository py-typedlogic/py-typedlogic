from dataclasses import dataclass

from pydantic import BaseModel
from typedlogic import FactMixin, axiom, gen1

NameType = str


@dataclass
class PersonAge(BaseModel, FactMixin):
    name: NameType
    age: int


@dataclass
class SameAge(BaseModel, FactMixin):
    name1: NameType
    name2: NameType


@axiom
def facts():
    assert PersonAge(name="Alice", age=25)
    assert PersonAge(name="Bob", age=30)
    assert PersonAge(name="Ciara", age=30)


@axiom
def axioms(name1: NameType, name2: NameType):
    if any(PersonAge(name=name1, age=age) & PersonAge(name=name2, age=age) for age in gen1(int)):
        assert SameAge(name1=name1, name2=name2)
