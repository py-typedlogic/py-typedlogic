from dataclasses import dataclass

from rdflib import RDF, RDFS

from typedlogic import FactMixin, Iff
from typedlogic.decorators import axiom
from typedlogic.integrations.frameworks.rdflib.rdf import Node, Triple

SUBCLASS_OF = RDFS.subClassOf
RDF_TYPE = RDF.type
RDFS_DOMAIN = RDFS.domain
RDFS_RANGE = RDFS.range

@dataclass
class OWLClass(FactMixin):
    node: Node

@dataclass
class RDFProperty(FactMixin):
    node: Node

@dataclass
class SubClassOf(FactMixin):
    subject: Node
    object: Node

@dataclass
class SubPropertyOf(FactMixin):
    subject: Node
    object: Node

@dataclass
class Type(FactMixin):
    subject: Node
    object: Node

@dataclass
class Domain(FactMixin):
    subject: Node
    object: Node


@dataclass
class Range(FactMixin):
    subject: Node
    object: Node

@axiom
def transitivity_and_reflexivity(s: Node, z: Node, o: Node):
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
    assert Iff((Triple(s, p, o) and (p == SUBCLASS_OF)),
        SubClassOf(s, o))
    assert Iff((Triple(s, p, o) and (p == RDF_TYPE)),
               Type(s, o))
    assert Iff((Triple(s, p, o) and (p == RDFS_DOMAIN)),
               Domain(s, o))
    assert Iff((Triple(s, p, o) and (p == RDFS_RANGE)),
               Range(s, o))
