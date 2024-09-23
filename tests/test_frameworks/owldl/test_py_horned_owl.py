from tests import INPUT_DIR
from typedlogic import Term
from typedlogic.integrations.frameworks.owldl.horned_owl_bridge import load_ontology
from typedlogic.integrations.frameworks.owldl.reasoner import OWLReasoner
from typedlogic.transformations import as_prolog

RO = INPUT_DIR / "ro.ofn"

def test_parse():
    axioms = load_ontology(RO)
    reasoner = OWLReasoner()
    for a in axioms:
        #print(a)
        fol = a.as_fol()
        if fol:
            #print(fol)
            #print(as_prolog(a.as_fol()))
            reasoner.add(fol)
        else:
            print(f"NO TRANSLATION: {a}")
    # TODO: make IRIs safe
    reasoner.add(Term("part_of", "a", "b"))
    reasoner.add(Term("part_of", "b", "c"))
    assert reasoner.coherent()
    parts = set()
    for fact in reasoner.model().iter_retrieve("has_part", "c"):
        print(fact)
        parts.add(fact.values[1])
    assert parts == {"a", "b"}
    #print(reasoner.solver.dump()



