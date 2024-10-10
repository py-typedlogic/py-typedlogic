from dataclasses import dataclass
from typing import ClassVar, Optional, Union

from typedlogic import Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.transformations import as_fol


@dataclass
class FOLCompiler(Compiler):
    """
    A compiler that generates First Order Logic (FOL) syntax.
    """

    default_suffix: ClassVar[str] = "fol"

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        """
        Compile a Theory object into FOL syntax.

        Example:
        -------
            >>> from typedlogic.registry import get_compiler
            >>> from typedlogic import *
            >>> theory = Theory()
            >>> x = Variable("x")
            >>> theory.predicate_definitions = [PredicateDefinition("P", {"x": "str"}),
            ...              PredicateDefinition("Q", {"x": "str"})]
            >>> s = Forall([x], Implies(Term("P", x), Term("Q", x)))
            >>> theory.add(sentence=s)
            >>> compiler = get_compiler("fol")
            >>> print(compiler.compile(theory))
            ∀[x]. P(x) → Q(x)

        :param theory:
        :param syntax:
        :param kwargs:
        :return:

        """
        lines = []
        for s in theory.sentences:
            lines.append(as_fol(s))
        return "\n".join(lines)
