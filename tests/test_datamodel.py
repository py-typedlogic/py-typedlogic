"""Demo version test."""
import pytest
from typedlogic import *
from typedlogic.datamodel import (
    Forall,
    PredicateDefinition,
    SentenceGroup,
    SentenceGroupType,
    Term,
    Theory,
    as_object,
    from_object,
)


def test_implies():
    x = Variable("x")
    y = Variable("y")
    t1 = Term("T1", x, y)
    t2 = Term("T1", x, x)
    assert as_object(t1) == {
        "arguments": ["T1", {"arguments": ["x"], "type": "Variable"}, {"arguments": ["y"], "type": "Variable"}],
        "type": "Term",
    }
    assert from_object(as_object(t1)) == t1
    impl = t1 >> t2
    assert isinstance(impl, Implies)
    # assert (t1 >> t2) != (t1 >> t1)
    assert impl.antecedent == t1
    assert impl.consequent == t2
    assert impl.antecedent != t2
    assert impl.consequent != t1
    impl = Iff(t1, t2)
    assert isinstance(impl, Iff)
    assert impl.left == t1
    assert impl.right == t2
    assert impl.operands == (t1, t2)
    assert str(impl) == "(T1(?x, ?y) <-> T1(?x, ?x))"
    obj = as_object(impl)
    assert list(obj.keys()) == ["type", "arguments"]
    assert obj["type"] == "Iff"
    assert len(obj["arguments"]) == 2
    assert from_object(as_object(impl)) == impl


def test_expressions():
    x = Variable("x")
    y = Variable("y")
    z = Variable("z")
    t1 = Term("ancestor_of", dict(ancestor="x", descendant="y"))
    t2 = Term("ancestor_of", dict(ancestor="y", descendant="z"))
    # TBox representation
    impl = Implies(
        And(Term("AncestorOf", dict(ancestor=x, descendant=z)) & Term("AncestorOf", dict(ancestor=z, descendant=y))),
        Term("AncestorOf", dict(ancestor=x, descendant=y)),
    )
    qs = Forall([x, y, z], impl)
    assert isinstance(qs, Forall)
    assert isinstance(qs.sentence, Implies)
    # alternative
    qs = Forall([x, y, z], impl)
    assert isinstance(qs, Forall)
    assert isinstance(qs.sentence, Implies)


def test_group_types():
    all_types = {x: x.value for x in SentenceGroupType}
    assert len(all_types) == 2
    assert SentenceGroupType.AXIOM.value == "axiom"


def test_term():
    x = Variable("x")
    y = Variable("y")
    z = Variable("z")
    t1 = Term("ancestor_of", {"ancestor": x, "descendant": y})
    t2 = Term("ancestor_of", {"ancestor": y, "descendant": z})
    assert not t1.is_ground
    assert not t1.positional
    t1andt2 = t1 & t2
    assert isinstance(t1andt2, And)
    assert x != y
    assert x == Variable("x")
    t1 = Term("p", "x", "y")
    assert t1.positional
    assert isinstance(t1, Term)
    assert t1.predicate == "p"
    assert list(t1.bindings.values()) == ["x", "y"]
    t1.make_keyword_indexed(["ancestor", "descendant"])
    assert t1.bindings == {"ancestor": "x", "descendant": "y"}
    assert not t1.positional
    constant_term = Term("p")
    assert constant_term.bindings == {}
    assert constant_term.is_constant
    assert constant_term.positional is None
    assert str(constant_term) == "p"
    t3 = Term("ancestor_of", {"ancestor": "x", "descendant": "y"})
    assert t3.is_ground


def test_complex_term():
    x = Variable("x")
    ct = Term("p", "foo", Term("q", x))
    assert str(ct) == "p(foo, q(?x))"


def test_that():
    quoted_term = Exists([Variable("x")], Term("Alien", "x"))
    that = Term("that", quoted_term)
    prop = Forall([Variable("y")], Implies(Term("Believer", "y"), Term("Believes", "y", that)))
    assert str(prop) == "∀y: None : (Believer(y) -> Believes(y, that(∃Alien(x))))"


def test_unary():
    t = Term("p")
    assert str(t) == "p"
    assert t.is_ground
    assert t.positional is None
    assert t.bindings == {}
    assert t.predicate == "p"
    assert t.values == ()


@pytest.mark.parametrize(
    "ex1, ex2, eq",
    [
        (Variable("x"), Variable("x"), True),
        (Variable("x"), Variable("y"), False),
        (Term("p", {"x": "a1"}), Term("p", {"x": "a1"}), True),
        (Term("p", {"x": "a1"}), Term("p", {"x": "a2"}), False),
        (
            Implies(Term("p", {"x": "a1"}), Term("p", {"x": "a2"})),
            Implies(Term("p", {"x": "a1"}), Term("p", {"x": "a2"})),
            True,
        ),
        (
            Implies(Term("p", {"x": "a1"}), Term("p", {"x": "a2"})),
            Implies(Term("p", {"x": "a1"}), Term("p", {"x": "a3"})),
            False,
        ),
    ],
)
def test_equality(ex1, ex2, eq):
    print(ex1, ex2, eq)
    assert (ex1 == ex2) == eq
    assert (ex1 != ex2) == (not eq)


def test_theorem():
    x = Variable("x")
    y = Variable("y")
    z = Variable("z")
    p = PredicateDefinition("ancestor_of", {"ancestor": str, "descendant": str})
    aa = SentenceGroup(
        name="test",
        sentences=[
            Implies(
                And(
                    Term("ancestor_of", {"ancestor": x, "descendant": z}),
                    Term("ancestor_of", {"ancestor": z, "descendant": y}),
                ),
                Term("ancestor_of", {"ancestor": x, "descendant": y}),
            ),
        ],
        # argument_types={'x': str, 'y': str, 'z': str},
    )
    th = Theory(
        name="test",
        sentence_groups=[aa],
        predicate_definitions=[p],
    )
    obj = as_object(th)
    print(obj)
    th2 = from_object(obj)
    assert th2 == th
    print(th)
