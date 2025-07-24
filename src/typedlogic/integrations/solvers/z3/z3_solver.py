from copy import copy
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Dict, Iterator, List, Mapping, Optional, Set, Type, Union

import z3
from z3 import SortRef

import typedlogic as tlog
import typedlogic.pybridge
from typedlogic import FactMixin, Variable
from typedlogic.builtins import NUMERIC_BUILTINS
from typedlogic.datamodel import DefinedType, PredicateDefinition, Sentence, Term
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
    A solver that uses Z3.

        >>> from typedlogic.integrations.frameworks.pydantic import FactBaseModel
        >>> class AncestorOf(FactBaseModel):
        ...     ancestor: str
        ...     descendant: str
        >>> solver = Z3Solver()
        >>> solver.add_predicate_definition(PredicateDefinition(predicate="AncestorOf", arguments={'ancestor': "str", 'descendant': "str"}))
        >>> solver.add_fact(AncestorOf(ancestor='p1', descendant='p1a'))
        >>> solver.add_fact(AncestorOf(ancestor='p1a', descendant='p1aa'))
        >>> from typedlogic import SentenceGroup, PredicateDefinition
        >>> aa = SentenceGroup(name="transitivity-of-ancestor-of")
        >>> solver.add_sentence_group(aa)
        >>> soln = solver.check()

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
            if not bindings:
                bindings = {}
            args = []
            for v in sentence.variables:
                var_name = v.name
                domain = v.domain
                s = self._sort(domain)
                arg = z3.Const(var_name, s())  ## TODO
                bindings[var_name] = arg
                args.append(arg)
            inner_sentence = self.translate(sentence.sentence, bindings)
            if isinstance(sentence, tlog.Exists):
                return z3.Exists(args, inner_sentence)
            else:
                return z3.ForAll(args, inner_sentence)
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
            pf_args = []
            for arg_name, var in sentence.bindings.items():
                if not bindings:
                    bindings = {}
                if isinstance(var, Variable):
                    if var.name not in bindings:
                        if var.name in self.constants:
                            pf_arg = self.constants[var.name]
                        else:
                            raise ValueError(f"Variable {var.name} not bound in {bindings} or {self.constants}")
                    else:
                        pf_arg = bindings[var.name]
                    pf_args.append(pf_arg)
                elif isinstance(var, Term):
                    args = [self._tr(a, bindings) for a in var.values]
                    p = var.predicate
                    if p == "add":
                        pf_args.append(args[0] + args[1])
                    elif p == "gt":
                        pf_args.append(args[0] > args[1])
                    elif p == "date":
                        pf_args.append(args[0] == args[1])
                    else:
                        raise NotImplementedError(f"Term not implemented: p: {p} {type(var)} v: {var}")
                elif var is None:
                    pf_args.append(z3.StringVal("None"))
                else:
                    py_typ = type(var).__name__
                    z3_typ = self._sort(py_typ)
                    t2m_map = {
                        z3.StringSort: z3.StringVal,
                        z3.IntSort: z3.IntVal,
                        z3.BoolSort: z3.BoolVal,
                        z3.RealSort: z3.RealVal,
                    }
                    z3_valf = t2m_map.get(z3_typ, z3.StringVal)
                    pf_arg = z3_valf(var)
                    pf_args.append(pf_arg)
            try:
                z3_expr = pf(*pf_args)
            except Exception as e:
                raise ValueError(f"Error translating {sentence} args: {pf_args} to Z3 using {pf}:\n{e}")
            return z3_expr
        raise NotImplementedError(f"Not implemented:{type(sentence)} :: {sentence}")

    def dump(self) -> str:
        return str(self.wrapped_solver)
