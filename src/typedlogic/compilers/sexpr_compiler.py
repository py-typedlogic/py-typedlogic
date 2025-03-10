import json
from dataclasses import dataclass
from typing import ClassVar, Optional, Union

from typedlogic import Sentence, Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import SExpression, as_sexpr


def _render(s: SExpression, position=0, depth=0) -> str:
    rendered = ""
    if position > 0:
        rendered += "\n"
        for _ in range(depth):
            rendered += "  "
    if isinstance(s, list):
        return rendered + f"({' '.join([_render(x, i, depth+1) for i, x in enumerate(s)])})"
    if isinstance(s, dict):
        raise ValueError(f"Cannot render dict: {s}")
    if position == 0:
        return str(s)
    return json.dumps(s)


@dataclass
class SExprCompiler(Compiler):
    default_suffix: ClassVar[str] = "sexpr"

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        """
        Compile a Theory object into S-Expressions.

        Example:
        -------
            >>> from typedlogic import *
            >>> theory = Theory()
            >>> x = Variable("x")
            >>> theory.predicate_definitions = [PredicateDefinition("P", {"x": "str"}),
            ...              PredicateDefinition("Q", {"x": "str"})]
            >>> s = Implies(Term("P", x), Term("Q", x))
            >>> theory.add(sentence=s)
            >>> compiler = SExprCompiler()
            >>> print(compiler.compile(theory))
            (Theory
              (name null)
              (constants
                (dict
                  ()))
              (type_definitions
                (dict
                  ()))
              (predicate_definitions
                ((PredicateDefinition
                    (predicate "P")
                    (arguments
                      (dict
                        ((x "str"))))
                    (description null)
                    (metadata null)
                    (parents null)
                    (python_class null))
                  (PredicateDefinition
                    (predicate "Q")
                    (arguments
                      (dict
                        ((x "str"))))
                    (description null)
                    (metadata null)
                    (parents null)
                    (python_class null))))
              (sentence_groups
                ((SentenceGroup
                    (name "Sentences")
                    (group_type null)
                    (docstring null)
                    (sentences
                      ((Implies
                          (P
                            (Variable "x"))
                          (Q
                            (Variable "x")))))
                    (_annotations null))))
              (ground_terms
                ())
              (_annotations null)
              (source_module_name null))

        :param theory:
        :param syntax:
        :param kwargs:
        :return:

        """
        sexpr = as_sexpr(theory)
        return _render(sexpr)

    def compile_sentence(self, sentence: Sentence, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        sexpr = as_sexpr(sentence)
        return _render(sexpr)
