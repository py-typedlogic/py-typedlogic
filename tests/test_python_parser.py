import ast

import pytest
from typedlogic import And, Implies, Not, Or, Variable
from typedlogic.datamodel import Exists, Forall, Iff, Term
from typedlogic.parsers.pyparser.python_ast_utils import parse_function_def_to_sentence_group, parse_sentence

X = Variable("x")
Y = Variable("y")
Z = Variable("z")
BLANK = Variable("_")
PERSON_TERM = Term("Person", {"name": X})
PERSON_TERM2 = Term("Person", {"name": X, "age": Y})
AGENT_TERM = Term("Agent", {"name": X})
AGENT_TERM2 = Term("Agent", {"name": X, "age": Y})

@pytest.mark.parametrize("text,expr", [
    ("Person(name=x)", PERSON_TERM),
    ("Person()", Term("Person", {})),
    ("Person(x)", Term("Person", X)),
    ("Person(_)", Term("Person", BLANK)),
    ("Num(1)", Term("Num", 1)),
    ("assert Person(name=x)", PERSON_TERM),
    ("Person(name='x')", Term("Person", {"name": "x"})),
    ("Person(age=55)", Term("Person", {"age": 55})),
    ("~Person(name=x)", Not(PERSON_TERM)),
    ("(~Person(name=x))", Not(PERSON_TERM)),
    ("((~Person(name=x)))", Not(PERSON_TERM)),
    ("not Person(name=x)", Not(PERSON_TERM)),
    ("PersonAge(x, y)", Term("PersonAge", X, Y)),
    ("PersonAge(x, 5)", Term("PersonAge", X, 5)),
    ("x == y", Term("eq", X, Y)),
    ("x < y", Term("lt", X, Y)),
    ("x != y", Term("ne", X, Y)),
    ("x + y", Term("add", X, Y)),
    ("Person(name=x) & Agent(name=x)", And(PERSON_TERM, AGENT_TERM)),
    ("Person(name=x) | Agent(name=x)", Or(PERSON_TERM, AGENT_TERM)),
    ("Person(name=x) >> Agent(name=x)", Implies(PERSON_TERM, AGENT_TERM)),
    ("Person(name=x, age=1, desc='x')", Term("Person", {"name": X, "age": 1, "desc": "x"})),
    ("all(Agent(name=x) for x in gen1(Name) if Person(name=x))", Forall([X], Implies(PERSON_TERM, AGENT_TERM))),
    ("any(Agent(name=x) for x in gen1(Name) if Person(name=x))", Exists([X], Implies(PERSON_TERM, AGENT_TERM))),
    ("not any(Agent(name=x) for x in gen1(Name) if Person(name=x))", Not(Exists([X], Implies(PERSON_TERM, AGENT_TERM)))),
    ("all(Agent(name=x, age=y) for x, y in gen2(Name, int) if Person(name=x, age=y))",
     Forall([X, Y], Implies(PERSON_TERM2, AGENT_TERM2))),
    ("any(Person(name=x) for x in gen1(Name))", Exists([X], PERSON_TERM)),
    ("if Person(name=x):\n  assert Agent(name=x)", Implies(Term("Person", {"name": X}),
                                                    Term("Agent", {"name": X}))),
    ("if Person(name=x):\n  Agent(name=x)", Implies(Term("Person", {"name": X}),
                                                    Term("Agent", {"name": X}))),
    #("if A(x):\n  B(x+1)",
    # Implies(Term('eq', X, 1), Term("B", X))),
    #("if A(x):\n  y==x+1, B(y)",
    # Implies(Term('A', X),
    #         And(Term('eq', Y, Term('add', X, 1))))),
    ("P(Q(x))", Term("P", Term("Q", X))),
    ('P(x+"a")', Term("P", Term("add", X, "a"))),
    ("P(x+1)", Term("P", Term("add", X, 1))),
    ("if x == 1:\n  B(x)",
     Implies(Term('eq', X, 1), Term("B", X))),
    ("if x == CONST:\n  B(x)",
     Implies(Term('eq', X, Variable("CONST")), Term("B", X))),
    ("if A(x) & eq(x, CONST):\n  B(x)",
     Implies(And(Term("A", X),Term("eq", X, Variable("CONST"))), Term("B", X))),
    ("if A(x) & (x==CONST):\n  B(x)",
     Implies(And(Term("A", X),Term("eq", X, Variable("CONST"))), Term("B", X))),
    ("if A(x) and x==CONST:\n  B(x)",
     Implies(And(Term("A", X),Term("eq", X, Variable("CONST"))), Term("B", X))),
    ("if A(x) and (x==CONST):\n  B(x)",
     Implies(And(Term("A", X),Term("eq", X, Variable("CONST"))), Term("B", X))),
    ("Implies((A() & B()), C())",
        Implies(And(Term("A", {}), Term("B", {})), Term("C", {}))),
    ("Implies((A() & (1 == 1)), C())",
        Implies(And(Term("A", {}), Term("eq", 1, 1)), Term("C", {}))),
     ("Implies((A(x) & (x=='foo')), B(x))",
      Implies(
           And(Term("A", X),
                     Term("eq", X,"foo")),
           Term("B", X))
      ),
     ("Iff((A(x) and (x=='foo')), B(x))",
      Iff(
           And(Term("A", X),
                     Term("eq", X, "foo")),
           Term("B", X))
      ),
     ("Iff((A(x) & (x==CONST)), B(x))",
      Iff(
           And(Term("A", X),
                     Term("eq", X, Variable("CONST"))),
           Term("B", X))
      ),

])
def test_parse_sentence(text, expr):
    tree = ast.parse(text)
    func_def = tree.body[0]
    print(ast.dump(func_def, indent=2))
    sentence = parse_sentence(func_def)
    print(sentence)
    print(type(sentence), type(expr))
    assert isinstance(sentence, type(expr))
    assert sentence == expr


