import logging
import math
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Union

import problog.logic as pl

from typedlogic import And, Forall, Implies, Or, Theory, Variable
from typedlogic.builtins import NAME_TO_INFIX_OP
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import Extension, NegationAsFailure, Not, NotInProfileError, Sentence, Term
from typedlogic.extensions.probabilistic import AnnotatedDisjunction, Evidence, Probability, That, validate_probability
from typedlogic.transformations import (
    PrologConfig,
    as_prolog,
    to_horn_rules,
    transform_sentence,
)

logger = logging.getLogger(__name__)

PROBABILITY_PREDICATE = "Probability"
THAT_PREDICATE = "That"
CONSTRAINT_VIOLATION_PREDICATE = "typedlogic_constraint_violation"
METADATA_PREDICATES = {Probability.__name__, That.__name__, Evidence.__name__, AnnotatedDisjunction.__name__}
NEGATED_COMPARISON_PREDICATES = {
    "eq": "ne",
    "ne": "eq",
    "lt": "ge",
    "le": "gt",
    "gt": "le",
    "ge": "lt",
}


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
        include_queries = kwargs.get("include_queries", True)
        strict = kwargs.get("strict", False)
        if not isinstance(strict, bool):
            raise ValueError("strict must be bool")
        prolog_config = self.prolog_config()
        if strict:
            prolog_config.allow_ungrounded_vars_in_head = False
        if not self._predicate_mappings:
            self._predicate_mappings = {}
        for pd in theory.predicate_definitions:
            prolog_pd = as_prolog(Term(pd.predicate), config=prolog_config)
            if "(" in prolog_pd:
                prolog_pd = prolog_pd[: prolog_pd.index("(")]
            self._predicate_mappings[prolog_pd] = pd.predicate
        clauses = []
        clauses.extend(self.false_predicate_declarations(theory, prolog_config))
        for sentence in theory.sentences + theory.ground_terms:
            clause = self._sentence_to_problog(sentence, prolog_config, strict=strict)
            if clause:
                clauses.append(clause)
        if include_queries:
            for pd in theory.predicate_definitions:
                if pd.predicate in METADATA_PREDICATES:
                    continue
                query_vars = [Variable(a) for a in pd.arguments.keys()]
                term = Term("query", Term(pd.predicate, *query_vars))
                clause = self._sentence_to_problog(term, prolog_config, strict=strict)
                clauses.append(clause)
        return "\n".join(clauses)

    @staticmethod
    def prolog_config() -> PrologConfig:
        """Return Prolog rendering configuration for ProbLog syntax."""
        return PrologConfig(
            disjunctive_datalog=True,
            double_quote_strings=True,
            operator_map={"eq": "=", "ne": r"\="},
            allow_nesting=False,
            allow_ungrounded_vars_in_head=True,
        )

    @staticmethod
    def false_predicate_declarations(theory: Theory, prolog_config: PrologConfig) -> List[str]:
        """Return false clauses for declared predicates that may otherwise be empty."""
        declarations = []
        seen: set[tuple[str, int]] = set()
        for predicate_definition in theory.predicate_definitions:
            if predicate_definition.predicate in METADATA_PREDICATES:
                continue
            predicate = as_prolog(Term(predicate_definition.predicate), config=prolog_config)
            if "(" in predicate:
                predicate = predicate[: predicate.index("(")]
            arity = len(predicate_definition.arguments)
            key = (predicate, arity)
            if key in seen:
                continue
            seen.add(key)
            if arity == 0:
                declarations.append(f"{predicate} :- fail.")
                continue
            args = ", ".join("_" for _ in range(arity))
            declarations.append(f"{predicate}({args}) :- fail.")
        return declarations

    def _sentence_to_problog(self, sentence: Sentence, prolog_config: PrologConfig, *, strict: bool = False) -> str:
        sentence = transform_sentence(sentence, lambda s: s.to_model_object() if isinstance(s, Extension) else s)
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
                            Term(Probability.__name__, pr, That(inner_expr).to_model_object()),
                            prolog_config,
                            strict=strict,
                        )
            return self._sentence_to_problog(sentence.sentence, prolog_config, strict=strict)

        if isinstance(sentence, Term) and sentence.predicate == AnnotatedDisjunction.__name__:
            return self._annotated_disjunction_to_problog(sentence, prolog_config)

        def _to_rules(s: Sentence) -> List[Sentence]:
            if strict:
                self._validate_horn_sentence(s)
                if isinstance(s, Term):
                    s = Implies(And(), s)
                rewritten = self._comparison_head_to_constraint(s, strict=True)
                if rewritten is None:
                    raise NotInProfileError(f"Cannot compile sentence: {s}")
                return [rewritten]
            rules = []
            try:
                for rule in to_horn_rules(s, allow_disjunctions_in_head=False, allow_goal_clauses=True):
                    rewritten_rule = self._comparison_head_to_constraint(rule)
                    if rewritten_rule is None:
                        continue
                    rules.append(rewritten_rule)
            except NotInProfileError as e:
                logger.info(f"Skipping sentence {s} due to {e}")
            return rules

        pr_sent = self._sentence_probability(sentence)
        if pr_sent:
            pr, inner = pr_sent
            inner = transform_sentence(inner, lambda s: s.to_model_object() if isinstance(s, Extension) else s)
            while isinstance(inner, Forall):
                inner = inner.sentence
            # A probability annotation denotes one random choice. Distributing it
            # over transformed rules would introduce independent random choices.
            self._validate_probabilistic_sentence(inner, strict=strict)
            inner_rules = _to_rules(inner)
            strs = []
            for r in inner_rules:
                rendered = self._rule_to_problog(r, prolog_config, strict=True)
                if rendered:
                    strs.append(f"{pr}::{rendered}")
            return "\n".join(strs)
        elif isinstance(sentence, Term) and sentence.predicate == Evidence.__name__:
            # special treatment for evidence sentences
            if len(sentence.values) != 2:
                raise ValueError(f"Invalid evidence sentence: {sentence}")
            inner = sentence.values[0]
            if isinstance(inner, Extension):
                inner = inner.to_model_object()
            self._validate_atom(inner)
            if self._contains_variable(inner):
                raise ValueError(f"Evidence must be ground: {inner}")
            inner_prolog = as_prolog(inner, config=prolog_config, strict=True)
            if not inner_prolog:
                raise ValueError(f"Invalid evidence inner sentence: {inner}")
            truth_value = sentence.values[1]
            if not isinstance(truth_value, bool):
                raise ValueError(f"Evidence truth_value must be bool, got {truth_value!r}")
            return f"evidence({inner_prolog}, {'true' if truth_value else 'false'})."
        else:
            rules = _to_rules(sentence)
            rendered_rules = [self._rule_to_problog(r, prolog_config, strict=strict) for r in rules]
            if strict and (not rendered_rules or any(not rendered for rendered in rendered_rules)):
                raise NotInProfileError(f"No clause emitted for sentence: {sentence}")
            return "\n".join(rendered for rendered in rendered_rules if rendered)

    @staticmethod
    def _contains_variable(value: Any) -> bool:
        """Find variables and None (rendered as _) inside observation arguments."""
        if value is None or isinstance(value, Variable):
            return True
        if isinstance(value, Term):
            return any(ProbLogCompiler._contains_variable(v) for v in value.values)
        if isinstance(value, (list, tuple)):
            return any(ProbLogCompiler._contains_variable(v) for v in value)
        return False

    @staticmethod
    def _validate_atom(sentence: Sentence) -> None:
        """Require an ordinary positive atom, not a connective or metadata wrapper."""
        if not isinstance(sentence, Term) or sentence.predicate in METADATA_PREDICATES | set(NAME_TO_INFIX_OP):
            raise NotInProfileError(f"Expected a positive atomic predicate, got {sentence}")

    @classmethod
    def _validate_body(cls, body: Sentence, *, allow_classical_negation: bool = False) -> None:
        """Accept conjunctions of atoms, comparisons, and explicit negation as failure."""
        if isinstance(body, Extension):
            body = body.to_model_object()
        if isinstance(body, And):
            for part in body.operands:
                cls._validate_body(part, allow_classical_negation=allow_classical_negation)
        elif isinstance(body, NegationAsFailure) or (allow_classical_negation and isinstance(body, Not)):
            cls._validate_atom(body.negated)
        elif isinstance(body, Term) and body.predicate not in METADATA_PREDICATES:
            return
        else:
            raise NotInProfileError(
                f"Unsupported ProbLog body: {body}; use explicit NegationAsFailure for closed-world negation"
            )

    @classmethod
    def _validate_horn_sentence(cls, sentence: Sentence) -> None:
        """Validate the fail-closed subset without general FOL-to-Horn rewriting."""
        if isinstance(sentence, Term):
            cls._validate_atom(sentence)
            if sentence.predicate != "query":
                cls._validate_head_grounding(And(), sentence)
            return
        if not isinstance(sentence, Implies):
            raise NotInProfileError(f"Strict ProbLog compilation requires an atom or Horn rule, got {sentence}")
        cls._validate_body(sentence.antecedent)
        head = sentence.consequent
        if isinstance(head, Or) and not head.operands:
            return  # Explicit integrity constraint.
        if isinstance(head, Term) and head.predicate in NEGATED_COMPARISON_PREDICATES:
            return  # Comparison head becomes an explicit integrity constraint.
        cls._validate_atom(head)
        cls._validate_head_grounding(sentence.antecedent, head)

    @classmethod
    def _validate_no_anonymous_head_arguments(cls, value: Any) -> None:
        """Reject arguments that render as fresh, unbound anonymous variables."""
        if value is None or (isinstance(value, Variable) and value.name == "_"):
            raise NotInProfileError("Anonymous arguments are not allowed in ProbLog heads")
        if isinstance(value, Term):
            for argument in value.values:
                cls._validate_no_anonymous_head_arguments(argument)
        elif isinstance(value, (list, tuple)):
            for argument in value:
                cls._validate_no_anonymous_head_arguments(argument)

    @classmethod
    def _validate_head_grounding(cls, body: Sentence, head: Term) -> None:
        """Include nested head variables in the strict range-restriction check."""
        cls._validate_no_anonymous_head_arguments(head)

        def variables(value: Any) -> set[str]:
            if isinstance(value, Variable):
                return {value.name}
            if isinstance(value, Term):
                return set().union(*(variables(v) for v in value.values))
            return set()

        def bound_variables(value: Sentence) -> set[str]:
            if isinstance(value, And):
                return set().union(*(bound_variables(v) for v in value.operands))
            if isinstance(value, Term) and value.predicate not in NAME_TO_INFIX_OP:
                return variables(value)
            return set()

        unbound = variables(head) - bound_variables(body)
        if unbound:
            raise NotInProfileError(f"Head variables need a positive body atom: {sorted(unbound)} in {head}")

    @classmethod
    def _validate_probabilistic_sentence(cls, sentence: Sentence, *, strict: bool) -> None:
        """Permit exactly one atomic fact or atomic-headed probabilistic rule."""
        if isinstance(sentence, Forall):
            cls._validate_probabilistic_sentence(sentence.sentence, strict=strict)
            return
        if isinstance(sentence, Extension):
            sentence = sentence.to_model_object()
        if isinstance(sentence, Implies):
            cls._validate_atom(sentence.consequent)
            cls._validate_body(sentence.antecedent, allow_classical_negation=not strict)
        else:
            cls._validate_atom(sentence)

    @classmethod
    def _annotated_disjunction_to_problog(cls, sentence: Term, config: PrologConfig) -> str:
        """Render one categorical choice directly, never through Horn conversion."""
        if len(sentence.values) != 2:
            raise ValueError(f"Invalid annotated disjunction: {sentence}")
        alternatives, body = sentence.values
        if not isinstance(alternatives, (list, tuple)) or not alternatives:
            raise ValueError("AnnotatedDisjunction needs at least one weighted alternative")
        if body is None:
            body = And()
        body = transform_sentence(body, lambda s: s.to_model_object() if isinstance(s, Extension) else s)
        cls._validate_body(body)
        probabilities = []
        rendered_heads = []
        rendered_atoms: set[str] = set()
        atoms = []
        for alternative in alternatives:
            if not isinstance(alternative, (list, tuple)) or len(alternative) != 2:
                raise ValueError(f"Expected (probability, atom), got {alternative!r}")
            probability, atom = alternative
            validate_probability(probability)
            if isinstance(atom, Extension):
                atom = atom.to_model_object()
            cls._validate_atom(atom)
            cls._validate_no_anonymous_head_arguments(atom)
            if atom in atoms:
                raise ValueError(f"Duplicate annotated-disjunction head: {atom}")
            atoms.append(atom)
            if not config.allow_ungrounded_vars_in_head:
                cls._validate_head_grounding(body, atom)
            # Rendering the corresponding rule validates head-variable grounding.
            as_prolog(Implies(body, atom), config=config, strict=True)
            rendered_atom = as_prolog(atom, config=config, strict=True)
            if rendered_atom in rendered_atoms:
                raise ValueError(f"Annotated-disjunction heads collide after rendering: {rendered_atom}")
            rendered_atoms.add(rendered_atom)
            probabilities.append(probability)
            rendered_heads.append(f"{probability}::{rendered_atom}")
        if math.fsum(probabilities) > 1:
            raise ValueError("Annotated-disjunction probabilities must sum to at most 1")
        heads = "; ".join(rendered_heads)
        if isinstance(body, And) and not body.operands:
            return f"{heads}."
        return f"{heads} :- {as_prolog(body, config=config, depth=1, strict=True)}."

    def _sentence_probability(self, sentence: Sentence) -> Optional[Tuple[Union[float, int], Sentence]]:
        if isinstance(sentence, Forall):
            return self._sentence_probability(sentence.sentence)
        if isinstance(sentence, Term):
            if sentence.predicate == PROBABILITY_PREDICATE:
                if len(sentence.values) != 2:
                    raise ValueError(f"Invalid probability sentence: {sentence}")
                pr = sentence.values[0]
                inner = sentence.values[1]
                validate_probability(pr)
                if not isinstance(inner, Sentence):
                    raise ValueError(f"Invalid inner sentence: {inner}")
                if isinstance(inner, Extension):
                    inner = inner.to_model_object()
                if not isinstance(inner, Term):
                    raise ValueError(f"Invalid inner term: {inner}")
                if inner.predicate != THAT_PREDICATE:
                    raise ValueError(f"Invalid inner predicate: {inner.predicate}")
                if len(inner.values) != 1:
                    raise ValueError(f"That must wrap exactly one sentence: {inner}")
                inner_ref = inner.values[0]
                if not isinstance(inner_ref, Sentence):
                    raise ValueError(f"Invalid inner reference: {inner_ref}")
                return pr, inner_ref
        return None

    @staticmethod
    def _comparison_head_to_constraint(rule: Sentence, *, strict: bool = False) -> Optional[Sentence]:
        """Convert implication heads like ``X != Y`` into ProbLog constraints."""
        if not isinstance(rule, Implies):
            return rule
        head = rule.consequent
        if not isinstance(head, Term) or head.predicate not in NAME_TO_INFIX_OP:
            return rule
        negated_predicate = NEGATED_COMPARISON_PREDICATES.get(head.predicate)
        if not negated_predicate:
            if strict:
                raise NotInProfileError(f"Unsupported built-in predicate in head: {rule}")
            logger.info(f"Skipping rule with built-in predicate in head: {rule}")
            return None
        negated_comparison = Term(negated_predicate, *head.values)
        return Implies(And(rule.antecedent, negated_comparison), Or())

    @staticmethod
    def _rule_to_problog(rule: Sentence, prolog_config: PrologConfig, *, strict: bool = False) -> str:
        """Render one rule, encoding goal clauses as ProbLog evidence."""
        if isinstance(rule, Implies) and isinstance(rule.consequent, Or) and not rule.consequent.operands:
            violation = Implies(rule.antecedent, Term(CONSTRAINT_VIOLATION_PREDICATE))
            return (
                f"{as_prolog(violation, config=prolog_config, strict=strict)}\n"
                f"evidence({CONSTRAINT_VIOLATION_PREDICATE}, false)."
            )
        return as_prolog(rule, config=prolog_config, strict=strict)

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
