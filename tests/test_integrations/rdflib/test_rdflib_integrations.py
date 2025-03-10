from pathlib import Path

import rdflib
from rdflib import RDFS, Graph
from typedlogic import Forall, Term
from typedlogic.integrations.frameworks.rdflib import rdf, rdfs
from typedlogic.integrations.frameworks.rdflib.rdf_parser import RDFParser
from typedlogic.integrations.solvers.souffle import SouffleSolver
from typedlogic.integrations.solvers.z3 import Z3Solver
from typedlogic.parsers.pyparser.python_parser import PythonParser
from typedlogic.transformations import replace_constants, simple_prolog_transform

EX = rdflib.Namespace("http://example.org/ex/")


INPUT_DIR = Path(__file__).parent / "input"
TEST_TTL = str(INPUT_DIR / "test.ttl")


def test_inference():
    g = Graph()
    g.parse(TEST_TTL, format="ttl")
    s = SouffleSolver()
    parser = PythonParser()
    theory = parser.transform(rdfs)
    s.add(theory)
    for sentence in theory.sentences:
        sentence = replace_constants(sentence, theory.constants)
        tr_sentences = simple_prolog_transform(sentence)
        # for trs in tr_sentences:
        #    print(f"  TR={trs}")
        #    # print(f"     {as_prolog(trs)}")
    for sentence in rdf.generate_sentences(g):
        s.add(sentence)
    model = s.model()
    assert model
    for fact in model.ground_terms:
        print("FACT", fact)
    assert Term("Type", str(EX["Fido"]), str(EX.Dog)) in model.ground_terms
    assert Term("Type", str(EX["Fido"]), str(EX.Animal)) in model.ground_terms
    assert Term("Type", str(EX["Fred"]), str(EX.Human)) in model.ground_terms


def test_parser():
    parser = RDFParser()
    theory = parser.parse(TEST_TTL)
    s = SouffleSolver()
    s.add(theory)
    model = s.model()
    assert model
    for fact in model.ground_terms:
        print("FACT", fact)
    assert Term("Type", str(EX["Fido"]), str(EX.Dog)) in model.ground_terms
    assert Term("Type", str(EX["Fido"]), str(EX.Animal)) in model.ground_terms
    assert Term("Type", str(EX["Fred"]), str(EX.Human)) in model.ground_terms


def test_load():
    parser = PythonParser()
    theory = parser.transform(rdf)
    for s in theory.sentences:
        print(f"S={s}")
        if isinstance(s, Forall):
            print(f"  INNER: {type(s.sentence)} {s.sentence}")


def test_check():
    s = Z3Solver()
    parser = PythonParser()
    theory = parser.transform(rdf)
    s.add(theory.predicate_definitions)
    print(theory.sentence_groups[0].sentences[0])
    s.add(theory.sentence_groups[0].sentences[0])
    s.add(rdf.Triple(EX.Cat, RDFS.subClassOf, EX.Animal))
    print(s.dump())
    model = s.model()
