from typing import List

import pytest

from typedlogic import (
    And,
    Exists,
    Forall,
    Iff,
    Implies,
    NegationAsFailure,
    Not,
    Or,
    PredicateDefinition,
    Term,
    Theory,
    Variable,
)
from typedlogic.datamodel import ExactlyOne, Implied, NotInProfileError
from typedlogic.transformations import (
    PrologConfig,
    as_prolog,
    counterexample_proof_sentences,
    counterexample_sentence,
    expand_exactly_one,
    sentences_from_predicate_hierarchy,
    simple_prolog_transform,
    simplify,
    to_cnf,
    to_cnf_lol,
    to_horn_rules,
    transform_sentence,
)

X = Variable("x")
Y = Variable("y")
Z = Variable("z")
P = Term("P")
Q = Term("Q")
R = Term("R")
S = Term("S")
P1x = Term("P1", X)
P2x = Term("P2", X)
P3x = Term("P3", X)
Q1xy = Term("Q1", X, Y)


@pytest.mark.parametrize(
    "expression,program,disjunctive",
    [
        (P, "p.", False),
        (P & Q, "p. q.", False),
        (P ^ Q, ":- p, q. p; q", True),
        (P >> Q, "q :- p.", False),
        (P << Q, "p :- q.", False),
        (Iff(P, Q), "p :- q. q :- p.", False),
        (P >> (Q >> R), "r :- p, q.", False),
        (P >> (Q | R), "q; r :- p.", True),
        (P >> (Q | (R & S)), "r; q :- p. s; q :- p", True),
        (P >> (Q | (R & ~S)), "q :- s, p. r; q :- p", True),
        (P | Q, "p; q.", True),
        (Not(P), ":- p.", True),
        # (P ^ Q, "r :- p. r :- q.", False),
        # (P >> (Q | R), "", False),
        (P >> (Q & R), "q :- p. r :- p.", False),
        ((P & Q) >> R, "r :- p, q.", False),
        (Iff(P & Q, R), "r :- p, q. p :- r. q :- r", True),
        ((P | Q) >> R, "r :- p. r :- q.", False),
        # ((P ^ Q) >> R, "r :- p. r :- q.", False),
        # ((P & ~Q) >> R, r"r :- p, \+ (q). q :- p, \+ (r).", False), # stratified negation
        ((~P) >> R, r"r :- \+ (p).", False),
        ((P & ~Q) >> R, r"r :- p, \+ (q).", False),
        (Term("P", Term("Q", 1)), "p(q(1)).", False),
        (Term("P", Term("eq", X, Y)), "p(X == Y).", False),
        (Term("P", Term("add", X, Y)), "p(X + Y).", False),
        (Forall([X], (P1x & Term("eq", X, 5)) >> P2x), r"p2(X) :- p1(X), X == 5.", False),
        (P1x >> P2x, "p2(X) :- p1(X).", False),
        # ((P1x & ~P3x)  >> P2x, r"p2(X) :- p1(X), \+ (p3(X)). p3(X) :- p1(X), \+ (p2(X))", False), # stratified negation
        ((P1x & ~P3x) >> P2x, r"p2(X) :- p1(X), \+ (p3(X)).", False),
        ((~P3x & P1x) >> P2x, r"p2(X) :- p1(X), \+ (p3(X)).", False),
        # (Exists([X], P1x), r"p1(sk__1).", False),
        # (Implies(P1x, Exists([X], P2x)), "x", False),
        (Exists([Y], Term("P", X, Y)) >> Term("Q", X), r"q(X) :- p(X, Y).", False),
        (Forall([X], (~P3x & P1x) >> P2x), r"p2(X) :- p1(X), \+ (p3(X)).", False),
        (Forall([X], P1x >> P2x), "p2(X) :- p1(X).", False),
        (Forall([X], ((P1x & Exists([Y], Term("Q", X, Y))) >> P2x)), "p2(X) :- p1(X), q(X, Y).", False),
        (Forall([X], (P1x | P2x) >> P3x), "p3(X) :- p1(X). p3(X) :- p2(X).", False),
        (Forall([X], Term("P", Term("f", X)) >> P2x), "p2(X) :- p(f(X)).", False),
        (Not(P & Q), ":- p, q.", True),
    ],
)
def test_to_horn_rule_syntax(expression, program, disjunctive):
    def _norm(p: str) -> List[str]:
        return sorted([l.strip() for l in p.split(".") if l.strip()])

    print(f"\nTR: {expression}")
    cnf = to_cnf_lol(expression)
    print(f"CNF: {cnf}")
    horn_sentence = to_horn_rules(expression, allow_disjunctions_in_head=disjunctive)
    print(f"HORN {disjunctive}: {horn_sentence}")
    config = PrologConfig(disjunctive_datalog=disjunctive, allow_skolem_terms=True)
    result = as_prolog(horn_sentence, config)
    assert _norm(program) == _norm(result), f"via {horn_sentence}"