axiom_func = """
def all_persons_are_mortal_axiom() -> bool:
    return all(
        Person(name=x) >> Mortal(name=x)
        for x in gen(NameType)
    )
"""

def test_parse_simple_function():
    tree = ast.parse(axiom_func)
    func_def = tree.body[0]
    sentence_group = parse_function_def_to_sentence_group(func_def)

    assert sentence_group.name == "all_persons_are_mortal_axiom"
    qs = sentence_group.sentences[0]
    assert isinstance(qs, Forall)
    assert qs.quantifier == "all"
    assert qs.variables == [X]
    sentence = qs.sentence
    assert isinstance(sentence, Implies)
    assert isinstance(sentence.antecedent, Term)
    assert sentence.antecedent.predicate == "Person"
    assert sentence.antecedent.bindings == {"name": X}
    assert isinstance(sentence.consequent, Term)
    assert sentence.consequent.predicate == "Mortal"
    assert sentence.consequent.bindings == {"name": X}

assert_example = """
def all_persons_are_mortal_axiom() -> bool:
    assert all(
        Person(name=x) >> Mortal(name=x)
        for x in gen(NameType)
    )
"""

def test_assert():
    tree = ast.parse(assert_example)
    func_def = tree.body[0]
    print(ast.dump(func_def, indent=2))
    sentence_group = parse_function_def_to_sentence_group(func_def)
    print(sentence_group)


func_args_example = """
NameType = Union[str, int]
def all_persons_are_mortal_axiom(x: NameType):
    if not Mortal(name=x):
        assert not Person(name=x)
"""

def test_func_args():
    tree = ast.parse(func_args_example)
    func_def = tree.body[-1]
    # print(ast.dump(func_def, indent=2))
    sentence_group = parse_function_def_to_sentence_group(func_def)
    print(sentence_group)
    qs = sentence_group.sentences[0]
    assert isinstance(qs, Forall)
    # assert qs.bindings == {"x": "NameType"}
    vars = qs.variables
    assert len(vars) == 1
    assert vars[0].name == "x"
    assert vars[0].domain == "NameType"
    sentence = qs.sentence
    assert isinstance(sentence, Implies)
    assert isinstance(sentence.antecedent, Not)
    assert isinstance(sentence.antecedent.operands[0], Term)


axiom_func_complex = """
def complex_axiom() -> bool:
    return all(
        (Person(name=x) & Human(species="homo sapiens")) >> (Mortal(name=x) | Immortal(name=x))
        for x in gen(NameType)
    )
"""

def test_complex_axiom():

    tree = ast.parse(axiom_func_complex)
    func_def = tree.body[0]
    parsed_axiom = parse_function_def_to_sentence_group(func_def)

    assert parsed_axiom.name == "complex_axiom"
    assert parsed_axiom.sentences == [
        Forall(
            [X],
            Implies(
                And(Term("Person", {"name": X}),
                    Term("Human", {"species": "homo sapiens"}),
                    ),
                Or(
                    Term("Mortal", {"name": X}),
                         Term("Immortal",{"name": X})
                ),
            ),
        )
    ]


axiom_func_neg = """
def negation_axiom() -> bool:
    return all(
        ~Mortal(name=x) >> Immortal(name=x)
        for x in gen(NameType)
    )
"""

def test_negation():

    tree = ast.parse(axiom_func_neg)
    func_def = tree.body[0]
    parsed_axiom = parse_function_def_to_sentence_group(func_def)

    qs = parsed_axiom.sentences[0]
    assert isinstance(qs, Forall)
    assert isinstance(qs.sentence, Implies)
    assert isinstance(qs.sentence.operands[0], Not)
    assert isinstance(qs.sentence.operands[0].operands[0], Term)
    assert qs.sentence.operands[0].operands[0].predicate == "Mortal"


axiom_func_nested = """
def nested_attribute_axiom() -> bool:
    return all(
        module.submodule.Predicate(attr=x) >> Result(value=x)
        for x in gen(ValueType)
    )
"""

def test_nested_attributes():

    tree = ast.parse(axiom_func_nested)
    func_def = tree.body[0]
    parsed_axiom = parse_function_def_to_sentence_group(func_def)

    qs = parsed_axiom.sentences[0]
    assert isinstance(qs, Forall)
    assert isinstance(qs.sentence, Implies)
    assert qs.sentence.operands[0].predicate == "module.submodule.Predicate"
    assert qs.sentence.operands[1].predicate == "Result"



axiom_func_unsupported = """
def unsupported_node_axiom() -> bool:
    return all(
        [Person(name=x)]  # List is not a supported node type
        for x in gen(NameType)
    )
"""

def test_unsupported_node_type():

    tree = ast.parse(axiom_func_unsupported)
    func_def = tree.body[0]
    with pytest.raises(NotImplementedError, match="Unsupported node type"):
        parse_function_def_to_sentence_group(func_def)
