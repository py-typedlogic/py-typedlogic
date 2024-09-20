from pydantic import BaseModel
from typedlogic import FactMixin, axiom, gen1, goal

Thing = str

AGE_THRESHOLD = 18

class PersonWithAge(BaseModel, FactMixin):
    name: Thing
    age: int


class Adult(BaseModel, FactMixin):
    name: Thing


class StageAge(BaseModel, FactMixin):
    stage: Thing
    age: int


@axiom
def facts():
    assert StageAge(stage="Adult", age=AGE_THRESHOLD)

@axiom
def classifications(name: Thing, age: int):
    if age >= AGE_THRESHOLD:
        assert Adult(name=name)

@goal
def goals():
    if PersonWithAge(name="Alice", age=25):
        assert Adult(name="Alice")
    if Adult(name="Bob"):
        assert any(PersonWithAge(name="Alice", age=age) for age in gen1(int))
