from typing import Dict, Union

import pytest
from problog.program import PrologString
from problog import get_evaluatable
from problog.logic import Term

from tests.theorems.probabilistic import coins, coins2, smokers
from typedlogic.extensions.probabilistic import Evidence, ProbabilisticModel
from typedlogic.integrations.solvers.problog.problog_compiler import ProbLogCompiler
from typedlogic.integrations.solvers.problog.problog_solver import ProbLogSolver
from typedlogic.parsers.pyparser.introspection import translate_module_to_theory


def as_simple_dict(result: Dict[Union[Term, str], float], precision=3) -> Dict[str, float]:
    return {str(k): round(v, precision) for k, v in result.items()}

# TODO: These tests don't actually test ptl behavior and can be removed in future
@pytest.mark.parametrize("prog,expected", [
    (
            """
            coin(c1). coin(c2).
            0.4::heads(C); 0.6::tails(C) :- coin(C).
            win :- heads(C).
            evidence(heads(c1), false).
            query(win).
            query(coin(_)).
            """,
            {"win": 0.4, 'coin(c1)': 1.0, 'coin(c2)': 1.0}
     ),
     (
            """
            coin(c1). coin(c2).
            0.4::heads(C) :- coin(C).
            0.6::tails(C) :- coin(C).
            win :- heads(C).
            query(win).
            """,
            {"win": 0.64}
     ),
     (
            """
            coin(c1). coin(c2). coin(c3).
            0.4::heads(C); 0.6::tails(C) :- coin(C).
            win :- heads(C).
            query(win).
            """,
            {"win": 0.784}
     ),
    (
            """
            coin("c1"). coin(c2). coin(c3).
            0.4::heads(C); 0.6::tails(C) :- coin(C).
            win :- heads(C).
            evidence(heads(c3), true).
            query(win).
            """,
            {"win": 1.0}
     ),
])
def test_problog(prog,expected):
    p = PrologString(prog)
    ev = get_evaluatable()
    result = ev.create_from(p).evaluate()
    result = as_simple_dict(result)
    assert result == expected

@pytest.mark.parametrize("theory_module,facts,evidences",
    [
        (coins, [coins.Coin("c1"), coins.Coin("c2")], [(coins.Heads("c1"), False)]),
        (coins2, [coins2.Coin("c1"), coins2.Coin("c2")], [(coins2.Heads("c1"), False)]),
    ]
)
def test_compiler(theory_module, facts, evidences):
    theory = translate_module_to_theory(theory_module)
    for f in facts:
        theory.add(f)
    for e, truth_value in evidences:
        theory.add(Evidence(e, truth_value))
    #theory.add(Probability(0.4, coins.Heads("c1")))
    compiler = ProbLogCompiler()
    compiled = compiler.compile(theory)
    assert "0.4::heads(C) :- coin(C)." in compiled


@pytest.mark.parametrize("theory_module,facts,evidences,expected",
    [
        (coins,
         [coins.Coin("c1"), coins.Coin("c2")],
         [(coins.Heads("c1"), False)],
         [(coins.Win(), 0.4), (coins.Heads("c1"), 0.0), (coins.Heads("c2"), 0.4)]
         ),
        (coins2,
         [coins2.Coin("c1"), coins2.Coin("c2")],
         [(coins2.Heads("c1"), False)],
         [(coins2.Win(), 0.4), (coins2.Heads("c1"), 0.0), (coins2.Heads("c2"), 0.4)]
         ),
        (smokers,
         [],
         [],
         [(smokers.Asthma("joris"), 0.169)],
         ),
        (smokers,
         [],
         [(smokers.Asthma("joris"), True)],
         [(smokers.Asthma("joris"), 1.0)],
         ),
    ]
)
def test_solver(theory_module, facts, evidences, expected):
    theory = translate_module_to_theory(theory_module)
    for f in facts:
        theory.add(f)
    for e, truth_value in evidences:
        theory.add(Evidence(e, truth_value))
    solver = ProbLogSolver()
    solver.add(theory)
    model = solver.model()
    if not isinstance(model, ProbabilisticModel):
        raise ValueError(f"Expected a ProbabilisticModel, got {model}")
    # print(model)
    #for term, pr in model.term_probabilities.items():
    #    print(pr, "::", term, type(term), model.term_probabilities[term])
    for term, pr in expected:
        assert round(model.term_probabilities[term.to_model_object()], 3) == pr

