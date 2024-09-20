from typing import List

import pytest
from typedlogic import And, Exists, Forall, Iff, Not, Or, Term, Variable
from typedlogic.transformations import (
    PrologConfig,
    as_prolog,
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
@pytest.mark.parametrize("expression,program,disjunctive",
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
        #((P ^ Q) >> R, "r :- p. r :- q.", False),
        # ((P & ~Q) >> R, r"r :- p, \+ (q). q :- p, \+ (r).", False), # stratified negation
        ((P & ~Q) >> R, r"r :- p, \+ (q).", False),
        (Term("P", Term("Q", 1)), "p(q(1)).", False),
        (Term("P", Term("eq", X, Y)), "p(X == Y).", False),
        (Term("P", Term("add", X, Y)), "p(X + Y).", False),
        (Forall([X], (P1x & Term("eq", X, 5)) >> P2x), r"p2(X) :- p1(X), X == 5.", False),
        (P1x >> P2x, "p2(X) :- p1(X).", False),
        # ((P1x & ~P3x)  >> P2x, r"p2(X) :- p1(X), \+ (p3(X)). p3(X) :- p1(X), \+ (p2(X))", False), # stratified negation
        ((P1x & ~P3x)  >> P2x, r"p2(X) :- p1(X), \+ (p3(X)).", False),
        ((~P3x & P1x)  >> P2x, r"p2(X) :- p1(X), \+ (p3(X)).", False),
        #(Exists([X], P1x), r"p1(sk__1).", False),
        (Exists([Y], Term("P", X, Y)) >> Term("Q", X), r"q(X) :- p(X, Y).", False),
        (Forall([X], (~P3x & P1x)  >> P2x), r"p2(X) :- p1(X), \+ (p3(X)).", False),
        (Forall([X], P1x >> P2x), "p2(X) :- p1(X).", False),
        (Forall([X], ((P1x & Exists([Y], Term("Q", X, Y))) >> P2x)), "p2(X) :- p1(X), q(X, Y).", False),
     ]
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


@pytest.mark.parametrize("expression,expected,direct",
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
    ])
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


@pytest.mark.parametrize("expression,expected",
    [
        (P, P),
        (P & Q, P & Q),
        (P | Q, P | Q),
        (P | (Q & R), (Q | P) & (R | P)),
        ((P & ~Q) >> R, Or(~P, Q, R)),
        ((P >> Q) >> R, ((P | R) & (~Q | R))),
    ])
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


