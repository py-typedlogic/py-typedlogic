"""Parser for TypedLogic's ergonomic text rule syntax."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, TextIO, Union

from lark import Lark, Transformer
from lark.exceptions import LarkError

from typedlogic import And, Exists, Forall, Iff, Implies, NegationAsFailure, Not, Or, PredicateDefinition, Term, Theory
from typedlogic.datamodel import Sentence, SentenceGroup, SentenceGroupType, Variable
from typedlogic.parser import Parser, ValidationMessage

GRAMMAR = r"""
start: statement*

statement: doc_comment* statement_body "."
?statement_body: declaration
               | constraint
               | sentence

doc_comment: DOC_COMMENT

?declaration: type_decl
            | predicate_decl

type_decl: TYPE NAME [":" type_expr]
predicate_decl: PRED NAME "/" INT                         -> predicate_arity_decl
              | PRED NAME "(" [predicate_arg_list] ")"    -> predicate_signature_decl

predicate_arg_list: predicate_arg ("," predicate_arg)*
predicate_arg: NAME ":" type_expr
type_expr: NAME

constraint: IF sentence

?sentence: quantifier
         | implication

quantifier: ALL var_decl_list "|" sentence     -> forall
          | EXISTS var_decl_list "|" sentence  -> exists

var_decl_list: var_decl ("," var_decl)*
var_decl: var_name [":" type_expr]
?var_name: NAME           -> bare_var_name
         | QVAR           -> marked_var_name

?implication: disjunction
            | disjunction ARROW implication   -> implies
            | disjunction RARROW implication  -> implies
            | disjunction LARROW implication  -> implied
            | disjunction IF implication      -> rule
            | disjunction IFF implication     -> iff

?disjunction: conjunction
            | disjunction "|" conjunction     -> or_

?conjunction: amp_conjunction
            | conjunction "," amp_conjunction -> and_

?amp_conjunction: unary
                | amp_conjunction "&" unary   -> and_

?unary: NAF unary                            -> naf
      | "~" unary                            -> strict_not
      | "!" unary                            -> strict_not
      | comparison

?comparison: sum
           | sum "==" sum                    -> eq
           | sum "=" sum                     -> eq
           | sum "!=" sum                    -> ne
           | sum "<=" sum                    -> le
           | sum "<" sum                     -> lt
           | sum ">=" sum                    -> ge
           | sum ">" sum                     -> gt

?sum: product
    | sum "+" product                        -> add
    | sum "-" product                        -> sub

?product: power
        | product "*" power                  -> mul
        | product "/" power                  -> truediv

?power: atom_expr
      | atom_expr "**" power                 -> pow

?atom_expr: quoted_sentence
          | atom
          | value
          | "(" sentence ")"

atom: predicate_ref "(" [arg_list] ")"
predicate_ref: NAME                          -> predicate_name
             | PRED                          -> predicate_keyword_name
             | HILOG_NAME                    -> hilog_predicate_name
             | QVAR                          -> hilog_marked_predicate_name

arg_list: arg_expr ("," arg_expr)*

?arg_expr: arg_comparison

?arg_comparison: arg_sum
               | arg_sum "==" arg_sum         -> eq
               | arg_sum "=" arg_sum          -> eq
               | arg_sum "!=" arg_sum         -> ne
               | arg_sum "<=" arg_sum         -> le
               | arg_sum "<" arg_sum          -> lt
               | arg_sum ">=" arg_sum         -> ge
               | arg_sum ">" arg_sum          -> gt

?arg_sum: arg_product
        | arg_sum "+" arg_product             -> add
        | arg_sum "-" arg_product             -> sub

?arg_product: arg_power
            | arg_product "*" arg_power       -> mul
            | arg_product "/" arg_power       -> truediv

?arg_power: arg_atom_expr
          | arg_atom_expr "**" arg_power      -> pow

?arg_atom_expr: quoted_sentence
              | atom
              | value
              | "(" arg_expr ")"

quoted_sentence: THAT "(" sentence ")"

?value: QVAR                                 -> marked_variable
      | NAME                                 -> bare_name
      | SIGNED_NUMBER                        -> number
      | ESCAPED_STRING                       -> string
      | SINGLE_QUOTED_STRING                 -> string
      | TRUE                                 -> true
      | FALSE                                -> false

