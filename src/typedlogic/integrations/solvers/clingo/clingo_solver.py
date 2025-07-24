import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar, Iterator, Optional

import clingo
from clingo import Control, SymbolType

from typedlogic.datamodel import NotInProfileError, Sentence, Term
from typedlogic.profiles import (
    AllowsComparisonTerms,
    AnswerSetProgramming,
    MixedProfile,
    MultipleModelSemantics,
    Profile,
)
from typedlogic.solver import Model, Solution, Solver
from typedlogic.transformations import PrologConfig, as_prolog, to_horn_rules

logger = logging.getLogger(__name__)


@dataclass
class ClingoSolver(Solver):
    """
    A solver that uses clingo.

    [clingo](https://potassco.org/clingo/) is an [ASP](https://en.wikipedia.org/wiki/Answer_set_programming)
    system to ground and solve logic programs, it is
    part of the Potsdam Answer Set Solving Collection (Potassco; [potassco.org/](https://potassco.org/)).


        >>> from typedlogic.integrations.frameworks.pydantic import FactBaseModel
        >>> class AncestorOf(FactBaseModel):
        ...     ancestor: str
        ...     descendant: str
         >>> from typedlogic import SentenceGroup, PredicateDefinition
        >>> solver = ClingoSolver()
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

    This solver supports MultipleModelSemantics:

        >>> from typedlogic.profiles import MultipleModelSemantics
        >>> solver.profile.impl(MultipleModelSemantics)
        True

    This means that when you call `solver.models()`, you will get all models that satisfy the program.
    See the tutorial for examples of this.

    """

    exec_name: str = field(default="clingo")
    profile: ClassVar[Profile] = MixedProfile(AnswerSetProgramming(), AllowsComparisonTerms(), MultipleModelSemantics())
    ctl: Optional[Control] = None

    def _clauses(self) -> Iterator[str]:
        negation_symbol = "not" if self.assume_closed_world else "-"
        prolog_config = PrologConfig(
            disjunctive_datalog=True,
            double_quote_strings=True,
            negation_symbol=negation_symbol,
            negation_as_failure_symbol="not",
            allow_nesting=False,
            double_quote_floats=True,
        )
        for sentence in self.base_theory.sentences + self.base_theory.ground_terms:
            if not isinstance(sentence, Sentence):
                raise ValueError(f"Expected Sentence, got {sentence}")
            rules = []
            try:
                for rule in to_horn_rules(sentence, allow_disjunctions_in_head=True, allow_goal_clauses=True):
                    rules.append(rule)
                    # yield as_prolog(rule, config=prolog_config)
            except NotInProfileError as e:
                logger.info(f"Skipping sentence {sentence} due to {e}")
            for rule in rules:
                try:
                    yield as_prolog(rule, config=prolog_config)
                except NotInProfileError as e:
                    logger.info(f"Skipping sentence {sentence} due to {e}")

    def models(self) -> Iterator[Model]:
        ctl = Control(["0"])
        predicate_name_map = {pd.predicate.lower(): pd.predicate for pd in self.base_theory.predicate_definitions}
        for clause in self._clauses():
            ctl.add(clause)

        # Ground the program
        ctl.ground([("base", [])])
        # Solve the program
        with ctl.solve(yield_=True) as handle:
            for clingo_model in handle:
                facts = []
                for atom in clingo_model.symbols(shown=True):
                    p = predicate_name_map.get(atom.name, atom.name)

                    def _v(sym: clingo.Symbol) -> Any:
                        if sym.type == SymbolType.String:
                            return str(sym.string)
                        if sym.type == SymbolType.Number:
                            return sym.number
                        return sym

                    term = Term(p, *[_v(a) for a in atom.arguments])
                    if not atom.positive:
                        term = ~term
                    facts.append(term)

                model = Model(ground_terms=facts)
                yield model

    def check(self) -> Solution:
        models = list(self.models())
        sat = len(models) > 0
        return Solution(satisfiable=sat)

    def dump(self) -> str:
        s = ""
        for clause in self._clauses():
            s += f"{clause}\n"
        return s
