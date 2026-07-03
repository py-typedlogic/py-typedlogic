import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, Iterator, Optional

from problog import get_evaluatable
from problog.errors import InconsistentEvidenceError
from problog.program import PrologString

from typedlogic.datamodel import NotInProfileError, Sentence, Term
from typedlogic.extensions.probabilistic import Evidence, ProbabilisticModel, Probability, That
from typedlogic.integrations.solvers.problog.problog_compiler import ProbLogCompiler
from typedlogic.profiles import (
    AllowsComparisonTerms,
    MixedProfile,
    MultipleModelSemantics,
    Probabilistic,
    Profile,
)
from typedlogic.solver import Solution, Solver
from typedlogic.transformations import as_prolog, counterexample_proof_sentences, to_horn_rules

logger = logging.getLogger(__name__)

DEFAULT_PROBLOG_ARGS = {
    "propagate_evidence": False,
}
COUNTEREXAMPLE_PREDICATE = "typedlogic_counterexample"


class UnsatisfiableEvidenceError(NotInProfileError):
    """
    Raised when ProbLog evidence is inconsistent with the program.
    """


class AmbiguousModelError(NotInProfileError):
    """
    Raised when a single-model API sees more than one probabilistic model.
    """


@dataclass
class ProbLogSolver(Solver):
    """
    A solver that uses problog.

    [problog](https://dtai.cs.kuleuven.be/problog/index.html) is a
    probabilistic logic programming language.

    Example:

        >>> from typedlogic.integrations.frameworks.pydantic import FactBaseModel
        >>> from typedlogic import SentenceGroup, PredicateDefinition, Forall, Variable
        >>> solver = ProbLogSolver()
        >>> solver.add_predicate_definition(PredicateDefinition(predicate="AncestorOf", arguments={'ancestor': 'str', 'descendant': 'str'}))
        >>> x = Variable('x')
        >>> y = Variable('y')
        >>> z = Variable('z')
        >>> tr_axiom = Forall([x, y, z], (Term('AncestorOf', x, y) & Term('AncestorOf', y, z)) >> Term('AncestorOf', x, z))
        >>> solver.add_sentence(tr_axiom)
        >>> solver.add_probabilistic_fact(Term('AncestorOf', 'p1', 'p1a'), 0.5)
        >>> solver.add_probabilistic_fact(Term('AncestorOf', 'p1a', 'p1aa'), 0.5)
        >>> model = solver.model()
        >>> print(model.term_probabilities[Term('AncestorOf', 'p1', 'p1aa')])
        0.25

    """

    exec_name: str = field(default="problog")
    profile: ClassVar[Profile] = MixedProfile(Probabilistic(), AllowsComparisonTerms(), MultipleModelSemantics())
    problog_args: Optional[Dict[str, Any]] = None

    def models(self, **kwargs) -> Iterator[ProbabilisticModel]:
        compiler = ProbLogCompiler()
        program = compiler.compile(self.base_theory)
        result = self._evaluate_program(program, **kwargs)
        m = ProbabilisticModel()
        for term, prob in result.items():
            plt_term = compiler.decompile_term(term)
            reified = Probability(prob, That(plt_term))
            reified_as_term = reified.to_model_object()
            if not isinstance(reified_as_term, Term):
                raise ValueError(f"Expected a term, got {reified_as_term}")
            m.ground_terms.append(reified_as_term)
            m.term_probabilities[plt_term] = prob
        yield m

    def _evaluate_program(self, program: str, **kwargs) -> Dict[Any, float]:
        """Evaluate a ProbLog program and return query probabilities."""
        for k, v in DEFAULT_PROBLOG_ARGS.items():
            if k not in kwargs:
                kwargs[k] = v
        if self.problog_args:
            for k, v in self.problog_args.items():
                if k not in kwargs:
                    kwargs[k] = v
        try:
            return get_evaluatable().create_from(PrologString(program), **kwargs).evaluate()
        except InconsistentEvidenceError as e:
            raise UnsatisfiableEvidenceError(
                "ProbLog evidence is inconsistent; no probabilistic model can satisfy the asserted evidence. "
                f"ProbLog reported: {e}"
            ) from e

    def model(self) -> ProbabilisticModel:
        models = list(self.models())
        if len(models) == 0:
            raise UnsatisfiableEvidenceError(
                "ProbLog produced no models; the evidence may be unsatisfiable for this probabilistic theory."
            )
        if len(models) > 1:
            raise AmbiguousModelError(
                "ProbLog produced multiple models; ProbLogSolver.model() expects exactly one model. "
                "Use ProbLogSolver.models() to inspect all models."
            )
        return models[0]

    def check(self) -> Solution:
        try:
            models = list(self.models())
        except UnsatisfiableEvidenceError:
            return Solution(satisfiable=False)
        sat = len(models) > 0
        return Solution(satisfiable=sat)

    def dump(self) -> str:
        compiler = ProbLogCompiler()
        return compiler.compile(self.base_theory)

    def prove(self, sentence: Sentence) -> Optional[bool]:
        """Prove Datalog-safe implications by checking counterexample probability."""
        compiler = ProbLogCompiler()
        try:
            counterexample_sentences = counterexample_proof_sentences(
                sentence,
                predicate=COUNTEREXAMPLE_PREDICATE,
            )
        except NotInProfileError:
            return None

        program = compiler.compile(self.base_theory, include_queries=False)
        proof_clauses: list[str] = []
        prolog_config = compiler.prolog_config()
        try:
            for proof_sentence in counterexample_sentences:
                for rule in to_horn_rules(proof_sentence, allow_disjunctions_in_head=False, allow_goal_clauses=True):
                    proof_clauses.append(as_prolog(rule, config=prolog_config))
            query = Term("query", Term(COUNTEREXAMPLE_PREDICATE))
            for rule in to_horn_rules(query, allow_disjunctions_in_head=False, allow_goal_clauses=True):
                proof_clauses.append(as_prolog(rule, config=prolog_config))
        except NotInProfileError as e:
            logger.info(f"Cannot prove sentence {sentence} with counterexample transform due to {e}")
            return None

        if proof_clauses:
            program = f"{program}\n" + "\n".join(proof_clauses)
        try:
            result = self._evaluate_program(program)
        except UnsatisfiableEvidenceError:
            return None

        counterexample = Term(COUNTEREXAMPLE_PREDICATE)
        for term, probability in result.items():
            if compiler.decompile_term(term) == counterexample:
                return probability == 0
        return None

    def add_probabilistic_fact(self, fact: Sentence, probability: float) -> None:
        pr_sent = Probability(probability, That(fact))
        self.add(pr_sent)

    def add_evidence(self, fact: Sentence, truth_value: bool) -> None:
        ev = Evidence(fact, truth_value)
        self.add(ev)
