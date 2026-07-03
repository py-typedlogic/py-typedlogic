"""Compiler for TypedLogic's ergonomic text rule syntax."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Optional, Union

from typedlogic import And, Exists, Forall, Iff, Implies, NegationAsFailure, Not, Or, Term, Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import PredicateDefinition, Sentence, SentenceGroup, SentenceGroupType, Variable
from typedlogic.parsers.tlog_parser import TLogParser


@dataclass
class TLogCompiler(Compiler):
    """Compile a theory into TLog syntax."""

    default_suffix: ClassVar[str] = "tlog"
    parser_class: ClassVar[type[TLogParser]] = TLogParser

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs: Any) -> str:
        """Compile a Theory object into TLog syntax."""
        lines: list[str] = []
        for name, base in theory.type_definitions.items():
            lines.append(f"type {name}: {base}.")
        if theory.type_definitions and theory.predicate_definitions:
            lines.append("")

        for predicate_definition in theory.predicate_definitions:
            lines.append(self._predicate_definition(predicate_definition))
        if theory.predicate_definitions and (theory.sentence_groups or theory.ground_terms):
            lines.append("")

        for sentence_group in theory.sentence_groups:
            if sentence_group.docstring:
                for line in sentence_group.docstring.splitlines():
                    lines.append(f"# {line}")
            if sentence_group.group_type == SentenceGroupType.LEMMA:
                lines.extend(self._lemma_lines(sentence_group))
                continue
            for sentence in sentence_group.sentences or []:
                lines.extend(self._sentence_lines(sentence))

        if theory.ground_terms:
            if lines and lines[-1] != "":
                lines.append("")
            for term in theory.ground_terms:
                lines.extend(self._sentence_lines(term))

        return "\n".join(lines)

    def _predicate_definition(self, predicate_definition: PredicateDefinition) -> str:
        arguments = ", ".join(
            f"{name}: {self._type_expr(type_name)}" for name, type_name in predicate_definition.arguments.items()
        )
        return f"pred {predicate_definition.predicate}({arguments})."

    def _sentence_lines(self, sentence: Sentence) -> list[str]:
        lines: list[str] = []
        comment = sentence.annotations.get("comment")
        if comment:
            for line in str(comment).splitlines():
                lines.append(f"/// {line}")
        lines.append(f"{self._sentence(sentence)}.")
        return lines

    def _lemma_lines(self, sentence_group: SentenceGroup) -> list[str]:
        return [
            f"{self._term(Term('lemma', sentence_group.name, Term('that', sentence)))}."
            for sentence in sentence_group.sentences or []
        ]

    def _sentence(self, sentence: Any, parenthesize: bool = False) -> str:
        if isinstance(sentence, Forall):
            result = f"all {self._variables(sentence.variables)} | {self._sentence(sentence.sentence)}"
        elif isinstance(sentence, Exists):
            result = f"exists {self._variables(sentence.variables)} | {self._sentence(sentence.sentence)}"
        elif isinstance(sentence, Implies):
            result = self._implication(sentence)
        elif isinstance(sentence, Iff):
            result = f"{self._sentence(sentence.left, True)} <-> {self._sentence(sentence.right, True)}"
        elif isinstance(sentence, And):
            result = self._boolean_sentence(sentence, " & ", "true")
        elif isinstance(sentence, Or):
            result = self._boolean_sentence(sentence, " | ", "false")
        elif isinstance(sentence, Not):
            result = f"~{self._sentence(sentence.negated, True)}"
        elif isinstance(sentence, NegationAsFailure):
            result = f"not {self._sentence(sentence.negated, True)}"
        elif isinstance(sentence, Term):
            result = self._term(sentence)
        elif isinstance(sentence, Variable):
            result = sentence.name
        else:
            result = self._value(sentence)

        if parenthesize and isinstance(sentence, (Forall, Exists, Implies, Iff, And, Or)):
            return f"({result})"
        return result

    def _implication(self, sentence: Implies) -> str:
        antecedent = self._sentence(sentence.antecedent, True)
        if isinstance(sentence.consequent, Or) and not sentence.consequent.operands:
            return f":- {antecedent}"
        consequent = self._sentence(sentence.consequent, True)
        return f"{consequent} :- {antecedent}"

    def _boolean_sentence(self, sentence: And | Or, separator: str, identity: str) -> str:
        if not sentence.operands:
            return identity
        return separator.join(self._sentence(op, True) for op in sentence.operands)

    def _term(self, term: Term) -> str:
        if term.predicate == "that" and len(term.values) == 1 and isinstance(term.values[0], Sentence):
            return f"that({self._sentence(term.values[0])})"

        operator = {
            "eq": "=",
            "ne": "!=",
            "lt": "<",
            "le": "<=",
            "gt": ">",
            "ge": ">=",
            "add": "+",
            "sub": "-",
            "mul": "*",
            "truediv": "/",
            "pow": "**",
        }.get(str(term.predicate))
        if operator and len(term.values) == 2:
            return f"{self._argument(term.values[0])} {operator} {self._argument(term.values[1])}"

        predicate = term.predicate
        if isinstance(predicate, Variable):
            predicate_name = f"@{predicate.name}"
        else:
            predicate_name = str(predicate)
        return f"{predicate_name}({', '.join(self._argument(value) for value in term.values)})"

    def _argument(self, value: Any) -> str:
        if isinstance(value, Sentence):
            return self._sentence(value, True)
        if isinstance(value, Variable):
            return value.name
        return self._value(value)

    def _value(self, value: Any) -> str:
        if isinstance(value, str):
            return repr(value)
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _variables(self, variables: list[Variable]) -> str:
        return ", ".join(f"{var.name}: {var.domain}" if var.domain else var.name for var in variables)

    def _type_expr(self, type_name: Any) -> str:
        return str(type_name)
