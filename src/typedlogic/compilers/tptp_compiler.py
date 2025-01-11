from collections import defaultdict
from dataclasses import dataclass
from typing import ClassVar, Dict, Optional, Union

from typedlogic import Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import SentenceGroupType
from typedlogic.transformations import as_tptp


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
