import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import ClassVar, Iterator, List, Optional

from typedlogic import Sentence
from typedlogic.compilers.prover9_compiler import Prover9Compiler
from typedlogic.profiles import MixedProfile, OpenWorld, Profile, Unrestricted
from typedlogic.solver import Model, Solution, Solver

logger = logging.getLogger(__name__)


@dataclass
class Prover9Solver(Solver):
    """
    A solver that uses Prover9.

    Prover9 is an automated theorem prover for first-order and equational logic

    See [The Prover9 site](https://www.cs.unm.edu/~mccune/prover9/)

    Note that in order to use this integration, you need to [install Prover9](https://www.cs.unm.edu/~mccune/prover9/)
    and have it on your path.

    Example:
    -------
        >>> from typedlogic.integrations.solvers.prover9 import Prover9Solver
        >>> from typedlogic.parsers.pyparser import PythonParser
        >>> import tests.theorems.simple_contradiction as sc
        >>> solver = Prover9Solver()
        >>> solver.load(sc)
        >>> r = solver.check()
        >>> r.satisfiable
        False


    This solver does implements the open-world assumption.

    """

    exec_name: str = field(default="prover9")
    profile: ClassVar[Profile] = MixedProfile(Unrestricted(), OpenWorld())

    def models(self) -> Iterator[Model]:
        r = self.check()
        if r.satisfiable:
            yield Model()

    def prove(self, sentence: Sentence) -> Optional[bool]:
        proved = self._run(goals=[sentence])
        return proved

    def _run(self, goals: Optional[List[Sentence]] = None) -> bool:
        compiler = Prover9Compiler()
        # print(f"THEORY; n_sentences: {len(self.base_theory.sentences)}")
        program = compiler.compile(self.base_theory, goals=goals)

        # print(program)

        with tempfile.NamedTemporaryFile(suffix=".prover9", mode="w") as fp:
            fp.write(program)
            fp.flush()
            res = subprocess.run([self.exec_name, "-f", fp.name], capture_output=True)
            if res.returncode not in (0, 2):
                logger.error(res.stdout.decode())
                raise ValueError(f"Prover9 failed with return code {res.returncode}")

            if "THEOREM PROVED" in res.stdout.decode():
                return True
            else:
                return False

    def check(self) -> Solution:
        proved = self._run()
        unsat = not self.base_theory.goals and not proved
        return Solution(satisfiable=unsat)

    def dump(self) -> str:
        compiler = Prover9Compiler()
        return compiler.compile(self.base_theory)
