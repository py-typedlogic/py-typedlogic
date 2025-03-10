"""
Example demonstrating class hierarchies and Clingo-style constraints for family relationships.
"""
from dataclasses import dataclass
from typing import Optional

from typedlogic import FactMixin
from typedlogic.decorators import axiom, goal

# Types
PersonName = str


@dataclass
class Person(FactMixin):
    """Base class for all persons."""
    name: PersonName


@dataclass
class Male(Person):
    """A male person."""
    pass


@dataclass
class Female(Person):
    """A female person."""
    pass


@dataclass
class ParentOf(FactMixin):
    """Represents parent-child relationship."""
    parent: PersonName
    child: PersonName


@dataclass
class Sibling(FactMixin):
    """Represents sibling relationship."""
    person1: PersonName
    person2: PersonName


@dataclass
class Ancestor(FactMixin):
    """Represents ancestor relationship."""
    ancestor: PersonName
    descendant: PersonName


@axiom
def example_facts():
    """Define example family members."""
    # Grandparents
    assert Male(name="John")
    assert Female(name="Mary")
    
    # Parents
    assert Male(name="Bob")
    assert Female(name="Alice")
    assert Male(name="Tom")
    
    # Children
    assert Male(name="Charlie")
    assert Female(name="Emma")
    assert Female(name="Sophia")
    
    # Parent relationships
    assert ParentOf(parent="John", child="Bob")
    assert ParentOf(parent="Mary", child="Bob")
    assert ParentOf(parent="Mary", child="Alice")
    
    assert ParentOf(parent="Bob", child="Charlie")
    assert ParentOf(parent="Bob", child="Emma")
    assert ParentOf(parent="Alice", child="Sophia")


@axiom
def parent_child_relationships(p: PersonName, c: PersonName):
    """Define parent-child implications."""
    # A parent of a person is their ancestor
    assert ParentOf(parent=p, child=c) >> Ancestor(ancestor=p, descendant=c)


@axiom
def ancestor_transitivity(a: PersonName, b: PersonName, c: PersonName):
    """Define transitivity of ancestry."""
    # If a is ancestor of b and b is ancestor of c, then a is ancestor of c
    assert (Ancestor(ancestor=a, descendant=b) & Ancestor(ancestor=b, descendant=c)) >> Ancestor(ancestor=a, descendant=c)


@axiom
def sibling_relationships(p1: PersonName, p2: PersonName, parent: PersonName):
    """Define sibling relationships from shared parents."""
    # Two different people with the same parent are siblings
    assert ((ParentOf(parent=parent, child=p1) & 
            ParentOf(parent=parent, child=p2) & 
            (p1 != p2))) >> Sibling(person1=p1, person2=p2)


@axiom
def sibling_symmetry(p1: PersonName, p2: PersonName):
    """Define symmetry of sibling relationship."""
    # If p1 is a sibling of p2, then p2 is a sibling of p1
    assert Sibling(person1=p1, person2=p2) >> Sibling(person1=p2, person2=p1)


@axiom
def sibling_constraints(p1: PersonName, p2: PersonName):
    """Define constraint that a person cannot be their own sibling."""
    assert ~Sibling(person1=p1, person2=p1)


@goal
def grandparent_is_ancestor(x: PersonName):
    """Test that John is an ancestor of Charlie."""
    assert Ancestor(ancestor="John", descendant="Charlie")


@goal
def mary_is_ancestor_of_charlie():
    """Test that Mary is an ancestor of Charlie through Bob."""
    assert Ancestor(ancestor="Mary", descendant="Charlie")


@goal
def emma_and_charlie_are_siblings():
    """Test that Emma and Charlie are siblings."""
    assert Sibling(person1="Emma", person2="Charlie")
    assert Sibling(person1="Charlie", person2="Emma")  # Due to symmetry


@goal
def sophia_not_sibling_of_charlie():
    """Sophia and Charlie have different parents, so they're not siblings."""
    assert ~Sibling(person1="Sophia", person2="Charlie")