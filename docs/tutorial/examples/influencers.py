from dataclasses import dataclass

from typedlogic import FactMixin, axiom, Term
from typedlogic.extensions.probabilistic import Probability, That, probability

PersonID = str

@dataclass
class Person(FactMixin):
    """
    An instance of a person.
    """
    id: PersonID

@dataclass
class Smokes(FactMixin):
    """
    A person that smokes.
    """
    id: PersonID

@dataclass
class Asthma(FactMixin):
    """
    A person with asthma.
    """
    id: PersonID

@dataclass
class Stress(FactMixin):
    """
    A person with stress.
    """
    id: PersonID

@dataclass
class Friend(FactMixin):
    """
    A relationship between two people where both are friends.
    """
    id: PersonID
    other_id: PersonID

@dataclass
class Influences(FactMixin):
    """
    A relationship between two people where one influences the other.
    """
    id: PersonID
    other_id: PersonID

@axiom
def smoking_from_stress(p: PersonID):
    """
    If a person has stress, they smoke.

    :param p: id of the person
    """
    if Stress(p):
        assert Smokes(p)

@axiom
def smoking_from_influencer(p: PersonID, other: PersonID):
    """
    If a person is influenced by another person, and that person smokes, then the influenced person smokes.

    :param p: id of the person that is entailed to smoke
    :param other: id of the person that influences the person
    """
    if Friend(p, other) and Influences(other, p) and Smokes(other):
        assert Smokes(p)

@axiom
def priors_for_person(p: PersonID):
    """
    Prior probabilities for a person to have stress, or
    for a smoker to have asthma.

    :param p: id of the person
    """
    assert probability(Person(p) >> Stress(p)) == 0.3
    assert probability(Smokes(p) >> Asthma(p)) == 0.4

@axiom
def priors_for_influences(p: PersonID, other: PersonID):
    """
    Prior probability for one person to influence another.
    :param p: id of the influencer
    :param other: id of the influenced
    """
    assert probability((Person(p) and Person(other)) >> Influences(p, other)) == 0.2

