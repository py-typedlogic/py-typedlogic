from pydantic import BaseModel
from typedlogic import FactMixin
from typedlogic.decorators import axiom

ID = str

class Link(BaseModel, FactMixin):
    source: ID
    target: ID

class Path(Link):
    pass

@axiom
def transitivity(x: ID, y: ID, z: ID):
    assert (Path(source=x, target=y) & Path(source=y, target=z)) >> Path(source=x, target=z)
