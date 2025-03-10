from pydantic import BaseModel
from typedlogic import FactMixin
from typedlogic.decorators import axiom

ID = str


class Link(BaseModel, FactMixin):
    source: ID
    target: ID


class Path(BaseModel, FactMixin):
    source: ID
    target: ID
    hops: int


@axiom
def path_from_link(x: ID, y: ID):
    assert Link(source=x, target=y) >> Path(source=x, target=y, hops=1)


@axiom
def transitivity(x: ID, y: ID, z: ID, d1: int, d2: int):
    assert (Path(source=x, target=y, hops=d1) & Path(source=y, target=z, hops=d2)) >> Path(
        source=x, target=z, hops=d1 + d2
    )
