"""
Compiler for the Common Logic Interchange Format (CLIF).

CLIF is the s-expression based concrete syntax for Common Logic (ISO/IEC 24707).
See https://en.wikipedia.org/wiki/Common_Logic for background.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import AbstractSet, Any, ClassVar, List, Optional, Union

from typedlogic import Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import (
    And,
    ExactlyOne,
    Exists,
    Extension,
    Forall,
    Iff,
    Implied,
    Implies,
    NegationAsFailure,
    Not,
    NotInProfileError,
    Or,
    Sentence,
    Term,
    Variable,
    Xor,
)

CLIF_RESERVED = frozenset(
    [
        "and",
        "or",
        "not",
        "if",
        "iff",
        "forall",
        "exists",
        "=",
        "true",
        "false",
        "null",
        "cl-text",
        "cl-module",
        "cl-imports",
        "cl-comment",
    ]
)
_BARE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")


def quote_string(value: str) -> str:
    r"""
    Quote a string using CLIF single-quote conventions.

    >>> quote_string("Fred Smith")
    "'Fred Smith'"
    >>> quote_string("it's")
    "'it\\'s'"

    :param value: the raw string
    :return: a CLIF quoted string
    """
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def render_name(name: str) -> str:
    """
    Render a name, quoting it if it is not a valid bare CLIF name.

    >>> render_name("Fred")
    'Fred'
    >>> render_name("Fred Smith")
    "'Fred Smith'"
    >>> render_name("not")
    "'not'"

    :param name: the name to render
    :return: a bare or quoted CLIF name
    """
    if _BARE_NAME.match(name) and name not in CLIF_RESERVED:
        return name
    return quote_string(name)


def _render_value(value: Any, bound: AbstractSet[str]) -> str:
    if isinstance(value, Variable):
        if value.name in bound:
            return value.name
        return f"?{value.name}"
    if isinstance(value, Sentence):
        return as_clif(value, bound)
    if isinstance(value, Enum):
        return _render_value(value.value, bound)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "null"
    if isinstance(value, str):
        return render_name(value)
    return quote_string(str(value))


def _render_binding(variable: Variable) -> str:
    if variable.domain:
        return f"({variable.name} {render_name(str(variable.domain))})"
    return variable.name


def as_clif(sentence: Sentence, bound: Optional[AbstractSet[str]] = None) -> str:
    """
    Convert a sentence to CLIF syntax.

    >>> from typedlogic import Term, Variable, Forall, Exists, And, Or, Not, Implies
    >>> x = Variable("x")
    >>> y = Variable("y")
    >>> print(as_clif(Term("Person", "Fred")))
    (Person Fred)
    >>> print(as_clif(Forall([x, y], Implies(Term("FriendOf", x, y), Term("FriendOf", y, x)))))
    (forall (x y) (if (FriendOf x y) (FriendOf y x)))
    >>> print(as_clif(Exists([x], And(Term("P", x), Not(Term("Q", x))))))
    (exists (x) (and (P x) (not (Q x))))

    Variables that are not bound by an enclosing quantifier are rendered with a ``?`` prefix:

    >>> print(as_clif(Term("P", x)))
    (P ?x)

    :param sentence: the sentence to convert
    :param bound: names of variables bound by enclosing quantifiers
    :return: CLIF representation of the sentence
    """
    if bound is None:
        bound = frozenset()
    if isinstance(sentence, Extension):
        sentence = sentence.to_model_object()
    if isinstance(sentence, Term):
        predicate = sentence.predicate
        if isinstance(predicate, Variable):
            rendered_predicate = _render_value(predicate, bound)
        elif predicate == "eq":
            rendered_predicate = "="
        else:
            rendered_predicate = render_name(predicate)
        parts = [rendered_predicate] + [_render_value(v, bound) for v in sentence.bindings.values()]
        return f"({' '.join(parts)})"
    if isinstance(sentence, (Forall, Exists)):
        quantifier = "forall" if isinstance(sentence, Forall) else "exists"
        inner_bound = set(bound) | {v.name for v in sentence.variables}
        bindings = " ".join(_render_binding(v) for v in sentence.variables)
        return f"({quantifier} ({bindings}) {as_clif(sentence.sentence, inner_bound)})"
    if isinstance(sentence, Xor):
        from typedlogic.transformations import expand_xor

        return as_clif(expand_xor(sentence), bound)
    if isinstance(sentence, ExactlyOne):
        from typedlogic.transformations import expand_exactly_one

        return as_clif(expand_exactly_one(sentence), bound)
    if isinstance(sentence, Implies):
        return f"(if {as_clif(sentence.antecedent, bound)} {as_clif(sentence.consequent, bound)})"
    if isinstance(sentence, Implied):
        return f"(if {as_clif(sentence.antecedent, bound)} {as_clif(sentence.consequent, bound)})"
    if isinstance(sentence, Iff):
        return f"(iff {as_clif(sentence.left, bound)} {as_clif(sentence.right, bound)})"
    if isinstance(sentence, NegationAsFailure):
        raise NotInProfileError("CLIF does not support negation as failure")
    if isinstance(sentence, Not):
        return f"(not {as_clif(sentence.negated, bound)})"
    if isinstance(sentence, And):
        operands = " ".join(as_clif(op, bound) for op in sentence.operands)
        return f"(and {operands})" if operands else "(and)"
    if isinstance(sentence, Or):
        operands = " ".join(as_clif(op, bound) for op in sentence.operands)
        return f"(or {operands})" if operands else "(or)"
    raise NotInProfileError(f"Unsupported sentence type: {type(sentence)}")


@dataclass
class ClifCompiler(Compiler):
    """
    Compiles a Theory to the Common Logic Interchange Format (CLIF).

    Example:
    -------
        >>> from typedlogic import Forall, Implies, PredicateDefinition, Term, Theory, Variable
        >>> theory = Theory(name="friends")
        >>> x = Variable("x")
        >>> y = Variable("y")
        >>> theory.predicate_definitions = [PredicateDefinition("FriendOf", {"x": "str", "y": "str"})]
        >>> theory.add(Term("FriendOf", "Alice", "Bob"))
        >>> theory.add(Forall([x, y], Implies(Term("FriendOf", x, y), Term("FriendOf", y, x))))
        >>> compiler = ClifCompiler()
        >>> print(compiler.compile(theory))
        (cl-text friends
          (FriendOf Alice Bob)
          (forall (x y) (if (FriendOf x y) (FriendOf y x)))
        )

    """

    default_suffix: ClassVar[str] = "clif"

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        """
        Compile a Theory object into a CLIF document.

        :param theory: the theory to compile
        :param syntax: unused
        :param kwargs: unused
        :return: CLIF representation of the theory
        """
        sentences: List[Sentence] = list(theory.sentences) + list(theory.ground_terms)
        lines = [as_clif(s) for s in sentences]
        if theory.name:
            body = "\n".join(f"  {line}" for line in lines)
            if body:
                return f"(cl-text {render_name(theory.name)}\n{body}\n)"
            return f"(cl-text {render_name(theory.name)})"
        return "\n".join(lines)

    def compile_sentence(self, sentence: Sentence, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        """
        Compile an individual sentence to CLIF.

        :param sentence: the sentence to compile
        :param syntax: unused
        :param kwargs: unused
        :return: CLIF representation of the sentence
        """
        return as_clif(sentence)
