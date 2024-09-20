from dataclasses import dataclass
from typing import ClassVar, Optional, Union

from typedlogic import Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.transformations import as_fol


@dataclass
class FOLCompiler(Compiler):

    default_suffix: ClassVar[str] = "fol"

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        lines = []
        for s in theory.sentences:
            lines.append(as_fol(s))
        return "\n".join(lines)
