from dataclasses import dataclass

from typedlogic import FactMixin, axiom


@dataclass
class Coin(FactMixin):
    id: str


@dataclass
class Heads(FactMixin):
    id: str


@dataclass
class Tails(FactMixin):
    id: str


@dataclass
class Win(FactMixin):
    """a win; unary predicate"""


@axiom
def win_heads(c: str):
    return Heads(c) >> Win()
