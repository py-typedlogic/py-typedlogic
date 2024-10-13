# Troubleshooting

This page provides solutions to common issues you might encounter when using TypedLogic.

## Type Checking Errors

**Issue**: MyPy reports type errors in axioms or fact definitions.

**Solution**: 
1. Ensure you're using the latest version of TypedLogic and MyPy.
2. Check that all your fact classes properly inherit from both `BaseModel` and `FactMixin`.
3. Verify that you're using the correct generator functions (`gen1`, `gen2`, etc.) with matching types.

Example of correct usage:
```python
@axiom
def correct_axiom():
    return all(
        Parent(parent=x, child=y) >> Ancestor(ancestor=x, descendant=y)
        for x, y in gen2(str, str)
    )
```

## Solver Not Finding Solutions

**Issue**: The solver fails to find a solution or prove a statement that you believe should be true.

**Solution**:
1. Double-check your axioms and make sure they correctly express the logical relationships you intend.
2. Verify that all necessary facts have been added to the solver.
3. Try using a different solver (e.g., switch from Z3 to Souffle) to see if the issue persists.
4. Add intermediate assertions or print statements to debug the logical flow.

## Performance Issues

**Issue**: Solving takes too long or consumes too much memory.

**Solution**:
1. Simplify your axioms if possible. Complex axioms can lead to exponential growth in the search space.
2. Use more specific types in your fact definitions to reduce the search space.
3. Consider using Souffle for large-scale problems, as it's often more efficient for certain types of logical reasoning.
4. Break down complex queries into smaller, manageable parts.

## Integration Issues

**Issue**: Difficulty integrating TypedLogic with existing projects or libraries.

**Solution**:
1. Ensure all required dependencies are installed and up-to-date.
2. Check for version compatibility between TypedLogic and other libraries you're using (especially Pydantic).
3. Use TypedLogic's built-in integration modules (e.g., `typedlogic.integrations.pydantic`) for smoother interoperability.

## Unexpected Logical Results

**Issue**: The solver produces results that seem logically incorrect.

**Solution**:
1. Review your axioms carefully. Small logical errors can lead to unexpected conclusions.
2. Use the `prove` method to test individual logical statements and isolate the source of the unexpected behavior.
3. Consider the closed-world assumption: the solver only knows what you've explicitly told it or what can be directly inferred from that information.

If you encounter issues not covered here, please check the project's issue tracker on GitHub or reach out to the community for assistance.
