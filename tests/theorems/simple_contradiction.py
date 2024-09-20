from dataclasses import dataclass

from typedlogic import FactMixin, axiom


@dataclass
class Foo(FactMixin):
    v: str


@axiom
def pos():
    assert Foo("bar")

@axiom
def neg():
    assert ~Foo("bar")
