from dataclasses import dataclass

from typedlogic import FactMixin, axiom, Term
from typedlogic.extensions.probabilistic import Probability, That


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
def prior_probabilities(c: str):
    assert Probability(0.4, That(Coin(c) >> Heads(c)))
    assert Probability(0.6, That(Coin(c) >> Tails(c)))
