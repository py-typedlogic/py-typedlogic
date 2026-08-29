from dataclasses import dataclass
from typing import ClassVar, Dict, List, Optional, Set, Union

from typedlogic import Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import DefinedType, NotInProfileError
from typedlogic.transformations import (
    PrologConfig,
    as_prolog,
    force_stratification,
    replace_constants,
    to_horn_rules,
)

#: Names reserved by Souffle for its own primitive types; a defined type using one of
#: these names is renamed rather than emitted as a redefinition of the primitive.
SOUFFLE_PRIMITIVE_TYPES = frozenset({"symbol", "number", "unsigned", "float"})


def _base_type(t: str) -> str:
    if t in ["int", "float"]:
        return "number"
    else:
        return "symbol"


def _type(name: str) -> str:
    """
    Render a defined type name as a Souffle type identifier.

    The name is preserved as-is; only collisions with Souffle's own primitive type
    names are renamed.

        >>> _type("PersonID")
        'PersonID'
        >>> _type("symbol")
        'symbol_t'

    """
    if name in SOUFFLE_PRIMITIVE_TYPES:
        return f"{name}_t"
    return name


def _pred(name: str) -> str:
    # return name.lower()
    return name


def _var(name: str) -> str:
    return name.lower()


def _referenced_types(theory: Theory) -> Set[str]:
    """
    Return the defined type names reachable from predicate argument declarations.

    A type definition that no predicate signature mentions cannot affect the generated
    program, so emitting it produces a declaration that merely *looks* like it brands
    something. This most often happens with plain Python aliases (``NameType = str``),
    which Python erases before annotations are introspected.

    :param theory: The theory being compiled
    :return: Names of type definitions transitively referenced by predicate arguments
    """
    tds = theory.type_definitions or {}
    seen: Set[str] = set()
    stack: List[DefinedType] = [t for pd in theory.predicate_definitions for t in pd.arguments.values()]
    while stack:
        t = stack.pop()
        if isinstance(t, list):
            stack.extend(t)
            continue
        if not isinstance(t, str) or t in seen or t not in tds:
            continue
        seen.add(t)
        stack.append(tds[t])
    return seen


@dataclass
class SouffleCompiler(Compiler):
    """
    Compile a theory to a Souffle Datalog program.

    Defined types are emitted as Souffle *subtypes* (``<:``) rather than aliases (``=``),
    so that Souffle enforces the distinction between two types that share a primitive
    representation. See :attr:`strict_subtypes` to opt out.
    """

    default_suffix: ClassVar[str] = "dl"

    strict_subtypes: bool = True
    """
    Emit branded types as Souffle subtypes (``.type PersonID <: symbol``).

    With ``=`` — the previous behaviour — Souffle treats the name as a pure alias, so
    ``PersonID`` and ``OrgID`` are mutually assignable and no branding is enforced.

    Set to ``False`` when a branded type over ``number`` takes part in arithmetic:
    Souffle types the result of an arithmetic functor as ``number``, which is not a
    subtype of the branded type, so a rule such as ``Age(x + 1) :- Age(x)`` needs an
    explicit ``as(x + 1, Age)`` cast under strict subtyping.
    """

    def _type_declarations(self, theory: Theory) -> List[str]:
        """
        Render the ``.type`` declarations for a theory.

        :param theory: The theory being compiled
        :return: One Souffle type declaration per referenced type definition
        """
        tds: Dict[str, DefinedType] = theory.type_definitions or {}
        referenced = _referenced_types(theory)
        blocks = []
        for k, v in tds.items():
            if k not in referenced:
                continue
            if isinstance(v, list):
                # A union is a genuine sum of its members, so it stays an `=` definition.
                members = [self._ref_type(theory, x) for x in v if isinstance(x, str)]
                blocks.append(f".type {_type(k)} = {' | '.join(members)}")
            else:
                if not isinstance(v, str):
                    raise NotImplementedError(f"Only string types are supported; got: {v}")
                operator = "<:" if self.strict_subtypes else "="
                blocks.append(f".type {_type(k)} {operator} {self._ref_type(theory, v)}")
        return blocks

    @staticmethod
    def _ref_type(theory: Theory, t: str) -> str:
        """
        Render a reference to a type, resolving defined types by name.

        :param theory: The theory being compiled
        :param t: A type name, either a defined type or a base type
        :return: The Souffle type name to use at a reference site
        """
        if t in (theory.type_definitions or {}):
            return _type(t)
        return _base_type(t)

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        blocks = []

        # for k, v in theory.constants.items():
        #    blocks.append(f".const {k}: {_base_type(v)}")
        blocks.extend(self._type_declarations(theory))

        if not theory.predicate_definitions:
            raise ValueError("No predicate definitions found in theory")
        for pd in theory.predicate_definitions:
            p = _pred(pd.predicate)
            args = [f"{_var(v)}: {self._ref_type(theory, v_typ)}" for v, v_typ in pd.arguments.items()]
            blocks.append(f".decl {p}({', '.join(args)})")

        config = PrologConfig(
            use_lowercase_vars=True,
            use_uppercase_predicates=None,
            negation_symbol="!",
            double_quote_strings=True,
            operator_map={
                "eq": "=",
            },
            include_parens_for_zero_args=True,
        )

        horn_rules = []
        for s in theory.sentences + theory.ground_terms:
            s = replace_constants(s, theory.constants)
            # TODO: allow preserving existentials
            try:
                tr_sentences = to_horn_rules(s)
                horn_rules.extend(tr_sentences)
            except NotInProfileError:
                # blocks.append(f"% IGNORED: {s} // {e}")
                continue

        horn_rules = force_stratification(horn_rules)
        for rule in horn_rules:
            try:
                prolog = as_prolog(rule, config)
                if not prolog.endswith("."):
                    prolog += "."
                blocks.append(prolog)
            except NotInProfileError:
                # blocks.append(f"% IGNORED: {s} // {e}")
                continue

        return "\n".join(blocks)
