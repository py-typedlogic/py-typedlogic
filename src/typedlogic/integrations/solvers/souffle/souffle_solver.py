import csv
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Iterator

from typedlogic.integrations.solvers.souffle.souffle_compiler import SouffleCompiler
from typedlogic.profiles import (
    AllowsComparisonTerms,
    ClassicDatalog,
    MixedProfile,
    Profile,
    SingleModelSemantics,
    SortedLogic,
)
from typedlogic.solver import Model, Solution, Solver
from typedlogic.utils.term_maker import make_terms

logger = logging.getLogger(__name__)


@dataclass
class SouffleSolver(Solver):
    """
    A solver that uses Soufflé.

    Soufflé is a logic programming language inspired by Datalog. For more details,
    see [The Souffle site](https://souffle-lang.github.io/).

    Note that in order to use this integration, you need to [install Souffle](https://souffle-lang.github.io/install)
    and have it on your path.

        >>> from typedlogic.integrations.frameworks.pydantic import FactBaseModel
        >>> class AncestorOf(FactBaseModel):
        ...     ancestor: str
        ...     descendant: str
        >>> solver = SouffleSolver()
        >>> from typedlogic import SentenceGroup, PredicateDefinition
        >>> solver.add_predicate_definition(PredicateDefinition(predicate="AncestorOf", arguments={'ancestor': str, 'descendant': str}))
        >>> solver.add_fact(AncestorOf(ancestor='p1', descendant='p1a'))
        >>> solver.add_fact(AncestorOf(ancestor='p1a', descendant='p1aa'))
        >>> aa = SentenceGroup(name="transitivity-of-ancestor-of")
        >>> solver.add_sentence_group(aa)
        >>> soln = solver.check()

    This solver does not implement the open-world assumption.

        >>> from typedlogic.profiles import OpenWorld
        >>> solver.profile.impl(OpenWorld)
        False

    """

    exec_name: str = field(default="souffle")
    profile: ClassVar[Profile] = MixedProfile(
        ClassicDatalog(), SortedLogic(), AllowsComparisonTerms(), SingleModelSemantics()
    )

    def models(self) -> Iterator[Model]:
        compiler = SouffleCompiler()
        program = compiler.compile(self.base_theory)
        pdmap = {}

        facts = []
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create output directives for each predicate
            output_files = {}
            input_files = {}
            for pd in self.base_theory.predicate_definitions:
                pred = pd.predicate
                pdmap[pred] = pd
                output_file = Path(temp_dir) / f"{pred}.csv"
                output_files[pred] = str(output_file)
                program += f'\n.output {pred}(IO=file, filename="{output_file}")\n'
                input_file = Path(temp_dir) / f"{pred}__in.csv"
                input_files[pred] = str(input_file)
                program += f'\n.input {pred}(IO=file, filename="{input_file}")\n'
                with open(input_file, "w", encoding="utf-8") as csvfile:
                    writer = csv.writer(csvfile, delimiter="\t")
                    for term in self.base_theory.ground_terms:
                        if term.predicate == pred:
                            writer.writerow(term.bindings.values())

            with tempfile.NamedTemporaryFile(suffix=".dl", mode="w") as fp:
                fp.write(program)
                fp.flush()
                res = subprocess.run([self.exec_name, fp.name], capture_output=True)
                if res.stderr:
                    msg = res.stderr.decode()
                    import re

                    if re.match(r".*Variable (\S+) only occurs once.*", msg):
                        logger.info(msg)
                    else:
                        logger.error(msg)

            for pred, filename in output_files.items():
                if not Path(filename).exists():
                    continue
                pd = pdmap[pred]
                rows = []
                with open(filename, "r") as csvfile:
                    reader = csv.reader(csvfile, delimiter="\t")
                    for row in reader:
                        rows.append(row)
                facts.extend(make_terms(rows, pd))

        model = Model(source_object=self, ground_terms=facts)
        yield model

    def check(self) -> Solution:
        return Solution(satisfiable=None)

    def dump(self) -> str:
        compiler = SouffleCompiler()
        return compiler.compile(self.base_theory)
