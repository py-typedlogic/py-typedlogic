from dataclasses import dataclass
from typing import ClassVar, Dict, Optional, Union

from mypy.checkexpr import defaultdict

from typedlogic import Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import SentenceGroupType
from typedlogic.transformations import as_tptp


@dataclass
class TPTPCompiler(Compiler):

    default_suffix: ClassVar[str] = "tptp"

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        lines = [f"% Problem: {theory.name}"]
        grp_counts: Dict[str, int] = defaultdict(int)
        for sg in theory.sentence_groups:
            if sg.group_type == SentenceGroupType.GOAL:
                typ = "conjecture"
            else:
                typ = "axiom"
            for s in sg.sentences or []:
                t = as_tptp(s)
                grp_counts[typ] += 1
                lines.append(f"fof(axiom{grp_counts[typ]}, axiom, {t}).")
        return "\n".join(lines)
