# py-typedlogic: Bridging Formal Logic and Typed Python

TypedLogic is a powerful Python package that bridges the gap between formal logic and strongly typed Python code. It allows you to leverage fast logic programming engines like Souffle while specifying your logic in mypy-validated Python code.

=== "Python Logic"

    ```python
    # links.py
    from pydantic import BaseModel
    from typedlogic import FactMixin, Term
    from typedlogic.decorators import axiom
    
    ID = str
    
    class Link(BaseModel, FactMixin):
        """A link between two entities"""
        source: ID
        target: ID
    
    class Path(BaseModel, FactMixin):
        """An N-hop path between two entities"""
        source: ID
        target: ID
        hops: int
    
    @axiom
    def path_from_link(x: ID, y: ID):
        """If there is a link from x to y, there is a path from x to y"""
        assert Link(source=x, target=y) >> Path(source=x, target=y, hops=1)
    
    @axiom
    def transitivity(x: ID, y: ID, z: ID, d1: int, d2: int):
        """Transitivity of paths, plus hop counting"""
        assert ((Path(source=x, target=y, hops=d1) & Path(source=y, target=z, hops=d2)) >>
                Path(source=x, target=z, hops=d1+d2))
    ```

=== "Execution"

    ```python
    from typedlogic.integrations.souffle_solver import SouffleSolver
    from links import Link
    import links as links

    solver = SouffleSolver()
    solver.load(links)  ## source for definitions and axioms
    # Add data
    links = [Link(source='CA', target='OR'), Link(source='OR', target='WA')]
    for link in links:
        solver.add(link)
    model = solver.model()
    for fact in model.iter_retrieve("Path"):
        print(fact)
    ```

=== "Output"

    ```plaintext
    Path(source='CA', target='OR', hops=1)
    Path(source='OR', target='WA', hops=1)
    Path(source='CA', target='WA', hops=2)
    ```


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

## Installation

Install TypedLogic using pip:

```bash
pip install typedlogic
```

With all extras pre-installed:

```bash
pip install typedlogic[all]
```

## Define predicates using Pythonic idioms

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

## Specify logical axioms directly in Python

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

## Performing reasoning from within Python

```python
from typedlogic.integrations.snakelogic import SnakeSolver

solver = SnakeSolver()
solver.load("links.py")  ## source for definitions and axioms
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

## Next Steps

- Explore the [Core Concepts](concepts/index) to understand the fundamental ideas behind TypedLogic
- Check out the [API Reference](api_reference.md) for detailed information on available classes and functions
- See [Advanced Usage](advanced_usage.md) for more complex examples and techniques
