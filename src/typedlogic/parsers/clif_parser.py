"""
Parser for the Common Logic Interchange Format (CLIF).

CLIF is the s-expression based concrete syntax for Common Logic (ISO/IEC 24707).
See https://en.wikipedia.org/wiki/Common_Logic for background.
"""

import re
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Iterator, List, Optional, TextIO, Tuple, Union

from typedlogic import And, Exists, Forall, Iff, Implies, Not, Or, PredicateDefinition, Term, Theory
from typedlogic.builtins import NAME_TO_INFIX_OP
from typedlogic.datamodel import BooleanSentence, QuantifiedSentence, Sentence, Variable
from typedlogic.parser import Parser, ValidationMessage

TEXT_KEYWORDS = frozenset(["cl-text", "cl:text", "cl-module", "cl:module"])
COMMENT_KEYWORDS = frozenset(["cl-comment", "cl:comment"])
IMPORT_KEYWORDS = frozenset(["cl-imports", "cl:imports"])

_NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
_SYMBOL_TERMINATORS = frozenset(["(", ")", "'", '"'])


class ClifSyntaxError(ValueError):
    """Raised when a CLIF document cannot be parsed."""

    pass


class _Symbol(str):
    """A bare CLIF name, as distinct from a quoted string."""

    pass


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _tokenize(text: str) -> Iterator[Tuple[str, Any]]:
    """Yield (kind, value) tokens, where kind is one of 'lparen', 'rparen', 'string', 'symbol'."""
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end == -1 else end + 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end == -1:
                raise ClifSyntaxError(f"Unterminated comment starting at line {_line_of(text, i)}")
            i = end + 2
            continue
        if c == "(":
            yield "lparen", None
            i += 1
            continue
        if c == ")":
            yield "rparen", None
            i += 1
            continue
        if c in "'\"":
            start = i
            i += 1
            chars: List[str] = []
            while i < n and text[i] != c:
                if text[i] == "\\" and i + 1 < n:
                    chars.append(text[i + 1])
                    i += 2
                else:
                    chars.append(text[i])
                    i += 1
            if i >= n:
                raise ClifSyntaxError(f"Unterminated string starting at line {_line_of(text, start)}")
            i += 1
            yield "string", "".join(chars)
            continue
        start = i
        while i < n and not text[i].isspace() and text[i] not in _SYMBOL_TERMINATORS:
            i += 1
        yield "symbol", _Symbol(text[start:i])


def _atom_value(kind: str, value: Any) -> Any:
    if kind == "symbol" and _NUMBER.match(value):
        if any(c in value for c in ".eE"):
            return float(value)
        return int(value)
    return value


def _read_forms(text: str) -> List[Any]:
    """Read a CLIF document into nested lists of atoms."""
    forms: List[Any] = []
    stack: List[List[Any]] = []
    for kind, value in _tokenize(text):
        if kind == "lparen":
            new_form: List[Any] = []
            if stack:
                stack[-1].append(new_form)
            else:
                forms.append(new_form)
            stack.append(new_form)
        elif kind == "rparen":
            if not stack:
                raise ClifSyntaxError("Unbalanced closing parenthesis")
            stack.pop()
        else:
            atom = _atom_value(kind, value)
            if stack:
                stack[-1].append(atom)
            else:
                forms.append(atom)
    if stack:
        raise ClifSyntaxError("Unbalanced opening parenthesis")
    return forms