@pytest.mark.parametrize(
    "expression,expected,direct",
    [
        (~P, ~P, True),
        (~~P, P, True),
        (~~~P, ~P, True),
        (Or(P), P, True),
        (Or(Or(P)), P, True),
        (Forall([X], Or(Or(P1x))), Forall([X], P1x), False),
        (Forall([X], Forall([Y], Q1xy)), Forall([X, Y], Q1xy), False),
        (And(P), P, True),
        (And(And(P)), P, True),
        (And(Or(P)), P, True),
        (And(Q, Or(P)), And(Q, P), True),
    ],
)
def test_simplify(expression, expected, direct):
    """

    :param expression:
    :param expected:
    :param direct:
    :return:
    """
    if direct:
        simplified = simplify(expression)
    else:
        simplified = transform_sentence(expression, simplify)
    assert simplified == expected, f"Expected {expected} but got {simplified}"


@pytest.mark.parametrize(
    "expression,expected",
    [
        (P, P),
        (P & Q, P & Q),
        (P | Q, P | Q),
        (P | (Q & R), (Q | P) & (R | P)),
        ((P & ~Q) >> R, Or(~P, Q, R)),
        ((P >> Q) >> R, ((P | R) & (~Q | R))),
    ],
)
def test_to_cnf(expression, expected):
    """
    Test conversion to CNF

    Note this is partly redundant with the to_horn_rule_syntax test, as that depends on
    conversion to CNF. However, this test is more direct and can be used to verify the
    correctness of the conversion.

    :param expression:
    :param expected:
    :return:
    """
    cnf = to_cnf(expression)
    assert cnf == expected, f"Expected {expected} but got {cnf}"


@pytest.mark.parametrize(
    "expression,expected",
    [
        (ExactlyOne(P), P),
        (ExactlyOne(P, Q), And(Or(P, Q), Not(And(P, Q)))),
        (
            ExactlyOne(P, Q, R),
            Or(
                And(P, Not(Or(Q, R))),
                And(Q, Not(Or(P, R))),
                And(R, Not(Or(P, Q))),
            ),
        ),
    ],
)
def test_expand_exactly_one(expression, expected):
    """ExactlyOne should expand to a disjunction of one-holds-others-do-not conjunctions."""
    assert expand_exactly_one(expression) == expected


def test_exactly_one_translates_to_horn_rules():
    """ExactlyOne with more than two operands should survive the full Horn translation."""
    rules = to_horn_rules(ExactlyOne(P, Q, R), allow_disjunctions_in_head=True)
    assert rules, "expected at least one rule"
    lines = as_prolog(rules, PrologConfig(disjunctive_datalog=True)).splitlines()
    # exactly one clause is the unconditional at-least-one disjunction
    [at_least_one] = [line for line in lines if ":-" not in line]
    assert sorted(at_least_one.rstrip(".").split("; ")) == ["p", "q", "r"]


def test_goal_clauses_dropped_unless_allowed():
    """Constraints (clauses with no positive literal) are only emitted when allow_goal_clauses is set."""
    assert to_horn_rules(Not(P)) == []
    assert to_horn_rules(Not(And(P, Q))) == []
    rules = to_horn_rules(Not(And(P, Q)), allow_goal_clauses=True)
    assert as_prolog(rules) == ":- p, q."


def test_empty_clause_respects_allow_goal_clauses():
    """The empty clause (false) is itself a goal clause and must respect the flag."""
    assert to_horn_rules(Or()) == []
    rules = to_horn_rules(Or(), allow_goal_clauses=True)
    assert as_prolog(rules) == ":- true."


def test_simple_prolog_transform_strict_handles_implied():
    """Implied sentences are supported and must not raise in strict mode."""
    [rule] = simple_prolog_transform(Implied(P, Q), strict=True)
    assert as_prolog(rule) == "p :- q."


def test_simple_prolog_transform_strict_handles_iff():
    """Iff sentences are rewritten to two implications and must not raise in strict mode."""
    rules = simple_prolog_transform(Iff(P, Q), strict=True)
    assert sorted(as_prolog(r) for r in rules) == ["p :- q.", "q :- p."]


def test_as_prolog_grounds_head_vars_from_disjunctive_body():
    """A head variable bound in every branch of a disjunctive body is grounded."""
    s = Implies(Or(Term("A", X), Term("B", X)), Term("C", X))
    assert as_prolog(s) == "c(X) :- (a(X); b(X))."


