

from pydantic import BaseModel
from typedlogic import FactMixin, axiom, gen1, goal

class Thing(BaseModel, FactMixin):
    name: str

class Place(Thing):
    name: str

class Person(Thing):
    name: str
    age: int