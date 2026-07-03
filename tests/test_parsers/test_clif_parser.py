import pytest

from typedlogic import And, Exists, Forall, Iff, Implies, Not, Or, Term, Variable
from typedlogic.compilers.clif_compiler import ClifCompiler, as_clif
from typedlogic.datamodel import ExactlyOne, NotInProfileError, Xor
from typedlogic.parsers.clif_parser import ClifParser, ClifSyntaxError


@pytest.fixture
def parser() -> ClifParser:
    return ClifParser()


@pytest.fixture
def compiler() -> ClifCompiler:
    return ClifCompiler()


def test_parse_ground_facts(parser):
    theory = parser.parse("(Person Fred) (Person 'Jie Wong') (Age Fred 33)")
    assert theory.sentences == [
        Term("Person", "Fred"),
        Term("Person", "Jie Wong"),
        Term("Age", "Fred", 33),
    ]


def test_parse_values(parser):
    theory = parser.parse("(P 1 -2.5 1e6 'a string' bare true false null)")
    [t] = theory.sentences
    assert t.values == (1, -2.5, 1000000.0, "a string", "bare", True, False, None)


def test_parse_quantified(parser):
    theory = parser.parse("(forall (x y) (if (FriendOf x y) (FriendOf y x)))")
    [s] = theory.sentences
    x = Variable("x")
    y = Variable("y")
    assert s == Forall([x, y], Implies(Term("FriendOf", x, y), Term("FriendOf", y, x)))


def test_parse_guarded_quantifier(parser):
    theory = parser.parse("(forall ((x Person)) (exists ((y Person)) (Knows x y)))")
    [s] = theory.sentences
    assert isinstance(s, Forall)
    assert s.variables == [Variable("x")]
    assert s.variables[0].domain == "Person"
    inner = s.sentence
    assert isinstance(inner, Exists)
    assert inner.variables[0].domain == "Person"


def test_parse_connectives(parser):
    theory = parser.parse(
        """
        (and (P a) (Q b))
        (or (P a) (not (Q b)))
        (iff (P a) (Q a))
        (= a b)
        """
    )
    a, b = "a", "b"
    assert theory.sentences == [
        And(Term("P", a), Term("Q", b)),
        Or(Term("P", a), Not(Term("Q", b))),
        Iff(Term("P", a), Term("Q", a)),
        Term("eq", a, b),
    ]


def test_parse_marked_free_variables(parser):
    theory = parser.parse("(P ?x)")
    [s] = theory.sentences
    assert s == Term("P", Variable("x"))


def test_parse_cl_text(parser):
    theory = parser.parse(
        """
        (cl-text my.theory
          (cl-comment 'this is ignored')
          (cl-imports other.theory)
          (Person Fred)
        )
        """
    )
    assert theory.name == "my.theory"
    assert theory.sentences == [Term("Person", "Fred")]


def test_parse_comments(parser):
    theory = parser.parse(
        """
        // a line comment
        (Person Fred) /* a block
        comment */ (Person Jie)
        """
    )
    assert theory.sentences == [Term("Person", "Fred"), Term("Person", "Jie")]


def test_parse_infers_predicate_definitions(parser):
    theory = parser.parse("(Age Fred 33) (forall ((x Person)) (if (Person x) (Named x)))")
    pd_map = theory.predicate_definition_map
    assert pd_map["Age"].arguments == {"arg0": "str", "arg1": "int"}
    assert pd_map["Person"].arguments == {"arg0": "Person"}


def test_parse_ground_terms(parser):
    terms = parser.parse_ground_terms("(Link a b) (forall (x) (P x)) (Link b c)")
    assert [str(t) for t in terms] == ["Link(a, b)", "Link(b, c)"]


@pytest.mark.parametrize(
    "text",
    [
        "(P a",
        "(P a))",
        "(P 'unterminated)",
        "()",
        "(not (P a) (Q b))",
        "(if (P a))",
        "(forall x (P x))",
        "orphan-atom",
    ],
)
def test_parse_errors(parser, text):
    with pytest.raises(ClifSyntaxError):
        parser.parse(text)


def test_validate(parser):
    assert parser.validate("(P a)") == []
    messages = parser.validate("(P a")
    assert len(messages) == 1
    assert messages[0].level == "error"


def test_compile_sentence(compiler):
    x = Variable("x")
    s = Forall([x], Implies(Term("P", x), Term("Q", x)))
    assert compiler.compile_sentence(s) == "(forall (x) (if (P x) (Q x)))"


def test_compile_quoting():
    assert as_clif(Term("P", "hello world", "it's")) == "(P 'hello world' 'it\\'s')"
    assert as_clif(Term("P", "not")) == "(P 'not')"


def test_compile_equality():
    assert as_clif(Term("eq", Variable("x"), 5)) == "(= ?x 5)"


def test_compile_xor_expands():
    p = Term("P")
    q = Term("Q")
    assert as_clif(Xor(p, q)) == "(and (or (P) (Q)) (not (and (P) (Q))))"


def test_compile_exactly_one_expands_three_operands():
    """ExactlyOne with more than two operands should compile through CLIF expansion."""
    p = Term("P")
    q = Term("Q")
    r = Term("R")
    assert as_clif(ExactlyOne(p, q, r)) == (
        "(or (and (P) (not (or (Q) (R)))) "
        "(and (Q) (not (or (P) (R)))) "
        "(and (R) (not (or (P) (Q)))))"
    )


def test_compile_negation_as_failure_not_in_profile(compiler):
    from typedlogic.datamodel import NegationAsFailure

    with pytest.raises(NotInProfileError):
        compiler.compile_sentence(NegationAsFailure(Term("P", "a")))


def test_roundtrip_preserves_strings(parser, compiler):
    theory = parser.parse("(P 'a string with spaces' '123' plain 123)")
    compiled = compiler.compile(theory)
    assert compiled == "(P 'a string with spaces' '123' plain 123)"
    assert compiler.compile(parser.parse(compiled)) == compiled


def test_registry_handles():
    from typedlogic.registry import get_compiler, get_parser

    assert isinstance(get_parser("clif"), ClifParser)
    assert isinstance(get_compiler("clif"), ClifCompiler)
