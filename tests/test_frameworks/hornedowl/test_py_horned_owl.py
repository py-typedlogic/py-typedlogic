import pyhornedowl.model as phom
import pytest
from pyhornedowl.pyhornedowl import PyIndexedOntology
from typedlogic import Exists, Forall, Term, Variable
from typedlogic.integrations.frameworks.hornedowl.horned_owl_bridge import (
    ConversionContext,
    load_ontology,
    translate_from_horned_owl,
    translate_to_horned_owl,
)
from typedlogic.integrations.frameworks.owldl.reasoner import OWLReasoner

from tests.test_frameworks.hornedowl import HORNEDOWL_INPUT_DIR

RO = HORNEDOWL_INPUT_DIR / "ro.ofn"


@pytest.mark.parametrize(
    "input_path",
    [
        RO,
    ],
)
def test_parse(input_path):
    axioms = load_ontology(input_path)
    reasoner = OWLReasoner()
    for a in axioms:
        # print(a)
        fol = a.as_fol()
        if fol:
            # print(fol)
            # print(as_sexpr(a))
            # try:
            ##    print(as_prolog(a.as_fol()))
            # except NotInProfileError as e:
            #    print(f"NO PROLOG: {e}")
            reasoner.add(fol)
        else:
            print(f"NO TRANSLATION: {a}")
    # TODO: make IRIs safe
    reasoner.add(Term("part_of", "a", "b"))
    reasoner.add(Term("part_of", "b", "c"))
    assert reasoner.coherent()
    parts = set()
    for fact in reasoner.model().iter_retrieve("has_part", "c"):
        # print(fact)
        parts.add(fact.values[1])
    assert parts == {"a", "b"}
    # print(reasoner.solver.dump()


o = PyIndexedOntology()
o.add_prefix_mapping("", "http://example.org/")
C = o.clazz("C")
D = o.clazz("D")
P = o.object_property("P")
Q = o.object_property("Q")
DP = o.data_property("DP")
DTL_1 = phom.DatatypeLiteral("1", phom.IRI.parse("http://www.w3.org/2001/XMLSchema#integer"))
IND_I = o.named_individual("ind_i")
IND_J = o.named_individual("ind_j")
VAR_I = Variable("I")


@pytest.mark.parametrize(
    "horned_owl_object,expected_fol",
    [
        (phom.SubClassOf(sub=C, sup=D), Forall([VAR_I], Term("C", VAR_I) >> Term("D", VAR_I))),
        (phom.EquivalentClasses([C, D]), None),
        (phom.SubClassOf(sub=C, sup=phom.ObjectSomeValuesFrom(P, D)), None),
        (phom.SubObjectPropertyOf(P, Q), None),
        (phom.EquivalentObjectProperties([P, Q]), None),
        (phom.ObjectPropertyDomain(P, C), None),
        (phom.ObjectPropertyRange(P, D), None),
        (phom.InverseObjectProperties(P, Q), None),
        (phom.FunctionalObjectProperty(P), None),
        (phom.InverseFunctionalObjectProperty(P), None),
        (phom.TransitiveObjectProperty(P), None),
        (phom.SymmetricObjectProperty(P), None),
        (phom.AsymmetricObjectProperty(P), None),
        (phom.IrreflexiveObjectProperty(P), ~Exists([VAR_I], Term("P", VAR_I, VAR_I))),
        (phom.ReflexiveObjectProperty(P), None),
        # Skip problematic test - https://github.com/ontology-tools/py-horned-owl/issues/31
        pytest.param(
            phom.ObjectPropertyAssertion(P, IND_I, IND_J),
            None,
            marks=pytest.mark.skip(reason="Known issue in py-horned-owl #31")
        ),
        (phom.ClassAssertion(C, IND_I), None),
        (phom.FacetRestriction(phom.Facet.MinExclusive, DTL_1), None),
        (
            phom.DatatypeRestriction(
                phom.Datatype(phom.IRI.parse("DT")), [phom.FacetRestriction(phom.Facet.MinExclusive, DTL_1)]
            ),
            None,
        ),
    ],
)
def test_translate(horned_owl_object, expected_fol):
    context = ConversionContext(ontology=o)
    pyowl_object = translate_from_horned_owl(horned_owl_object, {})
    # print(pyowl_object)
    as_fol = pyowl_object.as_fol()
    # print(f"From {horned_owl_object} got {pyowl_object}\n  {as_fol} ({repr(as_fol)})")
    if expected_fol:
        # This test is relatively rigid, it assumes the same variable *names* are used.
        # in future this could be made less rigid by checking semantics of expression
        assert as_fol == expected_fol, f"{as_fol} != {expected_fol}"
    # print(repr(pyowl_object))
    roundtripped = translate_to_horned_owl(pyowl_object, context)
    # print(roundtripped)
    assert roundtripped == horned_owl_object


def test_ad_hoc():
    f = phom.Facet
    me = f.MinExclusive
    print(me)
    me2 = f.MinExclusive
    print(me2)
    assert me == me2
    pyowl_object = translate_from_horned_owl(DTL_1, {})
    print(repr(pyowl_object))
    print(type(pyowl_object.datatype_iri))
    context = ConversionContext(ontology=o)
    roundtripped = translate_to_horned_owl(pyowl_object, context)
    dtr = phom.DatatypeRestriction(
        phom.Datatype(phom.IRI.parse("http://www.w3.org/2001/XMLSchema#integer")),
        [phom.FacetRestriction(phom.Facet.MinExclusive, DTL_1)],
    )
    pyowl_dtr = translate_from_horned_owl(dtr, {})
    print(repr(pyowl_dtr))
    print(type(pyowl_dtr.first))
    roundtripped = translate_to_horned_owl(pyowl_dtr, context)
    dpa = phom.DataPropertyAssertion(DP, IND_I, DTL_1)
    print(dpa)
    # https://github.com/ontology-tools/py-horned-owl/issues/31
    # dpa = phom.DataPropertyAssertion(dp=DP, from=IND_I, to=DTL_1)
