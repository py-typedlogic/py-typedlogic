"""Demo version test."""
import pytest
from typedlogic import *
from typedlogic import Fact, gen2
from typedlogic.datamodel import PredicateDefinition, SentenceGroup, Term, Theory
from typedlogic.pybridge import fact_arg_py_types, fact_args, fact_to_term

from tests.theorems.mortals import *
from typedlogic.transformations import to_horn_rules


def test_python_instances():
    t1 = AncestorOf(ancestor='x', descendant='y')
    t2 = AncestorOf(ancestor='y', descendant='z')
    assert isinstance(t1, Fact)
    assert isinstance(t2, Fact)
    assert isinstance(t1 & t2, And)
    # assert isinstance(t1 and t2, And)
    assert isinstance(t1 | t2, Or)
    assert isinstance(~t1, Not)
    # assert isinstance(not t1, Not)
    assert isinstance(t1 >> t2, Implies)
    assert isinstance((t1 & t1) >> t2, Implies)
    assert isinstance(t2 << t1, Implied)
    assert isinstance(t1 ^ t2, Xor)
    assert isinstance(not_provable(t1), NegationAsFailure)
    assert len(vars(t1)) == 2
    assert len(fact_args(t2)) == 2
    assert fact_args(t1) == ('ancestor', 'descendant')
    assert fact_arg_py_types(t1) == {'ancestor': str, 'descendant': str}
    assert isinstance(fact_to_term(t1), Term)



@pytest.mark.parametrize("ex1, ex2, eq", [
    (AncestorOf(ancestor='x', descendant='y'), AncestorOf(ancestor='x', descendant='y'), True),
    (AncestorOf(ancestor='x', descendant='y'), AncestorOf(ancestor='y', descendant='z'), False),
    ])
def test_equality(ex1, ex2, eq):
    assert (ex1 == ex2) == eq
    assert (ex1 != ex2) == (not eq)



def test_theorem():
    x = Variable("x")
    y = Variable("y")
    z = Variable("z")
    p = PredicateDefinition('ancestor_of', {'ancestor': str, 'descendant': str})
    aa = SentenceGroup(
        name="test",
        sentences=[Implies(
            And(Term('ancestor_of', {'ancestor': x, 'descendant':z }),
                Term('ancestor_of', {'ancestor': z, 'descendant': y})),
            Term('ancestor_of', {'ancestor': x, 'descendant': y})),
        ],
        # argument_types={'x': str, 'y': str, 'z': str},
    )
    th = Theory(
        name="test",
        sentence_groups=[aa],
        predicate_definitions=[p],
    )
    print(th)


def test_gen():
    """
    This test exists only to test mypy type checking.
    """
    def _f() -> None:
        for x, y in gen2(str, str):
            _dummy = AncestorOf(ancestor=x, descendant=y)

def test_unary():
    from tests.theorems.unary_predicates import Win
    t = Win()
    args = fact_args(t)
    assert args == ()


