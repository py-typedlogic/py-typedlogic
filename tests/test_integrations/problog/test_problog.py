from typing import Dict, Union

import pytest
from problog import get_evaluatable
from problog.logic import Term
from problog.program import PrologString
from typedlogic.datamodel import Forall, Variable
from typedlogic.extensions.probabilistic import Evidence, ProbabilisticModel, Probability, That
from typedlogic.integrations.solvers.problog.problog_compiler import ProbLogCompiler
from typedlogic.integrations.solvers.problog.problog_solver import ProbLogSolver
from typedlogic.parsers.pyparser.introspection import translate_module_to_theory

from tests.theorems.probabilistic import coins, coins2, smokers
import tests.theorems.probabilistic.diagnosis as diagnosis


def as_simple_dict(result: Dict[Union[Term, str], float], precision=3) -> Dict[str, float]:
    return {str(k): round(v, precision) for k, v in result.items()}


# TODO: These tests don't actually test ptl behavior and can be removed in future
@pytest.mark.parametrize(
    "prog,expected",
    [
        (
            """
            coin(c1). coin(c2).
            0.4::heads(C); 0.6::tails(C) :- coin(C).
            win :- heads(C).
            evidence(heads(c1), false).
            query(win).
            query(coin(_)).
            """,
            {"win": 0.4, "coin(c1)": 1.0, "coin(c2)": 1.0},
        ),
        (
            """
            coin(c1). coin(c2).
            0.4::heads(C) :- coin(C).
            0.6::tails(C) :- coin(C).
            win :- heads(C).
            query(win).
            """,
            {"win": 0.64},
        ),
        (
            """
            coin(c1). coin(c2). coin(c3).
            0.4::heads(C); 0.6::tails(C) :- coin(C).
            win :- heads(C).
            query(win).
            """,
            {"win": 0.784},
        ),
        (
            """
            coin("c1"). coin(c2). coin(c3).
            0.4::heads(C); 0.6::tails(C) :- coin(C).
            win :- heads(C).
            evidence(heads(c3), true).
            query(win).
            """,
            {"win": 1.0},
        ),
    ],
)
def test_problog(prog, expected):
    p = PrologString(prog)
    ev = get_evaluatable()
    result = ev.create_from(p).evaluate()
    result = as_simple_dict(result)
    assert result == expected


@pytest.mark.parametrize(
    "theory_module,facts,evidences",
    [
        (coins, [coins.Coin("c1"), coins.Coin("c2")], [(coins.Heads("c1"), False)]),
        (coins2, [coins2.Coin("c1"), coins2.Coin("c2")], [(coins2.Heads("c1"), False)]),
    ],
)
def test_compiler(theory_module, facts, evidences):
    theory = translate_module_to_theory(theory_module)
    for f in facts:
        theory.add(f)
    for e, truth_value in evidences:
        theory.add(Evidence(e, truth_value))
    # theory.add(Probability(0.4, coins.Heads("c1")))
    compiler = ProbLogCompiler()
    compiled = compiler.compile(theory)
    assert "0.4::heads(C) :- coin(C)." in compiled


