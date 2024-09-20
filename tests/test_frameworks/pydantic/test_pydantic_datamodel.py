from typedlogic import *
from typedlogic.generators import gen2
from typedlogic.parsers.pyparser import PythonParser

from tests.test_frameworks.pydantic.theorems.pydantic_mortals import *


def test_expressions():
    t1 = AncestorOf(ancestor='x', descendant='y')
    t2 = AncestorOf(ancestor='y', descendant='z')
    assert isinstance(t1, Fact)
    assert isinstance(t2, Fact)
    assert isinstance(t1 & t2, And)
    assert isinstance(t1 | t2, Or)
    assert isinstance(~t1, Not)
    assert isinstance(t1 >> t2, Implies)
    assert isinstance(t2 << t1, Implied)
    assert isinstance(t1 ^ t2, Xor)
    assert isinstance(not_provable(t1), NegationAsFailure)

def test_predicate_definitions():
    pp = PythonParser()
    import tests.test_frameworks.pydantic.theorems.pydantic_mortals as pm
    theory = pp.parse(pm)
    pd_map = {pd.predicate: pd for pd in theory.predicate_definitions}
    for pd in theory.predicate_definitions:
        print(pd)
    assert pd_map["PersonAge"].arguments == {'person': 'str', 'age': 'int'}


def test_gen():
    def _f() -> None:
        for x, y in gen2(str, str):
            _dummy = AncestorOf(ancestor=x, descendant=y)
