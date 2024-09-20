
# Getting Started with TypedLogic

This guide will help you get up and running with TypedLogic quickly.

## Installation

Install TypedLogic using pip:

```bash
pip install "typedlogic[snakelog]"
```

## Basic Usage

First define some basic data structures that you want to reason over. Here we will use Pydantic, but you
can use dataframes or plain python objects (and in the future, SQLModels, SQL Alchemy):

```python
from typedlogic.integrations.frameworks.pydantic import FactBaseModel

ID = str


class Link(FactBaseModel):
    source: ID
    target: ID


class Path(FactBaseModel):
    source: ID
    target: ID
```

These can be used in the standard way in Python:

```python
links = [Link(source='CA', target='OR'), Link(source='OR', target='WA')]
``` 

Now we can define some rules:

```python
from typedlogic.decorators import axiom

@axiom
def link_implies_path(x: ID, y: ID):
    """"For all x, y, if there is a link from x to y, then there is a path from x to y"""
    if Link(source=x, target=y):
        assert Path(source=x, target=y)

@axiom
def transitivity(x: ID, y: ID, z: ID):
    """For all x, y, z, if there is a path from x to y and a path from y to z,
       then there is a path from x to z"""
    if Path(source=x, target=y) and Path(source=y, target=z):
        assert Path(source=x, target=z)
```

Note that these rules are not actually executed in a Python environment, but
they are syntactically well-formed and accurately typed.

Now we can reason over the data. We will use a lightweight pure Python solver called `snakelog` that is easily installed
as an extra:

```python
from typedlogic.integrations.snakelogic import SnakeSolver

solver = SnakeSolver()
solver.load("links.py")
for link in links:
    solver.add(link)
model = solver.model()
for fact in model.iter_retrieve("Path"):
    print(fact)
```

This will print:

```
Path(source='CA', target='OR')
Path(source='OR', target='WA')
Path(source='CA', target='WA')
```

## Satisfiability checking

```python
@axiom
def acyclicity(x: ID, y: ID):
    assert ~(Path(source=x, target=y) and Path(source=y, target=x))
```

Now we can check if the model is satisfiable. We will use the [Z3 solver](...) for this

```python
from typedlogic.integrations.solvers.z3 import Z3Solver

solver = Z3Solver()
solver.load("links_with_acyclicity.py")
for link in links:
    solver.add(link)
# add a link that causes a cycle
solver.add_link(Link(source='WA', target='CA'))
solver.check().satisfiable
```

This will return `False` because the model is not satisfiable.

## Next Steps

- Explore the [Core Concepts](concepts/index) to understand the fundamental ideas behind TypedLogic
- Check out the [API Reference](api_reference.md) for detailed information on available classes and functions
- See [Advanced Usage](advanced_usage.md) for more complex examples and techniques

