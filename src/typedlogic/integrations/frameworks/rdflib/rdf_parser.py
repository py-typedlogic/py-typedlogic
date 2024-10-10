from pathlib import Path
from typing import Union, TextIO
from rdflib import RDFS, Graph
from typedlogic import Theory
from typedlogic.integrations.frameworks.rdflib import rdfs, rdf
from typedlogic.parser import Parser
from typedlogic.parsers.pyparser import PythonParser


class RDFParser(Parser):
    def parse(self, source: Union[Path, str, TextIO], **kwargs) -> Theory:
        g = Graph()
        g.parse(source, format="ttl")
        parser = PythonParser()
        theory = parser.transform(rdfs)
        for sentence in rdf.generate_sentences(g):
            theory.add(sentence)
        return theory