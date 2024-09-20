from typing import ClassVar, Optional, Union

from typedlogic import Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.integrations.solvers.z3.z3_solver import Z3Solver


class Z3Compiler(Compiler):
    """
    Implementation of the Compiler interface for Z3
    """

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None,  **kwargs) -> str:
        solver = Z3Solver()
        solver.add(theory)
        if syntax is None:
            syntax = ModelSyntax.SEXPR
        if syntax == ModelSyntax.SEXPR:
            return solver.wrapped_solver.sexpr()
        elif syntax == ModelSyntax.FUNCTIONAL:
            return str(solver.wrapped_solver)
        else:
            raise ValueError(f"Unknown syntax: {syntax}")

class Z3SExprCompiler(Z3Compiler):
    """
    Implementation of the Compiler interface for Z3 with S-Expression syntax
    """

    default_suffix: ClassVar[str] = "z3.sxpr"

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        return super().compile(theory, ModelSyntax.SEXPR, **kwargs)

class Z3FunctionalCompiler(Z3Compiler):
    """
    Implementation of the Compiler interface for Z3 with functional syntax
    """

    default_suffix: ClassVar[str] = "z3.fun"

    def compile(self, theory: Theory,syntax: Optional[Union[str, ModelSyntax]] = None,  **kwargs) -> str:
        return super().compile(theory, ModelSyntax.FUNCTIONAL, **kwargs)
