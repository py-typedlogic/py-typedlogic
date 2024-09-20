from dataclasses import dataclass
from typing import ClassVar, Optional, Union

import yaml

from typedlogic import Sentence, Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import as_object
from typedlogic.parsers.yaml_parser import YAMLParser


@dataclass
class YAMLCompiler(Compiler):

    default_suffix: ClassVar[str] = "yaml"
    parser_class = YAMLParser

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        """
        Compile a Theory object into YAML code.

        Example:
        -------
            >>> from typedlogic import *
            >>> theory = Theory()
            >>> x = Variable("x")
            >>> theory.predicate_definitions = [PredicateDefinition("P", {"x": "str"}),
            ...              PredicateDefinition("Q", {"x": "str"})]
            >>> s = Implies(Term("P", x), Term("Q", x))
            >>> theory.add(sentence=s)
            >>> compiler = YAMLCompiler()
            >>> print(compiler.compile(theory))
            type: Theory
            constants: {}
            type_definitions: {}
            predicate_definitions:
            - type: PredicateDefinition
              predicate: P
              arguments:
                x: str
            - type: PredicateDefinition
              predicate: Q
              arguments:
                x: str
            sentence_groups:
            - type: SentenceGroup
              name: Sentences
              sentences:
              - type: Implies
                arguments:
                - type: Term
                  arguments:
                  - P
                  - type: Variable
                    arguments:
                    - x
                - type: Term
                  arguments:
                  - Q
                  - type: Variable
                    arguments:
                    - x
            ground_terms: []

        :param theory:
        :param syntax:
        :param kwargs:
        :return:

        """
        obj = as_object(theory)
        return yaml.dump(obj, sort_keys=False)

    def compile_sentence(self, sentence: Sentence, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        obj = as_object(sentence)
        return yaml.dump(obj, sort_keys=False)