@pytest.mark.parametrize(
    "theory_module,facts,evidences,expected",
    [
        (
            coins,
            [coins.Coin("c1"), coins.Coin("c2")],
            [(coins.Heads("c1"), False)],
            [(coins.Win(), 0.4), (coins.Heads("c1"), 0.0), (coins.Heads("c2"), 0.4)],
        ),
        (
            coins2,
            [coins2.Coin("c1"), coins2.Coin("c2")],
            [(coins2.Heads("c1"), False)],
            [(coins2.Win(), 0.4), (coins2.Heads("c1"), 0.0), (coins2.Heads("c2"), 0.4)],
        ),
        (
            smokers,
            [],
            [],
            [(smokers.Asthma("joris"), 0.169)],
        ),
        (
            smokers,
            [],
            [(smokers.Asthma("joris"), True)],
            [(smokers.Asthma("joris"), 1.0)],
        ),
    ],
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
    # for term, pr in model.term_probabilities.items():
    #    print(pr, "::", term, type(term), model.term_probabilities[term])
    for term, pr in expected:
        assert round(model.term_probabilities[term.to_model_object()], 3) == pr

@pytest.mark.parametrize(
    "facts,disease_priors,phenotype_priors,d2p,evidences",
    [
        (
            [
                diagnosis.SubClassOf("SYNOPHYRIS", "FACIAL_FEATURES"),
                diagnosis.SubClassOf("LONG_EYELASHES", "FACIAL_FEATURES"),
                diagnosis.SubClassOf("CLEFT_PALATE", "FACIAL_FEATURES"),
                diagnosis.SubClassOf("RECURRENT_INFECTIONS", "IMMUNE_SYSTEM_PHENOTYPE"),
                diagnosis.SubClassOf("GENERALIZED_SKELETAL_DYSPLASIA_PHENOTYPE", "SKELETAL_DYSPLASIA_PHENOTYPE"),
                diagnosis.SubClassOf("OPD", "SKELETAL_DYSPLASIA"),
                diagnosis.SubClassOf("OPD1", "OPD"),
                diagnosis.SubClassOf("OPD2", "OPD"),
                diagnosis.Person("joris"),
                diagnosis.Person("jed"),
                diagnosis.Person("jay"),
                diagnosis.Person("healthy_heather"),
                diagnosis.Person("unknown_ursula"),
                diagnosis.Person("opd_patientA"),
                diagnosis.Person("opd_patientB"),
            ],
            [
                (0.00001, "CDLS"),
                (0.0001, "CF"),
                (0.000001, "OPD1"),
                (0.000001, "OPD2"),
            ],
            [
                (0.00001, "SYNOPHYRIS"),
                (0.00001, "LONG_EYELASHES"),
                (0.001, "RECURRENT_INFECTIONS"),
                (0.0005, "CLEFT_PALATE"),
                (0.0001, "SKELETAL_DYSPLASIA_PHENOTYPE"),
                (0.0001, "GENERALIZED_SKELETAL_DYSPLASIA_PHENOTYPE"),
            ],
            [
                (0.95, "CDLS", "SYNOPHYRIS"),
                (0.85, "CDLS", "LONG_EYELASHES"),
                (1.0, "CDLS", "NIPBL_MUTATION"),
                (0.90, "CF", "RECURRENT_INFECTIONS"),
                (0.01, "CF", "FACIAL_FEATURES"),
                (1.0, "CF", "CFTR_MUTATION"),
                (1.0, "SKELETAL_DYSPLASIA", "SKELETAL_DYSPLASIA_PHENOTYPE"),
                (0.95, "OPD", "CLEFT_PALATE"),
                (0.95, "OPD", "GENERALIZED_SKELETAL_DYSPLASIA_PHENOTYPE"),
                (1.0, "OPD", "FLNA_MUTATION"),
                # mutated genes
                #(0.00001, "NIPBL", "MUTATED"),
                #(0.00001, "CFTR", "MUTATED"),
                
            ],
            [
                (diagnosis.PersonHasObservation("joris", "SYNOPHYRIS"), True),
                (diagnosis.PersonHasObservation("joris", "LONG_EYELASHES"), True),
                (diagnosis.PersonHasObservation("joris", "RECURRENT_INFECTIONS"), True),
                (diagnosis.PersonHasObservation("jed", "SYNOPHYRIS"), True),
                (diagnosis.PersonHasObservation("jed", "LONG_EYELASHES"), False),
                (diagnosis.PersonHasObservation("jed", "IMMUNE_SYSTEM_PHENOTYPE"), False),
                (diagnosis.PersonHasObservation("jay", "SYNOPHYRIS"), False),
                (diagnosis.PersonHasObservation("jay", "LONG_EYELASHES"), False),
                (diagnosis.PersonHasObservation("jay", "RECURRENT_INFECTIONS"), True),
                (diagnosis.PersonHasObservation("healthy_heather", "FACIAL_FEATURES"), False),
                (diagnosis.PersonHasObservation("healthy_heather", "IMMUNE_SYSTEM_PHENOTYPE"), False),
                (diagnosis.PersonHasObservation("opd_patientA", "SKELETAL_DYSPLASIA_PHENOTYPE"), True),
                (diagnosis.PersonHasObservation("opd_patientB", "CLEFT_PALATE"), True),
                (diagnosis.PersonHasObservation("opd_patientB", "GENERALIZED_SKELETAL_DYSPLASIA_PHENOTYPE"), True),
            ],
        ),
    ],
)
def test_diagnosis( 
    facts,
    disease_priors,
    phenotype_priors,
    d2p,
    evidences,
):
    theory = translate_module_to_theory(diagnosis)
    for f in facts:
        theory.add(f)
    p = Variable("P")
    for prior, d in disease_priors:
        theory.add(Probability(prior, That(diagnosis.Person(p) >> diagnosis.PersonHasDisease(p, d))))
    for prior, ph in phenotype_priors:
        theory.add(Probability(prior, That(diagnosis.Person(p) >> diagnosis.PersonHasPhenotype(p, ph))))
    for prior, d, ph in d2p:
        theory.add(Probability(prior, That(diagnosis.PersonHasDisease(p, d) >> diagnosis.PersonHasPhenotype(p, ph))))
    for e, truth_value in evidences:
        theory.add(Evidence(e, truth_value))
    compiler = ProbLogCompiler()
    compiled = compiler.compile(theory)
    print(compiled)
    solver = ProbLogSolver()
    solver.add(theory)
    model = solver.model()
    if not isinstance(model, ProbabilisticModel):
        raise ValueError(f"Expected a ProbabilisticModel, got {model}")
    # print(model)
    # for term, pr in model.term_probabilities.items():
    #    print(pr, "::", term, type(term), model.term_probabilities[term])
    print(model)
    for term, pr in model.term_probabilities.items():
        print(pr, "::", term, type(term), model.term_probabilities[term])
    print("\n## PersonHasMutation")
    for term, pr in model.retrieve_probabilities("PersonHasPhenotype"):
        # show 3 decimal places
        if "MUTAT" in str(term) and pr > 0.001:
            print(f"{pr:0.5f} {term}")
    print("\n## PersonHasDisease")
    for term, pr in model.retrieve_probabilities("PersonHasDisease"):
        # show 3 decimal places
        print(f"{pr:0.5f} {term}")
    
