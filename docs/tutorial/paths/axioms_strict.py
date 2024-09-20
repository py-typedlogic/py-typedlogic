
from paths.model import Link, Path, ID
from typedlogic.decorators import axiom

@axiom
def link_implies_path(x: ID, y: ID):
    """Same as before"""
    if Link(source=x, target=y):
        assert Path(source=x, target=y)

@axiom
def transitivity(x: ID, y: ID, z: ID):
    """Same as before"""
    if Path(source=x, target=y) and Path(source=y, target=z):
        assert Path(source=x, target=z)

@axiom
def acyclicity(x: ID, y: ID):
    """No path should lead from a node back to itself"""
    assert not (Path(source=y, target=x) and Path(source=x, target=y))