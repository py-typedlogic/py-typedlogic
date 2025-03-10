"""
Theory corresponding to RDF.
"""
from dataclasses import dataclass
from typing import Iterator

import rdflib
from rdflib.term import Node

from typedlogic import FactMixin, axiom


@dataclass
class Triple(FactMixin):
    """
    A triple is the basic unit of information in RDF.
    """

    subject: Node
    predicate: Node
    object: Node


@dataclass
class NodeIntegerValue(FactMixin):
    node: Node
    value: int


@dataclass
class NodeStringValue(FactMixin):
    node: Node
    value: str


@dataclass
class IsIRI(FactMixin):
    node: Node


@dataclass
class IsBlank(FactMixin):
    node: Node


@axiom
def sp_iris(s: Node, p: Node, o: Node):
    """
    IRI rules for triples
    :param s:
    :param p:
    :param o:
    :return:
    """
    if Triple(s, p, o):
        IsIRI(p)
    if Triple(s, p, o):
        IsIRI(s) | IsBlank(s)


def generate_sentences(g: rdflib.Graph) -> Iterator[Triple]:
    # yield Triple(str(OWL.Thing), str(RDF.type), str(OWL.Thing))
    for s, p, o in g:
        if isinstance(o, rdflib.URIRef):
            # yield Triple(str(s), str(p), str(o))
            yield Triple(s, p, o)
        else:
            # TODO
            # yield Triple(str(s), str(p), str(o))
            yield Triple(s, p, o)
