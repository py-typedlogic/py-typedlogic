import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, Iterator, Optional

from problog import get_evaluatable
from problog.program import PrologString

from typedlogic.datamodel import NotInProfileError, Sentence, Term
from typedlogic.extensions.probabilistic import Probability, That, ProbabilisticModel, Evidence
from typedlogic.integrations.solvers.problog.problog_compiler import ProbLogCompiler
from typedlogic.profiles import (
    AllowsComparisonTerms,
    MixedProfile,
    MultipleModelSemantics,
    Profile,
    Probabilistic,
)
from typedlogic.solver import Solution, Solver

logger = logging.getLogger(__name__)

DEFAULT_PROBLOG_ARGS = {
    'propagate_evidence': False,
}


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
        p = PrologString(program)
        ev = get_evaluatable()
        for k, v in DEFAULT_PROBLOG_ARGS.items():
            if k not in kwargs:
                kwargs[k] = v
        if self.problog_args:
            for k, v in self.problog_args.items():
                if k not in kwargs:
                    kwargs[k] = v
        result = ev.create_from(p, **kwargs).evaluate()
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

    def model(self) -> ProbabilisticModel:
        models = list(self.models())
        if len(models) == 0:
            raise NotInProfileError("No models found")
        if len(models) > 1:
            raise NotInProfileError("Multiple models found")
        return models[0]

    def check(self) -> Solution:
        models = list(self.models())
        sat = len(models) > 0
        return Solution(satisfiable=sat)

    def dump(self) -> str:
        compiler = ProbLogCompiler()
        return compiler.compile(self.base_theory)

    def add_probabilistic_fact(self, fact: Sentence, probability: float) -> None:
        pr_sent = Probability(probability, That(fact))
        self.add(pr_sent)

    def add_evidence(self, fact: Sentence, truth_value: bool) -> None:
        ev = Evidence(fact, truth_value)
        self.add(ev)
