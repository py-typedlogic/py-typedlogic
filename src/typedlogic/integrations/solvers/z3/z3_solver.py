from copy import copy
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Dict, Iterator, List, Mapping, Optional, Set, Type, Union

import z3
from z3 import SortRef

import typedlogic as tlog
import typedlogic.pybridge
from typedlogic import FactMixin, Variable
from typedlogic.builtins import NUMERIC_BUILTINS
from typedlogic.datamodel import (
    CardinalityConstraint,
    DefinedType,
    NotInProfileError,
    PredicateDefinition,
    Sentence,
    Term,
)
from typedlogic.parsers.pyparser.python_ast_utils import logger
from typedlogic.profiles import (
    AllowsComparisonTerms,
    MixedProfile,
    MultipleModelSemantics,
    OpenWorld,
    Profile,
    SortedLogic,
    Unrestricted,
)
from typedlogic.pybridge import fact_arg_map, fact_predicate
from typedlogic.solver import Model, Solution, Solver
from typedlogic.transformations import contains_negation_as_failure

SORT_MAP: Mapping[str, Type[SortRef]] = {
    "str": z3.StringSort,
    "int": z3.IntSort,
    "bool": z3.BoolSort,
    "float": z3.RealSort,
}


# Return the first "M" models of formula list of formulas F
def get_models(s: z3.Solver, M: int) -> List[z3.Model]:
    # https://stackoverflow.com/questions/11867611/z3py-checking-all-solutions-for-equation
    # https://github.com/Z3Prover/z3/issues/5765
    result: List[z3.Model] = []
    s.push()
    while len(result) < M and s.check() == z3.sat:
        m = s.model()
        result.append(m)
        # Create a new constraint the blocks the current model
        block = []
        for d in m:
            # d is a declaration
            if d.arity() > 0:
                logger.warning(f"ignoring uninterpreted function {d}")
                continue
                # raise z3.Z3Exception(f"uninterpreted functions are not supported; {d}")
            # create a constant from declaration
            c = d()
            if z3.is_array(c) or c.sort().kind() == z3.Z3_UNINTERPRETED_SORT:
                raise z3.Z3Exception("arrays and uninterpreted sorts are not supported")
            block.append(c != m[d])
        s.add(z3.Or(block))
    s.pop()
    return result


