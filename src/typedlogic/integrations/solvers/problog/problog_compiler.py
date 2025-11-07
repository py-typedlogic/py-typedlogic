import logging
from typing import ClassVar, Optional, Union, List, Tuple, Dict, Any

import problog.logic as pl

from typedlogic import Theory, Forall, Variable
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import NotInProfileError, Sentence, Term, Extension
from typedlogic.extensions.probabilistic import Evidence, Probability, That
from typedlogic.transformations import (
    PrologConfig,
    as_prolog,
    to_horn_rules,
)

logger = logging.getLogger(__name__)

PROBABILITY_PREDICATE = "Probability"
THAT_PREDICATE = "That"


class ProbLogCompiler(Compiler):
    default_suffix: ClassVar[str] = "problog"
    _predicate_mappings: Optional[Dict[str, str]] = None

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        """
        Compile a Theory object into ProbLog code.

        Example:

            >>> from typedlogic import SentenceGroup, PredicateDefinition, Forall, Variable, Theory
            >>> x = Variable('x')
            >>> y = Variable('y')
            >>> z = Variable('z')
            >>> theory = Theory(
            ...     predicate_definitions=[PredicateDefinition(predicate="AncestorOf", arguments={'ancestor': 'str', 'descendant': 'str'})],
            ...     ground_terms=[Term('AncestorOf', 'p1', 'p1a'), Term('AncestorOf', 'p1a', 'p1aa')],
            ... )
            >>> theory.add(Forall([x, y, z], (Term('AncestorOf', x, y) & Term('AncestorOf', y, z)) >> Term('AncestorOf', x, z)))
            >>> theory.add(Probability(0.5, That(Term('AncestorOf', 'p1', 'p1a'))))
            >>> theory.add(Probability(0.5, That(Term('AncestorOf', 'p1a', 'p1aa'))))
            >>> compiler = ProbLogCompiler()
            >>> print(compiler.compile(theory))
            ancestorof(X, Z) :- ancestorof(X, Y), ancestorof(Y, Z).
            0.5::ancestorof("p1", "p1a").
            0.5::ancestorof("p1a", "p1aa").
            ancestorof("p1", "p1a").
            ancestorof("p1a", "p1aa").
            query(ancestorof(Ancestor, Descendant)).

        Note like most compilers, you don't need to use this directly. It is more common to use ProblogSolver, which takes care of
        compiling the problog program, feeding it to problog, and parsing results.

        :param theory:
        :param syntax:
        :param kwargs:
        :return:
        """
        prolog_config = PrologConfig(disjunctive_datalog=True, double_quote_strings=True, allow_nesting=False, allow_ungrounded_vars_in_head=True)
        if not self._predicate_mappings:
            self._predicate_mappings = {}
        for pd in theory.predicate_definitions:
            prolog_pd = as_prolog(Term(pd.predicate), config=prolog_config)
            if "(" in prolog_pd:
                prolog_pd = prolog_pd[: prolog_pd.index("(")]
            self._predicate_mappings[prolog_pd] = pd.predicate
        clauses = []
        for sentence in theory.sentences + theory.ground_terms:
            clause = self._sentence_to_problog(sentence, prolog_config)
            if clause:
                clauses.append(clause)
        for pd in theory.predicate_definitions:
            if pd.predicate in [Probability.__name__, That.__name__, Evidence.__name__]:
                continue
            query_vars = [Variable(a) for a in pd.arguments.keys()]
            term = Term("query", Term(pd.predicate, *query_vars))
            clause = self._sentence_to_problog(term, prolog_config)
            clauses.append(clause)
        return "\n".join(clauses)

    def _sentence_to_problog(self, sentence: Sentence, prolog_config: PrologConfig) -> str:
        if isinstance(sentence, Forall):
            if isinstance(sentence.sentence, Term):
                if sentence.sentence.predicate == "eq":
                    vals = sentence.sentence.values
                    if len(vals) != 2:
                        raise ValueError(f"Invalid equality sentence: {sentence}")
                    first = vals[0]
                    if isinstance(first, Term) and first.predicate == "probability":
                        inner_expr = first.values[0]
                        pr = vals[1]
                        return self._sentence_to_problog(
                            Term(Probability.__name__, pr, That(inner_expr).to_model_object()), prolog_config
                        )

        def _to_rules(s: Sentence) -> List[Sentence]:
            rules = []
            try:
                for rule in to_horn_rules(s, allow_disjunctions_in_head=False, allow_goal_clauses=True):
                    rules.append(rule)
            except NotInProfileError as e:
                logger.info(f"Skipping sentence {s} due to {e}")
            return rules

        pr_sent = self._sentence_probability(sentence)
        if pr_sent:
            pr, inner = pr_sent
            inner_rules = _to_rules(inner)
            strs = []
            for r in inner_rules:
                strs.append(f"{pr}::{as_prolog(r, config=prolog_config)}")
            return "\n".join(strs)
        elif isinstance(sentence, Term) and sentence.predicate == Evidence.__name__:
            # special treatment for evidence sentences
            if len(sentence.values) != 2:
                raise ValueError(f"Invalid evidence sentence: {sentence}")
            inner = sentence.values[0]
            inner_prolog = as_prolog(inner, config=prolog_config, strict=True)
            if not inner_prolog:
                raise ValueError(f"Invalid evidence inner sentence: {inner}")
            truth_value = sentence.values[1]
            return f"evidence({inner_prolog}, {'true' if truth_value else 'false'})."
        else:
            rules = _to_rules(sentence)
            return "\n".join([as_prolog(r, config=prolog_config, strict=False) for r in rules])

    def _sentence_probability(self, sentence: Sentence) -> Optional[Tuple[Union[float, int], Sentence]]:
        if isinstance(sentence, Forall):
            return self._sentence_probability(sentence.sentence)
        if isinstance(sentence, Term):
            if sentence.predicate == PROBABILITY_PREDICATE:
                if len(sentence.values) != 2:
                    raise ValueError(f"Invalid probability sentence: {sentence}")
                pr = sentence.values[0]
                inner = sentence.values[1]
                if not isinstance(pr, (float, int)):
                    raise ValueError(f"Invalid probability: {pr}")
                if not isinstance(inner, Sentence):
                    raise ValueError(f"Invalid inner sentence: {inner}")
                if isinstance(inner, Extension):
                    inner = inner.to_model_object()
                if not isinstance(inner, Term):
                    raise ValueError(f"Invalid inner term: {inner}")
                if inner.predicate != THAT_PREDICATE:
                    raise ValueError(f"Invalid inner predicate: {inner.predicate}")
                inner_ref = inner.values[0]
                if not isinstance(inner_ref, Sentence):
                    raise ValueError(f"Invalid inner reference: {inner_ref}")
                return pr, inner_ref
        return None

    def decompile_term(self, compiled_term: Any) -> Term:
        if isinstance(compiled_term, pl.Term):
            pms = self._predicate_mappings or {}
            functor = pms.get(compiled_term.functor, compiled_term.functor)

            def _decompile_const(a: Any) -> Any:
                if isinstance(a, pl.Constant):
                    v = a.value
                    if isinstance(v, str):
                        if v.startswith('"') and v.endswith('"'):
                            v = v[1:-1]
                    return v
                return str(a)

            vals = [_decompile_const(a) for a in compiled_term.args]
            plt_term = Term(functor, *vals)
            return plt_term
        raise ValueError(f"Expected a Prolog term, got {compiled_term}")
