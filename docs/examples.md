# Examples

This page provides various examples to illustrate the usage of TypedLogic in different scenarios.

## Basic Family Relationships

```python
from typedlogic import FactMixin, axiom, gen2
from pydantic import BaseModel

class Parent(BaseModel, FactMixin):
    parent: str
    child: str

class Ancestor(BaseModel, FactMixin):
    ancestor: str
    descendant: str

@axiom
def parent_is_ancestor():
    return all(
        Parent(parent=x, child=y) >> Ancestor(ancestor=x, descendant=y)
        for x, y in gen2(str, str)
    )

@axiom
def ancestor_transitivity():
    return all(
        (Ancestor(ancestor=x, descendant=y) & Ancestor(ancestor=y, descendant=z))
        >> Ancestor(ancestor=x, descendant=z)
        for x, y, z in gen3(str, str, str)
    )

# Usage
theory = Theory(
    name="family_relationships",
    predicate_definitions=[
        PredicateDefinition("Parent", {"parent": str, "child": str}),
        PredicateDefinition("Ancestor", {"ancestor": str, "descendant": str}),
    ],
    sentence_groups=[SentenceGroup(name="axioms", sentences=[parent_is_ancestor(), ancestor_transitivity()])],
)

solver = Z3Solver()
solver.add(theory)
solver.add_fact(Parent(parent="Alice", child="Bob"))
solver.add_fact(Parent(parent="Bob", child="Charlie"))

result = solver.prove(Ancestor(ancestor="Alice", descendant="Charlie"))
print(f"Alice is an ancestor of Charlie: {result}")
```

## Type Hierarchies

```python
from typedlogic import FactMixin, axiom, gen1
from pydantic import BaseModel

class Animal(BaseModel, FactMixin):
    name: str

class Mammal(Animal):
    pass

class Dog(Mammal):
    breed: str

@axiom
def dogs_are_mammals():
    return all(
        Dog(name=x, breed=y) >> Mammal(name=x)
        for x, y in gen2(str, str)
    )

@axiom
def mammals_are_animals():
    return all(
        Mammal(name=x) >> Animal(name=x)
        for x in gen1(str)
    )

# Usage
theory = Theory(
    name="animal_hierarchy",
    predicate_definitions=[
        PredicateDefinition("Animal", {"name": str}),
        PredicateDefinition("Mammal", {"name": str}),
        PredicateDefinition("Dog", {"name": str, "breed": str}),
    ],
    sentence_groups=[SentenceGroup(name="axioms", sentences=[dogs_are_mammals(), mammals_are_animals()])],
)

solver = Z3Solver()
solver.add(theory)
solver.add_fact(Dog(name="Buddy", breed="Labrador"))

result = solver.prove(Animal(name="Buddy"))
print(f"Buddy is an animal: {result}")
```

These examples demonstrate how to use TypedLogic to model relationships and hierarchies, define axioms, and perform logical reasoning. You can expand on these examples to create more complex logical systems tailored to your specific use cases.

