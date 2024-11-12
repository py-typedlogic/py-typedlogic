from dataclasses import dataclass

from typedlogic import FactMixin, axiom
from typedlogic.extensions.probabilistic import probability


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
    """a win"""


@axiom
def win(c: str):
    if Heads(c):
        assert Win()


@axiom
def flip_probs(c: str):
    assert probability(Coin(c) >> Heads(c)) == 0.4
    assert probability(Coin(c) >> Tails(c)) == 0.6
