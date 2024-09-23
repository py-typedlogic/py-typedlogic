"""
Note: requires pydantic
"""
from decimal import Decimal
from typing import NewType, Union

from pydantic import BaseModel
from typedlogic import FactMixin, axiom, gen1, goal

# Types
PosInt = int
Thing = Union[str, PosInt]

Age = Union[int, Decimal]

# Constant
AGE_THRESHOLD = 18

class PersonWithAge(BaseModel, FactMixin):
    name: Thing
    age: Age


class Adult(BaseModel, FactMixin):
    name: Thing


class StageAge(BaseModel, FactMixin):
    stage: Thing
    age: Age

IntOrDecimal = Union[int, Decimal]


class PersonWithAge2(BaseModel, FactMixin):
    name: Thing
    age_in_years: int

ZipCode = NewType('ZipCode', str)


class PersonWithAddress(BaseModel, FactMixin):
    name: Thing
    zip_code: ZipCode


#@axiom
#def facts():
#    assert StageAge(stage="Adult", age=AGE_THRESHOLD)

@axiom
def classifications(name: Thing, age: Age):
    if age >= 18:
        assert Adult(name=name)

@goal
def goals():
    if PersonWithAge(name="Alice", age=25):
        assert Adult(name="Alice")
    if Adult(name="Bob"):
        assert any(PersonWithAge(name="Alice", age=age) for age in gen1(int))
