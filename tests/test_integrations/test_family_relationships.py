import pytest
from typedlogic.integrations.solvers.z3 import Z3Solver
from typedlogic.profiles import ClosedWorld

import tests.theorems.family_relationships as fr

@pytest.mark.parametrize("solver_class", [Z3Solver])
def test_family_ancestor_relationships(solver_class):
    """Test family ancestor relationships."""
    solver = solver_class()
    solver.assume_closed_world = True
    
    # Load the family relationships module
    solver.load(fr)
    
    # Check that the model is satisfiable
    result = solver.check()
    assert result.satisfiable is True
    
    # Get the model
    model = solver.model()
    assert model is not None
    
    # Print the model facts for debugging
    print("\nFamily Relationships Model (Z3):")
    for term in sorted(str(t) for t in model.ground_terms):
        print(f"  {term}")
    
    # Test assertions
    assert solver.prove(fr.Ancestor(ancestor="John", descendant="Charlie"))
    assert solver.prove(fr.Ancestor(ancestor="Mary", descendant="Charlie"))
    assert solver.prove(fr.Ancestor(ancestor="Mary", descendant="Emma"))
    assert solver.prove(fr.Sibling(person1="Emma", person2="Charlie"))
    assert solver.prove(fr.Sibling(person1="Charlie", person2="Emma"))
    
    # Test negative assertions (parent relationships)
    assert solver.prove(fr.ParentOf(parent="John", child="Bob"))
    assert solver.prove(fr.ParentOf(parent="Mary", child="Bob"))
    assert solver.prove(fr.ParentOf(parent="Mary", child="Alice"))
    
    # Test additional ancestor relationships through transitivity
    assert solver.prove(fr.Ancestor(ancestor="John", descendant="Emma"))
    assert solver.prove(fr.Ancestor(ancestor="Mary", descendant="Sophia"))
    
    # Verify class hierarchy
    male_bob = solver.prove(fr.Male(name="Bob"))
    assert male_bob
    
    female_mary = solver.prove(fr.Female(name="Mary"))
    assert female_mary