from dataclasses import dataclass

from typedlogic import FactMixin
from typedlogic.decorators import predicate


@predicate
class Person:
    name: str
    age: int


@dataclass
class Animal(FactMixin):
    name: str
