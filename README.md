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

- Write logical axioms and rules using [Python syntax](https://py-typedlogic.github.io/py-typedlogic/tutorial/01-first-program/) 
- Interconvert between different logical formats and formalisms
    - [Compilers](https://py-typedlogic.github.io/py-typedlogic/conversion/compilers/)
    - [Parsers](https://py-typedlogic.github.io/py-typedlogic/conversion/parsers/)
- Benefit from strong typing and mypy validation
- Integration with multiple [FOL solvers](https://py-typedlogic.github.io/py-typedlogic/integrations/solvers/) and logic programming engines
- Integration with [OWL-DL](https://py-typedlogic.github.io/py-typedlogic/integrations/frameworks/owldl/)
- Integration with Python libraries like [Pydantic](https://py-typedlogic.github.io/py-typedlogic/integrations/frameworks/pydantic/)
- [Command Line](https://py-typedlogic.github.io/py-typedlogic/cli/) and Python interfaces

## Installation

Install TypedLogic using pip:

```bash
pip install "typedlogic"
```

## Next Steps

- Consult the [main docs](https://py-typedlogic.github.io/py-typedlogic/) for more information

## Contributing

### Testing with External Dependencies

Some tests require external executables (Prover9, Souffle) that may not be available in all environments. 
The test suite is designed to automatically skip tests that require unavailable dependencies.

When running in CI environments:
- Tests for external solvers are automatically skipped if the dependency is not available
- This allows CI to pass while still testing all available functionality

To install optional dependencies for testing:
- Prover9: Install from your package manager or from source
- Souffle: Install from your package manager or from source

Run tests with:
```bash
poetry run pytest
```
