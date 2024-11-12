from dataclasses import dataclass

from typedlogic import FactMixin, axiom, Term
from typedlogic.extensions.probabilistic import Probability, That, probability

PersonID = str

@dataclass
class Person(FactMixin):
    id: PersonID

@dataclass
class Smokes(FactMixin):
    id: PersonID

@dataclass
class Asthma(FactMixin):
    id: PersonID

@dataclass
class Stress(FactMixin):
    id: PersonID

@dataclass
class Friend(FactMixin):
    id: PersonID
    other_id: PersonID

@dataclass
class Influences(FactMixin):
    id: PersonID
    other_id: PersonID

@axiom
def smoking_from_stress(p: PersonID):
    if Stress(p):
        assert Smokes(p)

@axiom
def smoking_from_influencer(p: PersonID, other: PersonID):
    if Friend(p, other) and Influences(other, p) and Smokes(other):
        assert Smokes(p)

@axiom
def priors_for_person(p: PersonID):
    assert probability(Person(p) >> Stress(p)) == 0.3
    assert probability(Smokes(p) >> Asthma(p)) == 0.4

@axiom
def priors_for_influences(p: PersonID, other: PersonID):
    assert probability((Person(p) and Person(other)) >> Influences(p, other)) == 0.2


@axiom
def facts():
    assert Person("angelika")
    assert Person("joris")
    assert Person("jonas")
    assert Person("dimitar")
    assert Friend("joris", "jonas")
    assert Friend("joris", "angelika")
    assert Friend("joris", "dimitar")
    assert Friend("angelika", "jonas")