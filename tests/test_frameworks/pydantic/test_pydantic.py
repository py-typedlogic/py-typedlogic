from typedlogic import *
from typedlogic.generators import gen2
from typedlogic.parsers.pyparser import PythonParser

from tests.test_frameworks.pydantic.theorems.pydantic_mortals import *

X = Variable("x")
Y = Variable("y")


def test_expressions():
    t1 = AncestorOf(ancestor="a", descendant="b")
    t2 = AncestorOf(ancestor="b", descendant="c")
    assert isinstance(t1, Fact)
    assert isinstance(t2, Fact)
    assert t1.as_sexpr() == ["AncestorOf", "a", "b"]
    assert isinstance(t1 & t2, And)
    assert isinstance(t1 | t2, Or)
    assert isinstance(~t1, Not)
    assert isinstance(t1 >> t2, Implies)
    assert isinstance(t2 << t1, Implied)
    assert isinstance(t1 ^ t2, Xor)
    assert isinstance(not_provable(t1), NegationAsFailure)


def test_positional():
    assert AncestorOf("a", "b") == AncestorOf(ancestor="a", descendant="b")
    assert AncestorOf("a", "b").to_model_object() == Term("AncestorOf", "a", "b")


def test_predicate_definitions():
    pp = PythonParser()
    import tests.test_frameworks.pydantic.theorems.pydantic_mortals as pm

    theory = pp.parse(pm)
    pd_map = {pd.predicate: pd for pd in theory.predicate_definitions}
    for pd in theory.predicate_definitions:
        print(pd)
    assert pd_map["PersonAge"].arguments == {"person": "str", "age": "int"}
    # TODO:
    # assert pd_map["PersonHeight"].arguments == {'person': 'ID', 'height': ["int", "float"]}


def test_gen():
    def _f() -> None:
        for x, y in gen2(str, str):
            _dummy = AncestorOf(ancestor=x, descendant=y)
