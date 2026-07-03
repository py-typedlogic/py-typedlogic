"""Clingo-backed solver integration."""

import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar, Iterator, Optional

import clingo
from clingo import Control, SymbolType

from typedlogic.datamodel import Exists, NotInProfileError, Sentence, Term, Variable
from typedlogic.profiles import (
    AllowsComparisonTerms,
    AnswerSetProgramming,
    MixedProfile,
    MultipleModelSemantics,
    Profile,
)
from typedlogic.solver import Model, Solution, Solver
from typedlogic.transformations import PrologConfig, as_prolog, counterexample_proof_sentences, to_horn_rules

logger = logging.getLogger(__name__)
COUNTEREXAMPLE_PREDICATE = "typedlogic_counterexample"


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
        >>> solver.add_predicate_definition(
        ...     PredicateDefinition(predicate="AncestorOf", arguments={'ancestor': str, 'descendant': str})
        ... )
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

    def _prolog_config(self) -> PrologConfig:
        """Return Prolog rendering configuration for clingo syntax."""
        negation_symbol = "not" if self.assume_closed_world else "-"
        return PrologConfig(
            disjunctive_datalog=True,
            double_quote_strings=True,
            negation_symbol=negation_symbol,
            negation_as_failure_symbol="not",
            allow_nesting=False,
            double_quote_floats=True,
        )

    def _clauses(self) -> Iterator[str]:
        yield from self._predicate_declarations()
        prolog_config = self._prolog_config()
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

    def _predicate_declarations(self) -> Iterator[str]:
        """Yield clingo declarations for predicate names declared by the theory."""
        seen: set[tuple[str, int]] = set()
        for predicate_definition in self.base_theory.predicate_definitions:
            predicate = predicate_definition.predicate.lower()
            arity = len(predicate_definition.arguments)
            key = (predicate, arity)
            if key in seen:
                continue
            seen.add(key)
            yield f"#defined {predicate}/{arity}."

    def _add_clauses(self, ctl: Control) -> None:
        """Add the generated clingo program to a control object."""
        for clause in self._clauses():
            ctl.add(clause)

    def models(self) -> Iterator[Model]:
        """Yield models returned by clingo for the current theory."""
        ctl = Control(["0"])
        predicate_name_map = {pd.predicate.lower(): pd.predicate for pd in self.base_theory.predicate_definitions}
        self._add_clauses(ctl)

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

    def prove(self, sentence: Sentence) -> Optional[bool]:
        """Prove terms from the current model and Datalog-safe implications by counterexample search."""
        if isinstance(sentence, Exists) and isinstance(sentence.sentence, Term):
            return self._model_entails_term(sentence.sentence)
        if isinstance(sentence, Term):
            return self._model_entails_term(sentence)

        try:
            counterexample_sentences = counterexample_proof_sentences(
                sentence,
                predicate=COUNTEREXAMPLE_PREDICATE,
            )
        except NotInProfileError:
            return None

        ctl = Control(["0"])
        self._add_clauses(ctl)
        prolog_config = self._prolog_config()
        try:
            for proof_sentence in counterexample_sentences:
                for rule in to_horn_rules(proof_sentence, allow_disjunctions_in_head=True, allow_goal_clauses=True):
                    ctl.add(as_prolog(rule, config=prolog_config))
        except NotInProfileError as e:
            logger.info(f"Cannot prove sentence {sentence} with counterexample transform due to {e}")
            return None

        ctl.ground([("base", [])])
        saw_model = False
        with ctl.solve(yield_=True) as handle:
            for clingo_model in handle:
                saw_model = True
                if any(atom.name == COUNTEREXAMPLE_PREDICATE for atom in clingo_model.symbols(atoms=True)):
                    return False
        if not saw_model:
            return None
        return True

    def _model_entails_term(self, sentence: Term) -> bool:
        """Return whether the materialized model contains a term matching the query."""
        try:
            model = self.model()
        except StopIteration:
            return False
        return self._model_contains_term(model, sentence)

    @staticmethod
    def _model_contains_term(model: Model, sentence: Term) -> bool:
        """Return whether a materialized model contains a term."""
        sentence_values = sentence.values
        has_vars = any(isinstance(value, Variable) for value in sentence_values)
        for term in model.iter_retrieve(sentence.predicate):
            if len(term.values) != len(sentence_values):
                continue
            if term == sentence:
                return True
            if has_vars and ClingoSolver._term_matches_with_variables(term, sentence_values):
                return True
        return False

    @staticmethod
    def _term_matches_with_variables(term: Term, sentence_values: tuple[Any, ...]) -> bool:
        """Return whether a ground term matches expected values containing variables."""
        bindings: dict[str, Any] = {}
        for expected, actual in zip(sentence_values, term.values, strict=True):
            if not isinstance(expected, Variable):
                if expected != actual:
                    return False
                continue
            if expected.name in bindings:
                if bindings[expected.name] != actual:
                    return False
                continue
            bindings[expected.name] = actual
        return True

    def check(self) -> Solution:
        """Return satisfiability for the current clingo program."""
        models = list(self.models())
        sat = len(models) > 0
        return Solution(satisfiable=sat)

    def dump(self) -> str:
        """Return the generated clingo program."""
        s = ""
        for clause in self._clauses():
            s += f"{clause}\n"
        return s
