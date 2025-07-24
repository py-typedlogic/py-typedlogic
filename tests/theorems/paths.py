from pydantic import BaseModel
from typedlogic import FactMixin
from typedlogic.decorators import axiom

ID = str


class Path(BaseModel, FactMixin):
    source: ID
    target: ID


class Link(Path):
    pass


@axiom
def transitivity(x: ID, y: ID, z: ID):
    assert (Path(source=x, target=y) & Path(source=y, target=z)) >> Path(source=x, target=z)
