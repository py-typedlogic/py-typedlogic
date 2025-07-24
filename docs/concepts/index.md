
# typed-logic: Bridging Formal Logic and Typed Python

typed-logic is a Python package that allows Python data models to be augmented using formal logical statements, which
are then interpreted by *solvers* which can reason over combinations of programs and data allowing for 
*satisfiability checking*, and the generation of new data.

Currently the solvers supported are:

- [Z3](../integrations/solvers/z3)
- [Souffle](../integrations/solvers/souffle.md)
- [Clingo](../integrations/solvers/clingo)
- [Prover9](../integrations/solvers/prover9)
- [Snakelog](../integrations/solvers/snakelog)
- [ProbLog](../integrations/solvers/problog.md)

With support for more solvers (Vampire, OWL reasoners, etc.) planned.

typed-logic is aimed primarily at software developers and data modelers who are logic-curious, but don't necessarily have a background
in formal logic. It is especially aimed at Python developers who like to use lightweight ways of ensuring program and data correctness,
such as Pydantic for data and mypy for type checking of programs. 

## Key Features

- Write logical axioms and rules using familiar Python syntax
- Benefit from strong typing and mypy validation
- Seamless integration with logic programming engines
- Support for various solvers, including Z3 and Souffle
- Compatible with popular Python libraries like Pydantic

## Why TypedLogic?

TypedLogic combines the best of both worlds: the expressiveness and familiarity of Python with the power of formal logic and fast logic programming engines. This unique approach allows developers to:

1. Write more maintainable and less error-prone logical rules
2. Catch type-related errors early in the development process
3. Seamlessly integrate logical reasoning into existing Python projects
4. Leverage the performance of specialized logic engines without sacrificing the Python ecosystem

Get started with TypedLogic and experience a new way of combining logic programming with strongly typed Python!

# Core Concepts

TypedLogic is built around several core concepts that blend logical programming with typed Python. Understanding these concepts is crucial for effectively using the library.

## Use Python idioms to define your data structures

Facts are the basic units of information in TypedLogic. They are represented as Python classes that inherit from both `pydantic.BaseModel` and `FactMixin`. This approach allows you to define strongly-typed facts with automatic validation.

Example:

```python
from pydantic import BaseModel
from typedlogic import FactMixin

PersonID = str
PetID = str

class Person(BaseModel, FactMixin):
    name: PersonID
    
class PersonAge(BaseModel, FactMixin):
    name: PersonID
    age: int

class Pet(BaseModel, FactMixin):
    name: PetID

class PetSpecies(BaseModel, FactMixin):
    name: PetID
    species: str
    
class OwnsPet(BaseModel, FactMixin):
    person: PersonID
    pet: PetID
```

Note in many logic frameworks these definitions don't have a direct translation, but in sorted logics, these
may correspond to [predicate definitions](datamodel).

## Axioms

Axioms are logical rules or statements that define relationships between facts. In TypedLogic, axioms are defined using Python 
functions [decorated](decorators) with `@axiom`.

Example:

```python
from typedlogic.decorators import axiom

@axiom
def constraints(person: PersonID, pet: PetID):
    if OwnsPet(person=person, pet=pet):
        assert Person(name=person) and Pet(name=pet)
```

Note that the Python code in the function definition is **never executed**. The code must be in a [subset of python](../conversion/parsers/python/) that is translated to logic statements.

You can also derive new facts from axioms:

```python
class SameOwner(BaseModel, FactMixin):
    pet1: PetID
    pet2: PetID

from typedlogic.decorators import axiom

@axiom
def entail_same_owner(person: PersonID, pet1: PetID, pet2: PetID):
    if OwnsPet(person=person, pet=pet1) and OwnsPet(person=person, pet=pet2):
        assert SameOwner(pet1=pet1, pet2=pet2)
```

## Generators

Generators like `gen1`, `gen2`, etc., are used within axioms to create typed placeholders for variables. They help maintain type safety while defining logical rules.

You can use generators in combination with Python `all` and `any` functions to express quantified sentences:

```python
@axiom
def entail_same_owner():
    assert all(SameOwner(pet1=pet1, pet2=pet2)
               for person, pet1, pet2 in gen3(PersonID, PetID, PetID)
               if OwnsPet(person=person, pet=pet1) and OwnsPet(person=person, pet=pet2))
```

See [Generators](generators) for more information.

## Solvers

TypedLogic supports multiple [solvers](../integrations/solvers/), including Z3 and Souffle. Solvers are responsible for reasoning over the facts and axioms to derive new information or check for consistency.

Example (using the [Z3 solver](../integrations/solvers/z3.md) ):

```python
from typedlogic.integrations.solvers.z3 import Z3Solver

solver = Z3Solver()
solver.add(theory)
result = solver.check()
```

## Theories

A [Theory](datamodel/#typedlogic.datamodel.Theory) in TypedLogic is a collection of predicate definitions, facts, and axioms. It represents a complete knowledge base that can be reasoned over.

Example:

```python
from typedlogic import Theory

theory = Theory(
    name="family_relationships",
    predicate_definitions=[...],
    sentence_groups=[...],
)
```

