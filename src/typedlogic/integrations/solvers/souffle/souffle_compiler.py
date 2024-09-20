from typing import ClassVar, Optional, Union

from typedlogic import Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import NotInProfileError
from typedlogic.transformations import (
    PrologConfig,
    as_prolog,
    force_stratification,
    replace_constants,
    to_horn_rules,
)


def _base_type(t: str) -> str:
    if t in ["int", "float"]:
        return "number"
    else:
        return "symbol"

def _type(name: str) -> str:
    return name.capitalize()

def _pred(name: str) -> str:
    # return name.lower()
    return name

def _var(name: str) -> str:
    return name.lower()

class SouffleCompiler(Compiler):

    default_suffix: ClassVar[str] = "dl"

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None,  **kwargs) -> str:
        blocks = []

        #for k, v in theory.constants.items():
        #    blocks.append(f".const {k}: {_base_type(v)}")
        tds = theory.type_definitions or {}
        for k, v in tds.items():
            if isinstance(v, list):
                base_types = [_base_type(x) for x in v if isinstance(x, str)]
                blocks.append(f".type {_type(k)} = {' | '.join(base_types)}")
            else:
                if not isinstance(v, str):
                    raise NotImplementedError(f"Only string types are supported; got: {v}")
                blocks.append(f".type {_type(k)} = {_base_type(v)}")

        if not theory.predicate_definitions:
            raise ValueError("No predicate definitions found in theory")
        for pd in theory.predicate_definitions:
            p = _pred(pd.predicate)
            def _ref_type(t):
                if t in theory.type_definitions:
                    return _type(t)
                else:
                    return _base_type(t)
            args = [f"{_var(v)}: {_ref_type(v_typ)}" for v, v_typ in pd.arguments.items()]
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





