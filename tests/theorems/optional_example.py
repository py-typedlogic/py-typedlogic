from dataclasses import dataclass
from typing import Optional

from typedlogic import FactMixin
from typedlogic.decorators import axiom

Person = str


@dataclass
class FriendOf(FactMixin):
    """
    Predicate linking two friends.

    Demonstrates the use of optional fields

        >>> fact1 = FriendOf("x", "y", 2020, 2021)
        >>> fact2 = FriendOf("x", "y")

    fact1 entails fact2

    """
    subject: Person
    object: Person
    start_year: Optional[int] = None
    end_year: Optional[int] = None


@dataclass
class FriendPath(FactMixin):
    subject: Person
    object: Person


@axiom
def tr(s: Person, o: Person, y: int):
    assert FriendOf(subject=s, object=o) >> FriendPath(subject=s, object=o)
    assert FriendOf(subject=s, object=o) >> FriendPath(subject=s, object=o)


@axiom
def facts():
    assert FriendOf(subject="Fred", object="Jie", start_year=2000, end_year=2005)
    assert FriendOf(subject="Jie", object="Li")
