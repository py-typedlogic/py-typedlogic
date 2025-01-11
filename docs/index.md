# py-typedlogic: Bridging Formal Logic and Typed Python

TypedLogic is a powerful Python package that bridges the gap between formal logic and strongly typed Python code. It allows you to leverage fast logic programming engines like Souffle while specifying your logic in mypy-validated Python code.

=== "links.py"

    ```python
    # links.py
    from pydantic import BaseModel
    from typedlogic import FactMixin, gen2
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

    @axiom
    def reflexivity():
        """No paths back to self"""
        assert not any(Path(source=x, target=x, hops=d) for x, d in gen2(ID, int))
    ```

=== "run.py"

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

=== "stdout"

    Output:

    ```python
    Path(source='CA', target='OR', hops=1)
    Path(source='OR', target='WA', hops=1)
    Path(source='CA', target='WA', hops=2)
    ```

=== "Semantics"

    To convert the Python code to first-order logic, use the CLI:

    `typedlogic convert links.py -t fol`

    Output:

    ```
    ∀[x:ID y:ID]. Link(x, y) → Path(x, y, 1)
    ∀[x:ID y:ID z:ID d1:int d2:int]. Path(x, y, d1) ∧ Path(y, z, d2) → Path(x, z, d1+d2)
    ¬∃[x:ID d:int]. Path(x, x, d)
    ```

## Key Features

- Write logical axioms and rules using familiar Python syntax
- Benefit from strong typing and mypy validation
- Integration with multiple solvers and logic engines, including Z3 and Souffle
- Compatible with popular Python validation libraries like Pydantic

## Installation

Install TypedLogic using pip:

```bash
pip install typedlogic
```

With all extras pre-installed:

```bash
pip install typedlogic[all]
```

You can also use pipx to run the [CLI](cli.md) without installing the package globally:

```bash
pipx run typedlogic --help
```

## Define predicates using Pythonic idioms

Inherit from one of the TypedLogic base models to add semantics to your data model. For Pydantic:

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

Once you have defined your data model predicates, you can specify logical axioms directly in Python:

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

Use any of the existing solvers to perform reasoning:

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

outputs:

```
Path(source='CA', target='OR')
Path(source='OR', target='WA')
Path(source='CA', target='WA')
```

