import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import ClassVar, Dict, Optional, Union

from typedlogic import Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import Sentence, SentenceGroupType
from typedlogic.transformations import as_tptp, contains_negation_as_failure

logger = logging.getLogger(__name__)


def _skip_naf(sentence: Sentence, role: str) -> bool:
    """Return True (with a warning) if a sentence contains NAF and must be skipped."""
    if contains_negation_as_failure(sentence):
        logger.warning(
            f"Skipping {role} with negation-as-failure (unsupported in TPTP FOF): {sentence}. "
            "The theory is weakened by this omission; consider "
            "typedlogic.transformations.clark_completion for a classical rendering."
        )
        return True
    return False


@dataclass
class TPTPCompiler(Compiler):
    default_suffix: ClassVar[str] = "tptp"

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        """
        A Compiler that generates TPTP code from a Theory object.

        Example:

            >>> from typedlogic import *
            >>> theory = Theory()
            >>> x = Variable("x")
            >>> theory.predicate_definitions = [PredicateDefinition("P", {"x": "str"}),
            ...              PredicateDefinition("Q", {"x": "str"})]
            >>> s = Implies(Term("P", x), Term("Q", x))
            >>> theory.add(sentence=s)
            >>> compiler = TPTPCompiler()
            >>> print(compiler.compile(theory))
            % Problem: None
            fof(axiom1, axiom, (p(X) => q(X))).

        :param theory:
        :param syntax:
        :param kwargs:
        :return:
        """
        lines = [f"% Problem: {theory.name}"]
        grp_counts: Dict[str, int] = defaultdict(int)
        for sg in theory.asserted_sentence_groups:
            for s in sg.sentences or []:
                if _skip_naf(s, "sentence"):
                    continue
                t = as_tptp(s)
                grp_counts["axiom"] += 1
                lines.append(f"fof(axiom{grp_counts['axiom']}, axiom, {t}).")
        for sg in theory.sentence_groups:
            if sg.group_type == SentenceGroupType.GOAL:
                for s in sg.sentences or []:
                    if _skip_naf(s, "conjecture"):
                        continue
                    t = as_tptp(s)
                    grp_counts["conjecture"] += 1
                    lines.append(f"fof(conjecture{grp_counts['conjecture']}, conjecture, {t}).")
        return "\n".join(lines)