ALL.2: "all" | "forall" | "∀"
EXISTS.2: "exists" | "some" | "∃"
TYPE.2: "type" | "typedef"
PRED.2: "pred" | "predicate" | "rel" | "relation"
NAF.2: "not" | "\\+"
IF: ":-"
ARROW: "->"
RARROW: "=>"
LARROW: "<-"
IFF: "<->" | "<=>"
TRUE.2: "true"
FALSE.2: "false"
THAT.2: "that"

HILOG_NAME: "@" NAME
QVAR: "?" NAME
NAME: /[A-Za-z_][A-Za-z0-9_]*/
SINGLE_QUOTED_STRING: /'([^'\\]|\\.)*'/
DOC_COMMENT: /\/\/\/[^\n]*/
COMMENT: /#[^\n]*/
LINE_COMMENT: /\/\/(?!\/)[^\n]*/

%import common.SIGNED_NUMBER
%import common.INT
%import common.ESCAPED_STRING
%import common.WS
%ignore WS
%ignore COMMENT
%ignore LINE_COMMENT
"""


@dataclass(frozen=True)
class NameRef:
    """A bare or marked symbol that is resolved after statement context is known."""

    name: str
    variable: bool = False


@dataclass(frozen=True)
class PredicateRef:
    """A predicate reference, optionally in variable predicate position."""

    name: str
    variable: bool = False


@dataclass(frozen=True)
class AtomNode:
    """An atom before names have been resolved into variables or constants."""

    predicate: PredicateRef
    arguments: tuple[Any, ...]


@dataclass(frozen=True)
class UnaryNode:
    """A unary connective before lowering."""

    operator: str
    operand: Any


@dataclass(frozen=True)
class BinaryNode:
    """A binary connective or operator before lowering."""

    operator: str
    left: Any
    right: Any


@dataclass(frozen=True)
class QuantifierNode:
    """An explicitly quantified sentence before lowering."""

    quantifier: str
    variables: tuple[Variable, ...]
    sentence: Any


@dataclass(frozen=True)
class ConstraintNode:
    """A constraint of the form `:- body` before lowering."""

    body: Any


@dataclass(frozen=True)
class ThatNode:
    """A quoted sentence before lowering."""

    sentence: Any


@dataclass(frozen=True)
class PredicateArityDecl:
    """A predicate declaration that gives only arity."""

    name: str
    arity: int


@dataclass(frozen=True)
class PredicateSignatureDecl:
    """A predicate declaration with named typed arguments."""

    name: str
    arguments: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class TypeDecl:
    """A type declaration."""

    name: str
    base: str = "str"


@dataclass(frozen=True)
class StatementNode:
    """A parsed statement plus comments that should annotate it."""

    comments: tuple[str, ...]
    body: Any


class _TreeToNodes(Transformer):
    """Convert Lark parse trees into a small intermediate AST."""

    def statement(self, items: list[Any]) -> StatementNode:
        comments = tuple(item for item in items[:-1] if isinstance(item, str))
        return StatementNode(comments=comments, body=items[-1])

    def doc_comment(self, items: list[Any]) -> str:
        token = str(items[0])
        return token[3:].strip()

    def type_expr(self, items: list[Any]) -> str:
        return str(items[0])

    def type_decl(self, items: list[Any]) -> TypeDecl:
        name = str(items[1])
        base = str(items[2]) if len(items) > 2 else "str"
        return TypeDecl(name, base)

    def predicate_arity_decl(self, items: list[Any]) -> PredicateArityDecl:
        return PredicateArityDecl(str(items[1]), int(str(items[2])))

    def predicate_signature_decl(self, items: list[Any]) -> PredicateSignatureDecl:
        arguments = tuple(items[2]) if len(items) > 2 and isinstance(items[2], list) else ()
        return PredicateSignatureDecl(str(items[1]), arguments)

    def predicate_arg_list(self, items: list[Any]) -> list[tuple[str, str]]:
        return list(items)

    def predicate_arg(self, items: list[Any]) -> tuple[str, str]:
        return str(items[0]), str(items[1])

    def bare_var_name(self, items: list[Any]) -> str:
        return str(items[0])

    def marked_var_name(self, items: list[Any]) -> str:
        return str(items[0])[1:]

    def var_decl(self, items: list[Any]) -> Variable:
        domain = str(items[1]) if len(items) > 1 else None
        return Variable(str(items[0]), domain)

    def var_decl_list(self, items: list[Any]) -> tuple[Variable, ...]:
        return tuple(items)

    def forall(self, items: list[Any]) -> QuantifierNode:
        return QuantifierNode("forall", tuple(items[1]), items[2])

    def exists(self, items: list[Any]) -> QuantifierNode:
        return QuantifierNode("exists", tuple(items[1]), items[2])

    def constraint(self, items: list[Any]) -> ConstraintNode:
        return ConstraintNode(items[1])

    def implies(self, items: list[Any]) -> BinaryNode:
        return BinaryNode("implies", items[0], items[2])

    def implied(self, items: list[Any]) -> BinaryNode:
        return BinaryNode("implies", items[2], items[0])

    def rule(self, items: list[Any]) -> BinaryNode:
        return BinaryNode("implies", items[2], items[0])

    def iff(self, items: list[Any]) -> BinaryNode:
        return BinaryNode("iff", items[0], items[2])

    def or_(self, items: list[Any]) -> BinaryNode:
        return BinaryNode("or", items[0], items[1])

    def and_(self, items: list[Any]) -> BinaryNode:
        return BinaryNode("and", items[0], items[1])

    def naf(self, items: list[Any]) -> UnaryNode:
        return UnaryNode("naf", items[1])

    def strict_not(self, items: list[Any]) -> UnaryNode:
        return UnaryNode("not", items[0])

    def eq(self, items: list[Any]) -> Term:
        return Term("eq", items[0], items[1])

    def ne(self, items: list[Any]) -> Term:
        return Term("ne", items[0], items[1])

    def le(self, items: list[Any]) -> Term:
        return Term("le", items[0], items[1])

    def lt(self, items: list[Any]) -> Term:
        return Term("lt", items[0], items[1])

    def ge(self, items: list[Any]) -> Term:
        return Term("ge", items[0], items[1])

    def gt(self, items: list[Any]) -> Term:
        return Term("gt", items[0], items[1])

    def add(self, items: list[Any]) -> Term:
        return Term("add", items[0], items[1])

    def sub(self, items: list[Any]) -> Term:
        return Term("sub", items[0], items[1])

    def mul(self, items: list[Any]) -> Term:
        return Term("mul", items[0], items[1])

    def truediv(self, items: list[Any]) -> Term:
        return Term("truediv", items[0], items[1])

    def pow(self, items: list[Any]) -> Term:
        return Term("pow", items[0], items[1])

    def predicate_name(self, items: list[Any]) -> PredicateRef:
        return PredicateRef(str(items[0]))

    def predicate_keyword_name(self, items: list[Any]) -> PredicateRef:
        return PredicateRef(str(items[0]))

    def hilog_predicate_name(self, items: list[Any]) -> PredicateRef:
        return PredicateRef(str(items[0])[1:], variable=True)

    def hilog_marked_predicate_name(self, items: list[Any]) -> PredicateRef:
        return PredicateRef(str(items[0])[1:], variable=True)

    def arg_list(self, items: list[Any]) -> tuple[Any, ...]:
        return tuple(items)

    def atom(self, items: list[Any]) -> AtomNode:
        predicate = items[0]
        arguments = ()
        if len(items) > 1:
            arguments = tuple(items[1])
        return AtomNode(predicate, arguments)

    def quoted_sentence(self, items: list[Any]) -> ThatNode:
        return ThatNode(items[-1])

    def marked_variable(self, items: list[Any]) -> NameRef:
        return NameRef(str(items[0])[1:], variable=True)

    def bare_name(self, items: list[Any]) -> NameRef:
        return NameRef(str(items[0]))

    def number(self, items: list[Any]) -> Union[int, float]:
        raw = str(items[0])
        if "." in raw:
            return float(raw)
        return int(raw)

    def string(self, items: list[Any]) -> str:
        raw = str(items[0])
        return bytes(raw[1:-1], "utf-8").decode("unicode_escape")

    def true(self, items: list[Any]) -> bool:
        return True

    def false(self, items: list[Any]) -> bool:
        return False


class TLogParser(Parser):
    """Parse ergonomic TypedLogic rules into the core datamodel."""

    default_suffix = "tlog"

    def __init__(self, implicit_universal: bool = True, **kwargs: Any):
        """
        Create a parser.

        :param implicit_universal: Wrap unquantified rules containing variables in `Forall`.
        :param kwargs: Forwarded to the base parser.
        """
        super().__init__(**kwargs)
        self.implicit_universal = implicit_universal
        self._parser = Lark(GRAMMAR, parser="lalr", propagate_positions=True, maybe_placeholders=False)

    def parse(self, source: Union[Path, str, TextIO], **kwargs: Any) -> Theory:
        """Parse a TLog source into a theory."""
        text = self._read_source(source)
        tree = self._parser.parse(text)
        statement_nodes = _TreeToNodes().transform(tree)
        theory = Theory()
        for statement in statement_nodes.children:
            self._add_statement(theory, statement)
        return theory

    def validate_iter(self, source: Union[Path, str, TextIO], **kwargs: Any) -> Iterable[ValidationMessage]:
        """Validate source syntax."""
        try:
            self.parse(source, **kwargs)
        except (LarkError, ValueError) as e:
            yield ValidationMessage(message=str(e))

    def _read_source(self, source: Union[Path, str, TextIO]) -> str:
        if isinstance(source, Path):
            return source.read_text(encoding="utf-8")
        if hasattr(source, "read"):
            return source.read()
        return str(source)

    def _add_statement(self, theory: Theory, statement: StatementNode) -> None:
        body = statement.body
        if isinstance(body, TypeDecl):
            theory.type_definitions[body.name] = body.base
            return
        if isinstance(body, PredicateArityDecl):
            theory.predicate_definitions.append(
                PredicateDefinition(body.name, {f"arg{i}": "str" for i in range(body.arity)})
            )
            return
        if isinstance(body, PredicateSignatureDecl):
            theory.predicate_definitions.append(PredicateDefinition(body.name, dict(body.arguments)))
            return

        sentence = self._lower_statement(body)
        if self._add_meta_statement(theory, sentence, statement.comments):
            return
        if statement.comments:
            sentence.add_annotation("comment", "\n".join(statement.comments))
        theory.add(sentence)

    def _add_meta_statement(self, theory: Theory, sentence: Sentence, comments: tuple[str, ...]) -> bool:
        """Add top-level quoted meta statements as sentence groups."""
        if not isinstance(sentence, Term):
            return False
        if sentence.predicate == "lemma":
            name, quoted = self._named_quoted_sentence(sentence, "lemma")
            theory.sentence_groups.append(
                SentenceGroup(
                    name=name,
                    group_type=SentenceGroupType.LEMMA,
                    docstring="\n".join(comments) or None,
                    sentences=[quoted],
                )
            )
            return True
        if sentence.predicate == "test_case":
            name = str(sentence.values[0]) if sentence.values else "test_case"
            theory.sentence_groups.append(
                SentenceGroup(
                    name=name,
                    group_type=SentenceGroupType.TEST,
                    docstring="\n".join(comments) or None,
                    sentences=[sentence],
                )
            )
            return True
        return False

    def _named_quoted_sentence(self, sentence: Term, predicate: str) -> tuple[str, Sentence]:
        """Return the name and quoted sentence from a meta term."""
        if len(sentence.values) != 2:
            raise ValueError(f"{predicate} expects a name and that(sentence): {sentence}")
        name, quoted = sentence.values
        inner = self._quoted_sentence_value(quoted)
        return str(name), inner

    def _quoted_sentence_value(self, value: Any) -> Sentence:
        """Return the sentence wrapped by a that(...) term."""
        if not isinstance(value, Term) or value.predicate != "that" or len(value.values) != 1:
            raise ValueError(f"Expected that(sentence), got {value}")
        quoted = value.values[0]
        if not isinstance(quoted, Sentence):
            raise ValueError(f"Expected quoted sentence, got {quoted}")
        return quoted

    def _lower_statement(self, node: Any) -> Sentence:
        explicit_vars = self._explicit_vars(node)
        rule_like = bool(explicit_vars) or self._is_rule_like(node)
        sentence = self._lower(node, explicit_vars, bare_names_as_variables=rule_like)
        if explicit_vars:
            return sentence
        variables = self._sentence_variables(sentence)
        if self.implicit_universal and variables and rule_like:
            return Forall(variables, sentence)
        return sentence

    def _lower(self, node: Any, bound_vars: dict[str, Variable], bare_names_as_variables: bool) -> Any:
        if isinstance(node, QuantifierNode):
            local_vars = {**bound_vars, **{v.name: v for v in node.variables}}
            sentence = self._lower(node.sentence, local_vars, bare_names_as_variables=False)
            if node.quantifier == "forall":
                return Forall(list(node.variables), sentence)
            return Exists(list(node.variables), sentence)
        if isinstance(node, ConstraintNode):
            return Implies(self._lower(node.body, bound_vars, bare_names_as_variables), Or())
        if isinstance(node, UnaryNode):
            operand = self._lower(node.operand, bound_vars, bare_names_as_variables)
            if node.operator == "naf":
                return NegationAsFailure(operand)
            return Not(operand)
        if isinstance(node, ThatNode):
            return Term("that", self._lower_statement(node.sentence))
        if isinstance(node, BinaryNode):
            left = self._lower(node.left, bound_vars, bare_names_as_variables)
            right = self._lower(node.right, bound_vars, bare_names_as_variables)
            if node.operator == "and":
                return And(left, right)
            if node.operator == "or":
                return Or(left, right)
            if node.operator == "implies":
                return Implies(left, right)
            if node.operator == "iff":
                return Iff(left, right)
            raise ValueError(f"Unknown operator: {node.operator}")
        if isinstance(node, AtomNode):
            predicate: Union[str, Variable] = node.predicate.name
            if node.predicate.variable:
                predicate = bound_vars.get(node.predicate.name, Variable(node.predicate.name))
            args = [self._lower(arg, bound_vars, bare_names_as_variables) for arg in node.arguments]
            return Term(predicate, *args)
        if isinstance(node, Term):
            args = [self._lower(arg, bound_vars, bare_names_as_variables) for arg in node.values]
            return Term(node.predicate, *args)
        if isinstance(node, NameRef):
            if node.variable:
                return bound_vars.get(node.name, Variable(node.name))
            if node.name in bound_vars:
                return bound_vars[node.name]
            if bare_names_as_variables:
                return Variable(node.name)
            return node.name
        if isinstance(node, bool):
            return And() if node else Or()
        return node

    def _explicit_vars(self, node: Any) -> dict[str, Variable]:
        if isinstance(node, QuantifierNode):
            return {v.name: v for v in node.variables}
        return {}

    def _is_rule_like(self, node: Any) -> bool:
        if isinstance(node, (ConstraintNode, QuantifierNode)):
            return True
        if isinstance(node, BinaryNode):
            if node.operator in {"implies", "iff"}:
                return True
            return self._is_rule_like(node.left) or self._is_rule_like(node.right)
        if isinstance(node, UnaryNode):
            return self._is_rule_like(node.operand)
        return False

    def _sentence_variables(self, sentence: Any) -> list[Variable]:
        variables: list[Variable] = []
        seen: set[str] = set()

        def visit(value: Any) -> None:
            if isinstance(value, Variable):
                if value.name not in seen:
                    seen.add(value.name)
                    variables.append(value)
                return
            if isinstance(value, Term):
                if value.predicate == "that":
                    return
                if isinstance(value.predicate, Variable):
                    visit(value.predicate)
                for arg in value.values:
                    visit(arg)
                return
            if isinstance(value, (Forall, Exists)):
                for var in value.variables:
                    seen.add(var.name)
                visit(value.sentence)
                return
            if isinstance(value, (And, Or, Not, NegationAsFailure, Implies, Iff)):
                for operand in value.operands:
                    visit(operand)

        visit(sentence)
        return variables


class TLogMarkdownParser(TLogParser):
    """Parse TLog blocks embedded in Markdown prose."""

    default_suffix = "tlog.md"
    code_block_languages = frozenset({"tlog", "typedlogic", "logic"})

    def parse(self, source: Union[Path, str, TextIO], **kwargs: Any) -> Theory:
        """Parse fenced TLog code blocks from Markdown into a theory."""
        text = self._read_source(source)
        return super().parse(self._extract_tlog_blocks(text), **kwargs)

    def _extract_tlog_blocks(self, text: str) -> str:
        blocks: list[str] = []
        block_lines: list[str] = []
        in_block = False
        collecting = False
        fence = ""

        for line in text.splitlines():
            stripped = line.strip()
            if not in_block and self._starts_fence(stripped):
                fence = stripped[:3]
                language = stripped[3:].strip().split(maxsplit=1)[0].lower()
                collecting = language in self.code_block_languages
                in_block = True
                block_lines = []
                continue
            if in_block and stripped.startswith(fence):
                if collecting:
                    blocks.append("\n".join(block_lines))
                in_block = False
                collecting = False
                fence = ""
                block_lines = []
                continue
            if collecting:
                block_lines.append(line)

        if in_block and collecting:
            blocks.append("\n".join(block_lines))

        return "\n\n".join(blocks)

    def _starts_fence(self, stripped: str) -> bool:
        return stripped.startswith("```") or stripped.startswith("~~~")
