from dataclasses import dataclass

from typedlogic import FactMixin, axiom

Thing = str


@dataclass
class Likes(FactMixin):
    subject: Thing
    object: Thing


@dataclass
class Person(FactMixin):
    name: Thing


@dataclass
class Animal(FactMixin):
    name: Thing
    species: Thing


@axiom
def persons():
    assert Person(name="Fred")
    assert Person(name="Jie")


@axiom
def animals():
    assert Animal(name="corky", species="cat")
    assert Animal(name="fido", species="dog")


@axiom
def animal_preferences(x: Thing, species: Thing):
    """
    Record animal preferences.

    :param x:
    :param species:
    :return:
    """
    # All animals like Fred
    if Animal(name=x, species=species):
        assert Likes(subject=x, object="Fred")
    # All cats like Jie
    if Animal(name=x, species="cat"):
        assert Likes(subject=x, object="Jie")
    # Fred doesn't like dogs
    if Animal(name=x, species="dog"):
        assert ~Likes(subject="Fred", object=x)
        # assert Likes(subject="Akira", object=x)
