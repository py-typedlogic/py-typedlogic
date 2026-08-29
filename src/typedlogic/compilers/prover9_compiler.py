import logging
from dataclasses import dataclass
from typing import ClassVar, List, Optional, Union

from typedlogic import Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import Sentence, SentenceGroupType
from typedlogic.transformations import as_prover9, contains_negation_as_failure

logger = logging.getLogger(__name__)


def _skip_naf(sentence: Sentence, role: str) -> bool:
    """Return True (with a warning) if a sentence contains NAF and must be skipped."""
    if contains_negation_as_failure(sentence):
        logger.warning(
            f"Skipping {role} with negation-as-failure (unsupported by Prover9): {sentence}. "
            "The theory is weakened by this omission; consider "
            "typedlogic.transformations.clark_completion for a classical rendering."
        )
        return True
    return False


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
        for sg in theory.asserted_sentence_groups:
            for sentence in sg.sentences or []:
                if _skip_naf(sentence, "sentence"):
                    continue
                lines.append(f"    {as_prover9(sentence)}.")
        lines.append("end_of_list.")
        lines.append("")

        # Goals (conjecture)

        lines.append("formulas(goals).")
        for sg in theory.sentence_groups:
            if sg.group_type == SentenceGroupType.GOAL:
                for sentence in sg.sentences or []:
                    if _skip_naf(sentence, "goal"):
                        continue
                    lines.append(f"    {as_prover9(sentence)}.")
        if goals:
            for sentence in goals:
                if _skip_naf(sentence, "goal"):
                    continue
                lines.append(f"    {as_prover9(sentence)}.")
        lines.append("end_of_list.")
        return "\n".join(lines)
