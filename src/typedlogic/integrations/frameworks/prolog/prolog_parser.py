from pathlib import Path
from typing import Union, TextIO, List

from typedlogic import Theory, Sentence, Term, And, Or, Implies
from typedlogic.integrations.frameworks.prolog.basic_prolog import BasicPrologParser
import typedlogic.integrations.frameworks.prolog.basic_prolog as pl
from typedlogic.parser import Parser


class PrologParser(Parser):
    """
    A parser for Prolog source code.
    """

    default_suffix = "pro"

    def parse(self, source: Union[Path, str, TextIO], **kwargs) -> Theory:
        """
        Parse a Prolog source file and return a Theory object.

        :param source:
        :param kwargs:
        :return:
        """
        bpp = BasicPrologParser()
        if isinstance(source, Path):
            with open(source, "r") as f:
                source = f.read()
        elif isinstance(source, str):
            pass
        else:
            source = source.read()
        clauses = bpp.parse_program(source)
        theory = Theory()
        for clause in clauses:
            if isinstance(clause, pl.Rule):
                sentence = self.rule_to_sentence(clause)
                theory.add(sentence)
            elif isinstance(clause, pl.Comment):
                pass
            else:
                raise ValueError(f"Expected Rule, got {clause}")

        return theory

    def rule_to_sentence(self, rule: pl.Rule) -> Sentence:
        """
        Convert a Prolog rule to a Sentence.

        :param rule:
        :return:
        """

        def atom_to_term(atom: Union[pl.Atom, pl.Conjunction]):
            if not isinstance(atom, pl.Atom):
                raise ValueError(f"Expected Atom, got {atom}")
            return Term(atom.predicate, *atom.terms)

        head = atom_to_term(rule.head)
        if rule.body:
            body: Union[Term, And, Or]
            cnjs: List[And] = []
            for cnj_pl in rule.body.conjunctions:
                cnj = And(*[atom_to_term(a) for a in cnj_pl.atoms])
                cnjs.append(cnj)
            if len(cnjs) == 1:
                body = cnjs[0]
            else:
                body = Or(*cnjs)
            return Implies(body, head)
        else:
            return head