@dataclass
class Z3Solver(Solver):
    """
    A solver that uses Z3 for type checking and constraint validation.

    Z3 excels at verifying type constraints, detecting inconsistencies in typed systems,
    and proving properties through logical inference. While useful for entailment, Z3's
    real strength is in checking that constraints and type invariants are satisfied.

    Example: Detecting type violations in a categorization system:

        >>> from typedlogic import Term, Variable, Forall, Not
        >>> # Define predicates for a categorization system
        >>> solver = Z3Solver()
        >>> solver.add_predicate_definition(PredicateDefinition(
        ...     predicate="IsPositive", arguments={'x': "int"}
        ... ))
        >>> solver.add_predicate_definition(PredicateDefinition(
        ...     predicate="IsNegative", arguments={'x': "int"}
        ... ))
        >>> # Type constraint: nothing can be both positive and negative
        >>> x = Variable("x", "int")
        >>> mutual_exclusion = Forall([x], Not(
        ...     Term("IsPositive", {"x": x}) & Term("IsNegative", {"x": x})
        ... ))
        >>> solver.add_sentence(mutual_exclusion)
        >>> # Valid: separate classifications
        >>> solver.add_fact(Term("IsPositive", {"x": 5}))
        >>> solver.add_fact(Term("IsNegative", {"x": -3}))
        >>> soln = solver.check()
        >>> soln.satisfiable
        True
        >>> # Invalid: contradictory classification of same value
        >>> solver2 = Z3Solver()
        >>> solver2.add_predicate_definition(PredicateDefinition(
        ...     predicate="IsPositive", arguments={'x': "int"}
        ... ))
        >>> solver2.add_predicate_definition(PredicateDefinition(
        ...     predicate="IsNegative", arguments={'x': "int"}
        ... ))
        >>> solver2.add_sentence(mutual_exclusion)
        >>> solver2.add_fact(Term("IsPositive", {"x": 7}))
        >>> solver2.add_fact(Term("IsNegative", {"x": 7}))  # Contradiction!
        >>> soln2 = solver2.check()
        >>> soln2.satisfiable
        False

    Z3 can also verify class hierarchies, check inheritance constraints, and prove
    complex logical entailments from axiom systems.

    """

    _wrapped_solver: Optional[z3.Solver] = None
    profile: ClassVar[Profile] = MixedProfile(
        Unrestricted(), SortedLogic(), MultipleModelSemantics(), OpenWorld(), AllowsComparisonTerms()
    )
    max_models: int = field(default=5)

    # TODO: rename this
    predicate_map: Optional[Dict[str, z3.FuncDecl]] = None

    def __post_init__(self):
        if self._wrapped_solver is None:
            self._wrapped_solver = z3.Solver()

    @property
    def wrapped_solver(self) -> z3.Solver:
        if self._wrapped_solver is None:
            self._wrapped_solver = z3.Solver()
        return self._wrapped_solver

    def check(self) -> Solution:
        result = self.wrapped_solver.check()
        return Solution(satisfiable=result == z3.sat)

    def models(self) -> Iterator[Model]:
        results = get_models(self.wrapped_solver, self.max_models)
        if not results:
            raise ValueError("Not satisfiable")
        for wmodel in results:
            rmodel = Model(
                description=str(wmodel),
                source_object=wmodel,
                ground_terms=[],
            )
            yield rmodel
        return

    def prove(self, sentence: Sentence) -> Optional[bool]:
        if contains_negation_as_failure(sentence):
            logger.warning(
                f"Z3 cannot prove a goal containing negation-as-failure; returning unknown for: {sentence}. "
                "Consider typedlogic.transformations.clark_completion to obtain a classical rendering."
            )
            return None
        s = self.wrapped_solver
        s.push()
        s.add(z3.Not(self.translate(sentence)))
        result = s.check()
        s.pop()
        return result == z3.unsat

    def _unroll_type(self, typ: DefinedType) -> Set[str]:
        """
        Unroll a defined type into its components

        :param typ:
        :return:
        """
        if isinstance(typ, str):
            if typ in self.type_definitions:
                return self._unroll_type(self.base_theory.type_definitions[typ])
            return {typ}
        if isinstance(typ, list):
            ts: List[str] = []
            for t in typ:
                ts.extend(self._unroll_type(t))
            return set(ts)
        raise ValueError(f"Unknown type {typ}")

    def _sort(self, typ: Optional[str] = None) -> Union[Callable, Type[z3.SortRef]]:
        # TODO: change this to return instantiated sort, not the sort class
        if not typ:
            return z3.StringSort
        typs = self._unroll_type(typ)
        repl_map = {
            "Decimal": "float",
        }
        typs = {repl_map.get(t, t) for t in typs}
        if "float" in typs and "int" in typs:
            typs = typs.difference({"int"})
        if len(typs) > 1:
            # unions not directly supported
            # TODO: add constraints
            return lambda: z3.DeclareSort(typ)
        typ = list(typs)[0]
        if not isinstance(typ, str):
            # TODO - we should ensure types are strings
            typ = typ.__name__
        return SORT_MAP.get(typ, z3.StringSort)

    def _const(self, value: Any, typ: str) -> z3.Const:
        sort = self._sort(typ)
        return z3.Const(value, sort())

    def _func(self, name: str, *args) -> z3.FuncDecl:
        args = tuple([args] + [z3.BoolSort()])
        return z3.Function(name, *args)

    def _tr(self, var: Any, bindings: dict) -> z3.ExprRef:
        if var is None:
            return z3.StringVal("None")
        if isinstance(var, Variable):
            if var.name not in bindings:
                if var.name in self.constants:
                    pf_arg = self.constants[var.name]
                else:
                    raise ValueError(f"Variable {var.name} not bound in {bindings} or {self.constants}")
            else:
                pf_arg = bindings[var.name]
            return pf_arg
        if isinstance(var, Term):
            if var.predicate not in NUMERIC_BUILTINS:
                raise NotImplementedError(f"Term not implemented: p: {var.predicate} {type(var)} v: {var}")
            args = [self._tr(a, bindings) for a in var.values]
            return NUMERIC_BUILTINS[var.predicate](*args)
        py_typ = type(var).__name__
        z3_typ = self._sort(py_typ)
        t2m_map = {
            z3.StringSort: z3.StringVal,
            z3.IntSort: z3.IntVal,
            z3.BoolSort: z3.BoolVal,
            z3.RealSort: z3.RealVal,
        }
        z3_valf = t2m_map.get(z3_typ, z3.StringVal)
        return z3_valf(var)

    def add_fact(self, fact: FactMixin) -> None:
        return self.add_sentence(fact)

    def add_sentence(self, sentence: Sentence) -> None:
        # Negation-as-failure has no classical reading; skipping the sentence keeps the
        # rest of a mixed theory usable (weakened) instead of failing whole-theory.
        if contains_negation_as_failure(sentence):
            if self.strict:
                raise NotInProfileError(
                    f"Z3 does not support negation-as-failure: {sentence}. "
                    "Consider typedlogic.transformations.clark_completion to obtain a classical rendering."
                )
            logger.warning(
                f"Skipping sentence with negation-as-failure (unsupported by Z3): {sentence}. "
                "The theory is weakened by this omission; consider "
                "typedlogic.transformations.clark_completion for a classical rendering."
            )
            return
        # normalize_variables(sentence)
        z3_expr = self.translate(sentence)
        self.wrapped_solver.add(z3_expr)

    def add_predicate_definition(self, predicate_definition: PredicateDefinition) -> None:
        """
        Add a predicate definition to the solver.

        E.g. `` Function('AncestorOf', StringSort(), StringSort(), BoolSort())``

        :param predicate_definition:
        :return:
        """
        args = [self._sort(a)() for a in predicate_definition.arguments.values()]
        args += [z3.BoolSort()]
        p = z3.Function(predicate_definition.predicate, *args)
        if not self.predicate_map:
            self.predicate_map = {}
        self.predicate_map[predicate_definition.predicate] = p
        if not self.predicate_definitions:
            self.predicate_definitions = {}
        self.predicate_definitions[predicate_definition.predicate] = predicate_definition

    def translate(self, sentence: Sentence, bindings: Optional[Dict[str, z3.SortRef]] = None) -> z3.ExprRef:
        """
        Translate a Sentence to a Z3 expression.

        :param sentence: The Sentence to translate
        :param bindings: local bindings of variable names to Z3 Sorts
        :return: The Z3 expression
        """
        if isinstance(sentence, tlog.And):
            return z3.And(*[self.translate(op, bindings) for op in sentence.operands])
        if isinstance(sentence, tlog.Or):
            return z3.Or(*[self.translate(op, bindings) for op in sentence.operands])
        if isinstance(sentence, tlog.Xor):
            return z3.Xor(*[self.translate(op, bindings) for op in sentence.operands])
        if isinstance(sentence, tlog.ExactlyOne):
            disj = []
            for a in sentence.operands:
                disj.append(
                    z3.And(
                        self.translate(a, bindings),
                        *[z3.Not(self.translate(b, bindings)) for b in sentence.operands if b != a],
                    )
                )
            return z3.Or(*disj)
        if isinstance(sentence, tlog.NegationAsFailure):
            raise NotInProfileError(
                f"Z3 has classical semantics and cannot translate negation-as-failure: {sentence}. "
                "Consider typedlogic.transformations.clark_completion to obtain a classical rendering."
            )
        if isinstance(sentence, tlog.Not):
            return z3.Not(self.translate(sentence.operands[0], bindings))
        if isinstance(sentence, tlog.Iff):
            # rewrite
            lhs = sentence.left
            rhs = sentence.right
            rewritten = tlog.And(tlog.Implies(lhs, rhs), tlog.Implies(rhs, lhs))
            return self.translate(rewritten, bindings)
        if isinstance(sentence, tlog.Implied):
            # rewrite
            lhs = sentence.operands[0]
            rhs = sentence.operands[1]
            return self.translate(tlog.Implies(rhs, lhs), bindings)
        if isinstance(sentence, tlog.Implies):
            lhs = self.translate(sentence.operands[0], bindings)
            rhs = self.translate(sentence.operands[1], bindings)
            return z3.Implies(lhs, rhs)
        if isinstance(sentence, (tlog.Forall, tlog.Exists)):
            # Copy the incoming bindings so variables bound by this quantifier are
            # scoped to its body and do not leak into sibling subformulas (variable
            # capture). Mutating a shared dict here would let an inner quantifier's
            # variable bind free occurrences of the same name elsewhere.
            bindings = dict(bindings) if bindings else {}
            args = []
            for v in sentence.variables:
                var_name = v.name
                domain = v.domain
                if domain is None:
                    # An untyped quantified variable otherwise defaults to a string sort, which
                    # mis-sorts it against typed predicates. Infer its type from the declared
                    # predicates it is used in (e.g. an int column) before falling back.
                    domain = self._infer_variable_domain(var_name, sentence.sentence)
                s = self._sort(domain)
                arg = z3.Const(var_name, s())  ## TODO
                bindings[var_name] = arg
                args.append(arg)
            inner_sentence = self.translate(sentence.sentence, bindings)
            if not args:
                # z3 rejects quantifiers over an empty variable list; a quantifier
                # binding nothing is logically equivalent to its body.
                return inner_sentence
            if isinstance(sentence, tlog.Exists):
                return z3.Exists(args, inner_sentence)
            else:
                return z3.ForAll(args, inner_sentence)
        if isinstance(sentence, CardinalityConstraint):
            # Must precede the generic Term branch, since CardinalityConstraint is a Term subclass.
            return self._translate_cardinality(sentence, bindings)
        if isinstance(sentence, (tlog.Term, typedlogic.pybridge.FactMixin)):  # TODO: use Expression
            if isinstance(sentence, typedlogic.pybridge.FactMixin):
                sentence = tlog.Term(fact_predicate(sentence), fact_arg_map(sentence))
            if not self.predicate_map or not self.predicate_definitions:
                raise ValueError("You must add predicate definitions before adding facts")
            pd = self.predicate_definitions.get(sentence.predicate)
            pf = self.predicate_map.get(sentence.predicate)
            if pf is None and sentence.predicate in NUMERIC_BUILTINS:
                pf = NUMERIC_BUILTINS[sentence.predicate]
            elif pf is None or pd is None:
                raise ValueError(
                    f"Predicate {sentence.predicate} not found in {self.predicate_map}\n"
                    "Did you remember to declare these as predicates?"
                )
            elif sentence.positional:
                # TODO: more elegant way to do this
                sentence = copy(sentence)
                sentence.make_keyword_indexed(list(pd.arguments.keys()))
            if not bindings:
                bindings = {}
            pf_args = [self._tr(var, bindings) for var in sentence.bindings.values()]
            try:
                z3_expr = pf(*pf_args)
            except Exception as e:
                raise ValueError(f"Error translating {sentence} args: {pf_args} to Z3 using {pf}:\n{e}")
            return z3_expr
        raise NotImplementedError(f"Not implemented:{type(sentence)} :: {sentence}")

    def _translate_cardinality(
        self, cc: CardinalityConstraint, bindings: Optional[Dict[str, z3.SortRef]] = None
    ) -> z3.ExprRef:
        """
        Translate a :class:`CardinalityConstraint` to an equivalent first-order Z3 formula.

        Z3 has no native counting quantifier over an unbounded sort, so a cardinality
        constraint is encoded using distinct existentials, which is the standard
        first-order rendering of counting:

        - *at least ``n``*: there exist ``n`` pairwise-distinct values satisfying the
          template and conditions.
        - *at most ``n``*: there do **not** exist ``n + 1`` pairwise-distinct values that
          all satisfy the template and conditions (so ``at most 0`` reduces to
          ``∀y. ¬(template ∧ conditions)``).

        Global variables (bound by an enclosing quantifier) are read from ``bindings``;
        the remaining (counted) variable is the aggregation key. Only a single counted
        variable is supported.

        :param cc: the cardinality constraint to translate
        :param bindings: variable bindings from the surrounding context
        :return: a boolean Z3 expression that holds iff the cardinality bounds are met
        """
        bindings = dict(bindings) if bindings else {}
        already_bound = set(bindings) | set(self.constants or {})
        counted = cc.counted_variables(bound=already_bound)
        if len(counted) != 1:
            raise NotImplementedError(
                f"Z3 cardinality translation currently supports exactly one counted variable, "
                f"got {[v.name for v in counted]} in {cc}"
            )
        counted_var = counted[0]
        template = cc.template
        conditions = cc.conditions
        assert template is not None, f"Cardinality constraint has no template: {cc}"
        # An untyped counted variable would otherwise default to a string sort, which
        # mis-sorts the witnesses against a typed predicate argument (e.g. an int column)
        # and triggers a Z3 sort mismatch. Infer its domain from the template/conditions
        # predicates it is used in, mirroring the quantifier-variable handling above.
        domain = counted_var.domain
        if domain is None:
            domain = self._infer_variable_domain(counted_var.name, template)
        if domain is None and conditions is not None:
            domain = self._infer_variable_domain(counted_var.name, conditions)
        sort = self._sort(domain)()

        def phi(const: z3.ExprRef) -> z3.ExprRef:
            local_bindings = dict(bindings)
            local_bindings[counted_var.name] = const
            atoms = [self.translate(template, local_bindings)]
            if conditions is not None and conditions != template:
                atoms.append(self.translate(conditions, local_bindings))
            return z3.And(*atoms)

        def distinct_witnesses(count: int, tag: str) -> z3.ExprRef:
            consts = [z3.Const(f"{counted_var.name}__card_{tag}{i}", sort) for i in range(count)]
            body = [phi(c) for c in consts]
            if len(consts) > 1:
                body.append(z3.Distinct(*consts))
            return z3.Exists(consts, z3.And(*body))

        conjuncts = []
        if cc.minimum_number is not None and cc.minimum_number > 0:
            conjuncts.append(distinct_witnesses(cc.minimum_number, "ge"))
        if cc.maximum_number is not None:
            conjuncts.append(z3.Not(distinct_witnesses(cc.maximum_number + 1, "le")))
        if not conjuncts:
            return z3.BoolVal(True)
        if len(conjuncts) == 1:
            return conjuncts[0]
        return z3.And(*conjuncts)

    def _infer_variable_domain(self, var_name: str, sentence: Any) -> Optional[str]:
        """
        Infer an untyped quantified variable's type from its use in declared predicates.

        Walks the quantifier body and returns the declared argument type at the first
        position where the variable appears as a direct argument of a declared predicate.
        Returns ``None`` when no such use exists, leaving the caller to fall back to the
        default sort.

        :param var_name: The name of the quantified variable.
        :param sentence: The body of the quantified sentence.
        :return: The inferred type name, or ``None`` if it cannot be determined.
        """
        if not self.predicate_definitions:
            return None
        for term in self._iter_terms(sentence):
            pd = self.predicate_definitions.get(term.predicate)
            if pd is None:
                continue
            arg_names = list(pd.arguments.keys())
            arg_types = list(pd.arguments.values())
            for i, (key, value) in enumerate(term.bindings.items()):
                if not (isinstance(value, Variable) and value.name == var_name):
                    continue
                idx = i if term.positional else (arg_names.index(key) if key in arg_names else i)
                if idx < len(arg_types):
                    return arg_types[idx]
        return None

    def _iter_terms(self, node: Any) -> Iterator[Term]:
        """
        Yield every ``Term`` atom in a sentence tree, recursing into nested terms.

        :param node: A sentence or sub-expression.
        :return: An iterator over the contained terms.
        """
        if isinstance(node, Term):
            yield node
            for value in node.values:
                yield from self._iter_terms(value)
            return
        if isinstance(node, (tlog.Forall, tlog.Exists)):
            yield from self._iter_terms(node.sentence)
            return
        operands = getattr(node, "operands", None)
        if operands is not None:
            for operand in operands:
                yield from self._iter_terms(operand)

    def dump(self) -> str:
        return str(self.wrapped_solver)
