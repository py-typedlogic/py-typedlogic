"""
Theory corresponding to RDF-Schema (RDFS)
"""
from dataclasses import dataclass

from rdflib import RDF, RDFS

from typedlogic import FactMixin, Iff
from typedlogic.decorators import axiom
from typedlogic.integrations.frameworks.rdflib.rdf import Node, Triple

RDFS_SUBCLASS_OF = RDFS.subClassOf
RDF_TYPE = RDF.type
RDFS_DOMAIN = RDFS.domain
RDFS_RANGE = RDFS.range


@dataclass
class OWLClass(FactMixin):
    """
    True if node is an OWL Class

    Note that even though OWL predicates are typically defined in owlfull.py,
    owl:Class is considered part of RDFS.
    """

    node: Node


@dataclass
class RDFProperty(FactMixin):
    """
    RDF.Property axiom
    """

    node: Node


@dataclass
class SubClassOf(FactMixin):
    """
    SubClassOf axiom
    """

    subject: Node
    object: Node


@dataclass
class SubPropertyOf(FactMixin):
    """
    SubPropertyOf axiom
    """

    subject: Node
    object: Node


@dataclass
class Type(FactMixin):
    """
    rdf.Type axiom
    """

    subject: Node
    object: Node


@dataclass
class Domain(FactMixin):
    """
    property domain axiom
    """

    subject: Node
    object: Node


@dataclass
class Range(FactMixin):
    """
    property range axiom
    """

    subject: Node
    object: Node


@axiom
def transitivity_and_reflexivity(s: Node, z: Node, o: Node):
    """
    Axioms for transitivity and reflexivity.

    :param s: subject
    :param z: intermediate
    :param o: object
    :return:
    """
    if SubClassOf(s, z) and SubClassOf(z, o):
        assert SubClassOf(s, o)
    if OWLClass(s):
        assert SubClassOf(s, s)
    if RDFProperty(s):
        assert SubPropertyOf(s, s)
    if SubPropertyOf(s, z) and SubPropertyOf(z, o):
        assert SubPropertyOf(s, o)


@axiom
def type_propagation(s: Node, c: Node, d: Node):
    """
    Propagation of rdf:type up class hierarchy

    :param s: subject
    :param c: asserted class
    :param d: inferred class
    :return:
    """
    if Type(s, c) and SubClassOf(c, d):
        assert Type(s, d)


@axiom
def domain_and_range(s: Node, p: Node, o: Node, c: Node):
    if Triple(s, p, o) & Range(p, c):
        Type(o, c)
    if Triple(s, p, o) & Domain(p, c):
        Type(s, c)


@axiom
def classification_of_triples(s: Node, p: Node, o: Node):
    assert Iff((Triple(s, p, o) and (p == RDFS_SUBCLASS_OF)), SubClassOf(s, o))
    assert Iff((Triple(s, p, o) and (p == RDF_TYPE)), Type(s, o))
    assert Iff((Triple(s, p, o) and (p == RDFS_DOMAIN)), Domain(s, o))
    assert Iff((Triple(s, p, o) and (p == RDFS_RANGE)), Range(s, o))