class ClifParser(Parser):
    """
    A parser for Common Logic Interchange Format (CLIF) documents.

    Example:
    -------
        >>> parser = ClifParser()
        >>> theory = parser.parse('''
        ... (cl-text friends
        ...   (FriendOf Alice Bob)
        ...   (forall (x y) (if (FriendOf x y) (FriendOf y x)))
        ... )
        ... ''')
        >>> theory.name
        'friends'
        >>> for s in theory.sentences:
        ...     print(s)
        FriendOf(Alice, Bob)
        ∀x: None, y: None : (FriendOf(?x, ?y) -> FriendOf(?y, ?x))

    """

    default_suffix = "clif"

    def parse(self, source: Union[Path, str, TextIO], **kwargs) -> Theory:
        """
        Parse a CLIF document into a Theory.

        :param source: a path to a file, CLIF text, or a file-like object
        :param kwargs: unused
        :return: the parsed theory
        """
        text = self._read_source(source)
        theory = Theory()
        for form in _read_forms(text):
            self._process_form(form, theory)
        theory.predicate_definitions = self._infer_predicate_definitions(theory)
        return theory

    def parse_ground_terms(self, source: Union[Path, str, TextIO], **kwargs) -> List[Term]:
        """
        Parse a CLIF document and return all ground terms (facts).

        :param source: a path to a file, CLIF text, or a file-like object
        :param kwargs: unused
        :return: ground terms
        """
        theory = self.parse(source, **kwargs)
        return [s for s in theory.sentences if isinstance(s, Term) and s.is_ground]

    def validate_iter(self, source: Union[Path, str, TextIO, ModuleType], **kwargs) -> Iterator[ValidationMessage]:
        """
        Validate a CLIF document.

        :param source: a path to a file, CLIF text, or a file-like object
        :param kwargs: unused
        :return: iterator of validation messages
        """
        if isinstance(source, ModuleType):
            raise ValueError("ClifParser cannot validate python modules")
        try:
            self.parse(source, **kwargs)
        except ClifSyntaxError as e:
            yield ValidationMessage(message=str(e))

    def _read_source(self, source: Union[Path, str, TextIO]) -> str:
        if isinstance(source, Path):
            return source.read_text(encoding="utf-8")
        if hasattr(source, "read"):
            return source.read()  # type: ignore[union-attr]
        return str(source)

    def _process_form(self, form: Any, theory: Theory) -> None:
        if not isinstance(form, list):
            raise ClifSyntaxError(f"Unexpected top-level atom: {form!r}")
        if form and isinstance(form[0], _Symbol):
            keyword = str(form[0])
            if keyword in TEXT_KEYWORDS:
                if len(form) < 2:
                    raise ClifSyntaxError(f"({keyword} ...) requires a name")
                theory.name = str(form[1])
                for sub_form in form[2:]:
                    self._process_form(sub_form, theory)
                return
            if keyword in COMMENT_KEYWORDS or keyword in IMPORT_KEYWORDS:
                return
        theory.add(self._sentence(form, {}))

    def _sentence(self, form: Any, bound: Dict[str, Variable]) -> Sentence:
        if not isinstance(form, list):
            raise ClifSyntaxError(f"Expected a sentence, got atom: {form!r}")
        if not form:
            raise ClifSyntaxError("Empty sentence: ()")
        head = form[0]
        operator = str(head) if isinstance(head, _Symbol) else None
        if operator in ("forall", "exists"):
            return self._quantified(form, bound)
        if operator == "and":
            return And(*[self._sentence(f, bound) for f in form[1:]])
        if operator == "or":
            return Or(*[self._sentence(f, bound) for f in form[1:]])
        if operator == "not":
            if len(form) != 2:
                raise ClifSyntaxError(f"(not ...) requires exactly one sentence: {form!r}")
            return Not(self._sentence(form[1], bound))
        if operator == "if":
            if len(form) != 3:
                raise ClifSyntaxError(f"(if ...) requires exactly two sentences: {form!r}")
            return Implies(self._sentence(form[1], bound), self._sentence(form[2], bound))
        if operator == "iff":
            if len(form) != 3:
                raise ClifSyntaxError(f"(iff ...) requires exactly two sentences: {form!r}")
            return Iff(self._sentence(form[1], bound), self._sentence(form[2], bound))
        if operator == "=":
            return Term("eq", *[self._argument(f, bound) for f in form[1:]])
        return self._atom(form, bound)

    def _quantified(self, form: List[Any], bound: Dict[str, Variable]) -> Sentence:
        quantifier = str(form[0])
        if len(form) < 3 or not isinstance(form[1], list):
            raise ClifSyntaxError(f"({quantifier} ...) requires a binding list and a body: {form!r}")
        variables = [self._binding(b, quantifier) for b in form[1]]
        inner_bound = {**bound, **{v.name: v for v in variables}}
        bodies = [self._sentence(f, inner_bound) for f in form[2:]]
        body = bodies[0] if len(bodies) == 1 else And(*bodies)
        if quantifier == "forall":
            return Forall(variables, body)
        return Exists(variables, body)

    def _binding(self, form: Any, quantifier: str) -> Variable:
        domain: Optional[str] = None
        if isinstance(form, list):
            if len(form) != 2:
                raise ClifSyntaxError(f"Invalid binding in ({quantifier} ...): {form!r}")
            form, domain_form = form
            domain = str(domain_form)
        if not isinstance(form, str):
            raise ClifSyntaxError(f"Invalid binding in ({quantifier} ...): {form!r}")
        name = str(form)
        if name.startswith("?"):
            name = name[1:]
        return Variable(name, domain)

    def _atom(self, form: List[Any], bound: Dict[str, Variable]) -> Term:
        head = form[0]
        if isinstance(head, list):
            raise ClifSyntaxError(f"Compound terms in operator position are not supported: {form!r}")
        predicate: Union[str, Variable]
        name = str(head)
        if isinstance(head, _Symbol) and name.startswith("?"):
            predicate = bound.get(name[1:], Variable(name[1:]))
        elif isinstance(head, _Symbol) and name in bound:
            predicate = bound[name]
        else:
            predicate = name
        arguments = [self._argument(f, bound) for f in form[1:]]
        # Term supports Variable predicates at runtime (hilog-style), but is annotated as str-only
        return Term(predicate, *arguments)  # type: ignore[arg-type]

    def _argument(self, form: Any, bound: Dict[str, Variable]) -> Any:
        if isinstance(form, list):
            return self._sentence(form, bound)
        if isinstance(form, _Symbol):
            name = str(form)
            if name.startswith("?"):
                return bound.get(name[1:], Variable(name[1:]))
            if name in bound:
                return bound[name]
            if name == "true":
                return True
            if name == "false":
                return False
            if name == "null":
                return None
            return name
        return form

    def _infer_predicate_definitions(self, theory: Theory) -> List[PredicateDefinition]:
        """Infer predicate definitions from the atoms used in the parsed sentences."""
        inferred: Dict[str, Dict[str, str]] = {}

        def argument_type(value: Any) -> str:
            if isinstance(value, Variable):
                return value.domain or "str"
            if isinstance(value, bool):
                return "bool"
            if isinstance(value, (int, float)):
                return type(value).__name__
            return "str"

        def visit(sentence: Sentence) -> None:
            if isinstance(sentence, Term):
                predicate = sentence.predicate
                if isinstance(predicate, str) and predicate not in NAME_TO_INFIX_OP:
                    arguments = {f"arg{i}": argument_type(v) for i, v in enumerate(sentence.bindings.values())}
                    if predicate not in inferred or len(arguments) > len(inferred[predicate]):
                        inferred[predicate] = arguments
                for value in sentence.bindings.values():
                    if isinstance(value, Sentence):
                        visit(value)
                return
            if isinstance(sentence, QuantifiedSentence):
                visit(sentence.sentence)
                return
            if isinstance(sentence, BooleanSentence):
                for operand in sentence.operands:
                    visit(operand)

        for s in theory.sentences:
            visit(s)
        return [PredicateDefinition(predicate, arguments) for predicate, arguments in inferred.items()]
