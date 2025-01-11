"""
Axioms for OWL-Full via RDF bridge.

INCOMPLETE!

Corresponds to [OWL 2 RL Docs](https://www.w3.org/TR/owl2-profiles/#Reasoning_in_OWL_2_RL_and_RDF_Graphs_using_Rules)
"""
from rdflib import OWL

from typedlogic import And, Not
from typedlogic.decorators import axiom
from typedlogic.integrations.frameworks.rdflib.rdfs import Triple, Node, RDFS_SUBCLASS_OF, RDF_TYPE

OWL_SAME_AS = OWL.sameAs
OWL_DIFFERENT_FROM = OWL.differentFrom
OWL_EQUIVALENT_CLASS = OWL.equivalentClass
OWL_THING = OWL.Thing
OWL_NOTHING = OWL.Nothing

# Table 4


@axiom
def eq_ref(s: Node, p: Node, o: Node):
    """
    EQ REF axiom

    :param s:
    :param p:
    :param o:
    :return:
    """
    assert Triple(s, p, o) >> And(
        Triple(s, OWL_SAME_AS, s),
        Triple(p, OWL_SAME_AS, p),
        Triple(o, OWL_SAME_AS, o),
    )


@axiom
def eq_sym(x: Node, y: Node):
    assert Triple(x, OWL_SAME_AS, y) >> Triple(y, OWL_SAME_AS, x)


@axiom
def eq_trans(x: Node, y: Node, z: Node):
    assert And(
        Triple(x, OWL_SAME_AS, y),
        Triple(y, OWL_SAME_AS, z),
    ) >> Triple(x, OWL_SAME_AS, z)


@axiom
def eq_rep_s(s: Node, p: Node, o: Node, s2: Node):
    assert And(
        Triple(s, p, o),
        Triple(s, OWL_SAME_AS, s2),
    ) >> Triple(s2, p, o)


@axiom
def eq_rep_o(s: Node, p: Node, o: Node, o2: Node):
    assert And(
        Triple(s, p, o),
        Triple(o, OWL_SAME_AS, o2),
    ) >> Triple(s, p, o2)


@axiom
def eq_rep_p(s: Node, p: Node, o: Node, p2: Node):
    assert And(
        Triple(s, p, o),
        Triple(p, OWL_SAME_AS, p2),
    ) >> Triple(s, p2, o)


@axiom
def eq_diff1(x: Node, y: Node):
    assert Not(And(Triple(x, OWL_SAME_AS, y), Triple(x, OWL_DIFFERENT_FROM, y)))


# TODO: lists


# Table 9 TODO
@axiom
def scm_cls(c: Node):
    assert Triple(c, RDF_TYPE, OWL.Class) >> And(
        Triple(c, RDFS_SUBCLASS_OF, c),
        Triple(c, OWL_EQUIVALENT_CLASS, c),
        Triple(c, RDFS_SUBCLASS_OF, OWL_THING),
        Triple(OWL_NOTHING, RDFS_SUBCLASS_OF, c),
    )
