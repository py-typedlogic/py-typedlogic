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
    assert (Path(source=x, target=y, hops=d1) & Path(source=y, target=z, hops=d2)) >> Path(
        source=x, target=z, hops=d1 + d2
    )


@axiom
def reflexivity():
    """No paths back to self"""
    assert not any(Path(source=x, target=x, hops=d) for x, d in gen2(ID, int))
