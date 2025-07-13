from dataclasses import dataclass
from enum import Enum, IntEnum

from typedlogic import FactMixin
from typedlogic.decorators import predicate, axiom


class AgeCategory(Enum):
    YOUNG = "young"
    MIDDLE_AGED = "middle_aged"
    OLD = "old"

class LivingStatus(IntEnum):
    DEAD = 0
    ALIVE = 1
    UNKNOWN = 99

@dataclass
class Person(FactMixin):
    name: str
    age: int
    living_status: LivingStatus

@dataclass
class PersonHasAgeCategory(FactMixin):
    person: str
    age_category: AgeCategory

@dataclass
class IsAlive(FactMixin):
    person: str

@axiom
def person_has_age_category(p: str, age: int, age_category: AgeCategory, living_status: LivingStatus):
    if Person(p, age, living_status) and age > 44 and age < 65:
        assert PersonHasAgeCategory(p, AgeCategory.MIDDLE_AGED)
    if Person(p, age, living_status) and age > 64:
        assert PersonHasAgeCategory(p, AgeCategory.OLD)
    if Person(p, age, living_status) and age < 45:
        assert PersonHasAgeCategory(p, AgeCategory.YOUNG)
            
@axiom
def is_alive(p: str, age: int, living_status: LivingStatus):
    assert (Person(p, age, LivingStatus.ALIVE) >> IsAlive(p))

