
from paths.model import Link, Path, ID
from typedlogic.decorators import axiom

@axiom
def link_implies_path(x: ID, y: ID):
    """
    The presence of a link implies the existence of a (one-hop) path.
    """
    if Link(source=x, target=y):
        assert Path(source=x, target=y)

@axiom
def transitivity(x: ID, y: ID, z: ID):
    """
    If there is a path from x to y and a path from y to z,
    then there is a path from x to z.
    """
    if Path(source=x, target=y) and Path(source=y, target=z):
        assert Path(source=x, target=z)
