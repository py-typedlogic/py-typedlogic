from pathlib import Path
from typing import TextIO, Union

from rdflib import Graph

from typedlogic import Theory, Term
from typedlogic.integrations.frameworks.rdflib import rdf, rdfs
from typedlogic.parser import Parser
from typedlogic.parsers.pyparser import PythonParser


class RDFParser(Parser):
    """
    Parsers RDF Graphs into typedlogic theories.

    Example:

        >>> parser = RDFParser()
        >>> import rdflib as rdflib
        >>> from rdflib.namespace import RDF, RDFS
        >>> g = rdflib.Graph()
        >>> EX = rdflib.Namespace("http://example.org/")
        >>> _ = g.add((EX.hasPet, RDFS.domain, EX.Human))
        >>> _ = g.add((EX.hasPet, RDFS.range, EX.Animal))
        >>> _ = g.add((EX.Fred, EX.hasPet, EX.Fido))
        >>> theory = parser.parse(g)
        >>> preds = [pd.predicate for pd in theory.predicate_definitions]
        >>> for pred in sorted(preds):
        ...     print(pred)
        <BLANKLINE>
        ...
        SubClassOf
        SubPropertyOf
        Triple
        ...

    Note that the predicates here are predicates from the theory of RDF, RDFS, and OWL-Full.
    "user-defined" predicates (e.g. hasPet) are not in this list, as these are mapped to instances
    of Triple.

        >>> facts = [fact.as_sexpr() for fact in theory.ground_terms]
        >>> for fact in sorted(facts):
        ...     print(fact)
        ['Triple', rdflib.term.URIRef('http://example.org/Fred'), rdflib.term.URIRef('http://example.org/hasPet'), rdflib.term.URIRef('http://example.org/Fido')]
        ['Triple', rdflib.term.URIRef('http://example.org/hasPet'), rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#domain'), rdflib.term.URIRef('http://example.org/Human')]
        ['Triple', rdflib.term.URIRef('http://example.org/hasPet'), rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#range'), rdflib.term.URIRef('http://example.org/Animal')]

    After this other facts can be inferred using a solver.

        >>> from typedlogic.registry import get_solver
        >>> s = get_solver("souffle")
        >>> s.add(theory)
        >>> model = s.model()
        >>> assert model
        >>> from typedlogic.integrations.frameworks.rdflib.rdfs import Type
        >>> for fact in sorted(model.retrieve(Type)):
        ...     print(fact)
        Type(http://example.org/Fido, http://example.org/Animal)
        Type(http://example.org/Fred, http://example.org/Human)

    """

    def parse(self, source: Union[Path, str, TextIO, Graph], format="ttl", **kwargs) -> Theory:
        """
        Parse am RDF Graph to a theory.

        :param source: rdflib Graph pr a path to a graph
        :param format: rdflib accepted format
        :param kwargs:
        :return: Parsed theory
        """
        if isinstance(source, Graph):
            g = source
        else:
            g = Graph()
            g.parse(source, format=format)
        parser = PythonParser()
        theory = parser.transform(rdfs)
        for sentence in rdf.generate_sentences(g):
            t = sentence.to_model_object()
            if not isinstance(t, Term):
                raise ValueError(f"expected term: {t}")
            theory.ground_terms.append(t)
        return theory