def test_as_prolog_rejects_head_var_missing_from_a_body_branch():
    """A head variable bound in only one branch of a disjunctive body is not safe."""
    s = Implies(Or(Term("A", X), Term("B", Y)), Term("C", X))
    with pytest.raises(NotInProfileError):
        as_prolog(s)


def test_as_prolog_grounds_head_vars_from_nested_function_terms():
    """A head variable bound inside a body function term is grounded."""
    s = Implies(Term("A", Term("f", X)), Term("B", X))
    assert as_prolog(s) == "b(X) :- a(f(X))."


def test_as_prolog_negated_goals_do_not_ground_head_vars():
    """A variable appearing only under negation in the body cannot ground a head variable."""
    s = Implies(And(Term("A", Y), Not(Term("B", X))), Term("C", X))
    with pytest.raises(NotInProfileError):
        as_prolog(s)


def test_counterexample_sentence_for_universal_implication():
    """Universal implications can be transformed into Datalog counterexample rules."""
    sentence = Forall([X, Y], Implies(And(P1x, Q1xy), P2x))
    counterexample = counterexample_sentence(sentence)

    assert counterexample == Implies(And(P1x, Q1xy, NegationAsFailure(P2x)), Term("counterexample", X, Y))
    config = PrologConfig(negation_as_failure_symbol="not", allow_nesting=False)
    assert as_prolog(counterexample, config) == "counterexample(X, Y) :- p1(X), q1(X, Y), not p2(X)."


def test_counterexample_sentence_rejects_ungrounded_head_variables():
    """Counterexample rules must not put ungrounded variables in the negated head."""
    sentence = Forall([X, Y], Implies(P1x, Term("Q", Y)))

    with pytest.raises(NotInProfileError, match="not grounded"):
        counterexample_sentence(sentence)


def test_counterexample_proof_sentences_reject_ungrounded_head_variables():
    """Proof fixtures must reject lemmas that are not Datalog-safe."""
    sentence = Forall([X, Y], Implies(P1x, Term("Q", Y)))

    with pytest.raises(NotInProfileError, match="not grounded"):
        counterexample_proof_sentences(sentence)


def test_counterexample_proof_sentences_assume_positive_antecedents():
    """The proof fixture grounds antecedent atoms as assumptions before querying the head."""
    sentence = Forall([X, Y], Implies(And(P1x, Q1xy), P2x))
    proof_sentences = counterexample_proof_sentences(sentence)

    config = PrologConfig(negation_as_failure_symbol="not", allow_nesting=False, double_quote_strings=True)
    assert as_prolog(proof_sentences, config).splitlines() == [
        'p1("__counterexample_x").',
        'q1("__counterexample_x", "__counterexample_y").',
        'counterexample :- not p2("__counterexample_x").',
    ]


def test_as_prolog_quotes_atoms_with_special_characters():
    """String values containing quotes or backslashes must render as valid quoted atoms."""
    assert as_prolog(Term("p", "plain")) == "p('plain')"
    assert as_prolog(Term("p", "O'Brien")) == r"p('O\'Brien')"
    assert as_prolog(Term("p", "a\\b")) == r"p('a\\b')"


def test_hierarchy_implications_match_parent_args_by_name():
    """Child predicates may declare extra arguments; parent arguments are matched by name."""
    theory = Theory(
        predicate_definitions=[
            PredicateDefinition("Employee", {"name": "str", "salary": "int"}, parents=["Person"]),
            PredicateDefinition("Person", {"name": "str"}),
        ],
    )
    [s] = sentences_from_predicate_hierarchy(theory)
    assert as_prolog(s, translate=True) == "person(Name) :- employee(Name, Salary)."


def test_hierarchy_rejects_parent_args_missing_from_child():
    """A parent argument absent from the child would leave an unbound head variable."""
    theory = Theory(
        predicate_definitions=[
            PredicateDefinition("Dog", {"name": "str"}, parents=["Animal"]),
            PredicateDefinition("Animal", {"id": "str"}),
        ],
    )
    with pytest.raises(ValueError, match="not present in child"):
        sentences_from_predicate_hierarchy(theory)


def test_hierarchy_rejects_unknown_parent():
    """A parent predicate with no definition should raise a clear error."""
    theory = Theory(
        predicate_definitions=[
            PredicateDefinition("Dog", {"name": "str"}, parents=["Animal"]),
        ],
    )
    with pytest.raises(ValueError, match="Unknown parent"):
        sentences_from_predicate_hierarchy(theory)
