from dataclasses import dataclass
from typing import ClassVar, List, Optional, Union

from typedlogic import Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import Sentence, SentenceGroupType
from typedlogic.transformations import as_prover9


@dataclass
class Prover9Compiler(Compiler):
    default_suffix: ClassVar[str] = "prover9"

    def compile(
        self,
        theory: Theory,
        syntax: Optional[Union[str, ModelSyntax]] = None,
        goals: Optional[List[Sentence]] = None,
        **kwargs,
    ) -> str:
        lines = [f"% Problem: {theory.name}"]
        # Assumptions (axioms)
        lines.append("formulas(assumptions).")
        for sg in theory.sentence_groups:
            if sg.group_type != SentenceGroupType.GOAL:
                for sentence in sg.sentences or []:
                    lines.append(f"    {as_prover9(sentence)}.")
        lines.append("end_of_list.")
        lines.append("")

        # Goals (conjecture)

        lines.append("formulas(goals).")
        for sg in theory.sentence_groups:
            if sg.group_type == SentenceGroupType.GOAL:
                for sentence in sg.sentences or []:
                    lines.append(f"    {as_prover9(sentence)}.")
        if goals:
            for sentence in goals:
                lines.append(f"    {as_prover9(sentence)}.")
        lines.append("end_of_list.")
        return "\n".join(lines)
