from __future__ import annotations

from typedlogic.decorators import predicate
from typedlogic.integrations.frameworks.owldl import (
    ObjectIntersectionOf,
    ObjectSomeValuesFrom,
    PropertyExpressionChain,
    Thing,
    TopObjectProperty,
)


@predicate
class Person(Thing):
    """A person is a thing."""

    disjoint_union_of = ["Man", "Woman"]

@predicate
class Man(Person):
    pass

@predicate
class Woman(Person):
    pass

@predicate
class HasDescendant(TopObjectProperty):
    transitive = True
    asymmetric = True
    domain = Person
    range = Person

@predicate
class HasChild(HasDescendant):
    range = Person

@predicate
class HasAncestor(TopObjectProperty):
    inverse_of = HasDescendant

@predicate
class HasParent(HasAncestor):
    inverse_of = HasChild

@predicate
class HasGrandchild(HasDescendant):
    subproperty_chain = PropertyExpressionChain(HasChild, HasChild)

@predicate
class Parent(Person):
    """A parent is a person who has a child."""

    equivalent_to = ObjectIntersectionOf(Person, ObjectSomeValuesFrom(HasChild, Thing))

@predicate
class Father(Person):
    equivalent_to = ObjectIntersectionOf(Parent, Man)
