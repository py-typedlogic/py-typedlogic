# Advanced Usage

This section covers more advanced topics and techniques for using TypedLogic effectively.

## Working with Multiple Solvers

TypedLogic supports multiple solvers, allowing you to choose the best tool for your specific use case. Here's an example of using both Z3 and Souffle solvers:

```python
from typedlogic.integrations.solvers.z3 import Z3Solver
from typedlogic.integrations.solvers.souffle import SouffleSolver

# Using Z3
z3_solver = Z3Solver()
z3_solver.add(theory)
z3_result = z3_solver.check()

# Using Souffle
souffle_solver = SouffleSolver()
souffle_solver.add(theory)
souffle_result = souffle_solver.check()
```

## Custom Predicate Definitions

For more complex scenarios, you can define custom predicates with specific argument types:

```python
from typedlogic import PredicateDefinition

custom_predicate = PredicateDefinition(
    predicate="ComplexRelation",
    arguments={
        "arg1": str,
        "arg2": int,
        "arg3": float
    }
)

theory.add(custom_predicate)
```

## Integrating with Pydantic

TypedLogic seamlessly integrates with Pydantic for robust data validation:

```python
from pydantic import BaseModel, Field
from typedlogic import FactMixin

class ComplexFact(BaseModel, FactMixin):
    name: str
    age: int = Field(..., ge=0, le=150)
    scores: List[float] = Field(..., min_items=1, max_items=5)

# This fact will be validated according to the Pydantic rules
valid_fact = ComplexFact(name="Alice", age=30, scores=[85.5, 92.0, 78.5])
```

## Handling Negation and Existential Quantification

TypedLogic supports negation and existential quantification in axioms:

```python
from typedlogic import axiom, gen1, Exists

@axiom
def unique_parent():
    return all(
        ~Exists(["y"], Parent(parent="y", child=x) & (y != z))
        for x, z in gen2(str, str)
        if Parent(parent=z, child=x)
    )
```

These advanced techniques allow you to express complex logical relationships and constraints in your TypedLogic-based systems.

