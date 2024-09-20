from typedlogic.registry import get_solver

# py-typedlogic: Pythonic logic for your data models.

Define logical predicates directly in Python as Pydantic, dataclasses, SQLModel, or plain python objects:

```python
# links.py
from pydantic import BaseModel
from typedlogic import FactMixin, Term

ID = str

class Link(BaseModel, FactMixin):
    """A link between two entities"""
    source: ID
    target: ID

class Path(BaseModel, FactMixin):
    """An N-hop path between two entities, consisting of one or more links"""
    source: ID
    target: ID
    hops: int
```

This data model has two classes, `Link` and `Path`. These also correspond to *predicate signatures*
in a logical theory.

You can use this to create objects (ground terms, in logic terms) using normal Python code:

```python
links = []
for source, target in [('CA', 'OR'), ('OR', 'WA')]:
   links.append(link)
```

Define logical *constraints* or *rules* using Python syntax:
 
```python
from typedlogic.decorators import axiom

@axiom
def path_from_link(x: ID, y: ID):
    """If there is a link from x to y, there is a path from x to y"""
    if Link(source=x, target=y):
        assert Path(source=x, target=y, hops=1)

@axiom
def transitivity(x: ID, y: ID, z: ID, d1: int, d2: int):
    """Transitivity of paths, plus hop counting"""
    if Path(source=x, target=y, hops=d1) and Path(source=y, target=z, hops=d2):
        assert Path(source=x, target=z, hops=d1+d2)
```

Use a solver to infer new facts:

```python
from typedlogic.registry import get_solver
from links import Link

solver = get_solver("clingo")
solver.load(links) 
links = [Link(source='CA', target='OR'), Link(source='OR', target='WA')]
for link in links:
    solver.add(link)
model = solver.model()
for fact in model.iter_retrieve("Path"):
    print(fact)
```

prints:

```
Path(source='CA', target='OR')
Path(source='OR', target='WA')
Path(source='CA', target='WA')
```

## Key Features

- Write logical axioms and rules using Python syntax (but can also be used independently of this)
- Benefit from strong typing and mypy validation
- Integration with multiple FOL solvers and logic programming engines
- Interconversion between multiple syntaxes for FOL, Rules, and logical models
- Integration with OWL-DL
- Integration with Python libraries like Pydantic
- Command Line and Python interfaces

## Installation

Install TypedLogic using pip:

```bash
pip install "typedlogic"
```

## Next Steps

- Consult the main docs 
