from dataclasses import dataclass
from typing import List, Union, Optional
import re


@dataclass
class Atom:
    """
    Represents a Prolog atom (fact or predicate).

    >>> atom = Atom("parent", ["john", "mary"])
    >>> str(atom)
    'parent(john, mary)'
    """

    predicate: str
    terms: List[Union[str, int]]

    def __str__(self):
        if not self.terms:
            return self.predicate
        terms_str = ", ".join(str(term) for term in self.terms)
        return f"{self.predicate}({terms_str})"


@dataclass
class Conjunction:
    """
    Represents a conjunction of atoms (connected by ',').

    >>> conj = Conjunction([Atom("parent", ["X", "Y"]), Atom("age", ["Y", 42])])
    >>> str(conj)
    '(parent(X, Y), age(Y, 42))'
    """

    atoms: List[Union["Atom", "Conjunction"]]

    def __str__(self):
        if len(self.atoms) == 1:
            return str(self.atoms[0])
        atoms_str = ", ".join(str(atom) for atom in self.atoms)
        return f"({atoms_str})"


@dataclass
class Disjunction:
    """
    Represents a disjunction of conjunctions (connected by ';').

    >>> disj = Disjunction([
    ...     Conjunction([Atom("parent", ["X", "Y"])]),
    ...     Conjunction([Atom("guardian", ["X", "Y"])])
    ... ])
    >>> str(disj)
    'parent(X, Y); guardian(X, Y)'
    """

    conjunctions: List[Conjunction]

    def __str__(self):
        return "; ".join(str(conj) for conj in self.conjunctions)


@dataclass
class Rule:
    """
    Represents a Prolog rule with a head and a disjunctive body.

    >>> head = Atom("ancestor", ["X", "Y"])
    >>> body = Disjunction([
    ...     Conjunction([Atom("parent", ["X", "Y"])]),
    ...     Conjunction([Atom("parent", ["X", "Z"]), Atom("ancestor", ["Z", "Y"])])
    ... ])
    >>> rule = Rule(head, body)
    >>> str(rule)
    'ancestor(X, Y) :- parent(X, Y); (parent(X, Z), ancestor(Z, Y))'
    """

    head: Atom
    body: Optional[Disjunction]

    def __str__(self):
        if not self.body:
            return f"{self.head}."
        return f"{self.head} :- {self.body}"


@dataclass
class Query:
    """
    Represents a Prolog query.

    >>> query = Query(Conjunction([Atom("parent", ["john", "X"])]))
    >>> str(query)
    '?- parent(john, X)'
    """

    body: Conjunction

    def __str__(self):
        return f"?- {self.body}"


class BasicPrologParser:
    """
    Parser for Prolog/Datalog with support for disjunctions and nested conjunctions.

    Basic fact:
    >>> parser = BasicPrologParser()
    >>> parser.parse("parent(john, mary).")
    Rule(head=Atom(predicate='parent', terms=['john', 'mary']), body=None)

    Simple disjunctive rule:
    >>> print(parser.parse("ancestor(X, Y) :- parent(X, Y); grandparent(X, Y)."))
    ancestor(X, Y) :- parent(X, Y); grandparent(X, Y)

    Rule with nested conjunction:
    >>> print(parser.parse("ancestor(X, Y) :- parent(X, Y); (parent(X, Z), ancestor(Z, Y))."))
    ancestor(X, Y) :- parent(X, Y); (parent(X, Z), ancestor(Z, Y))

    Complex rule with multiple nestings:
    >>> print(parser.parse("a(X) :- b(X); (c(X), d(X)); (e(X), (f(X), g(X)))."))
    a(X) :- b(X); (c(X), d(X)); (e(X), (f(X), g(X)))

    Query with conjunction:
    >>> print(parser.parse("?- parent(X, Y), ancestor(Y, Z)."))
    ?- (parent(X, Y), ancestor(Y, Z))
    """

    def __init__(self):
        self.token_patterns = [
            ("ATOM", r"[a-z][a-zA-Z0-9_]*"),
            ("VAR", r"[A-Z][a-zA-Z0-9_]*"),
            ("NUM", r"\d+"),
            ("LP", r"\("),
            ("RP", r"\)"),
            ("COMMA", r","),
            ("SEMI", r";"),
            ("DOT", r"\."),
            ("IF", r":-"),
            ("QUERY", r"\?-"),
            ("WHITESPACE", r"\s+"),
        ]
        self.token_regex = "|".join(f"(?P<{name}>{pattern})" for name, pattern in self.token_patterns)
        self.token_re = re.compile(self.token_regex)

    def tokenize(self, text: str) -> List[tuple]:
        """
        Convert input text into a list of tokens.

        >>> parser = BasicPrologParser()
        >>> parser.tokenize("a(X) :- b(X); (c(X), d(X)).")
        [('ATOM', 'a'), ('LP', '('), ('VAR', 'X'), ('RP', ')'), ('IF', ':-'), ('ATOM', 'b'), ('LP', '('), ('VAR', 'X'), ('RP', ')'), ('SEMI', ';'), ('LP', '('), ('ATOM', 'c'), ('LP', '('), ('VAR', 'X'), ('RP', ')'), ('COMMA', ','), ('ATOM', 'd'), ('LP', '('), ('VAR', 'X'), ('RP', ')'), ('RP', ')'), ('DOT', '.')]
        """
        pos = 0
        tokens = []
        while pos < len(text):
            match = self.token_re.match(text, pos)
            if match is None:
                raise SyntaxError(f"Invalid token at position {pos}")

            token_type = match.lastgroup
            token_value = match.group()
            if token_type != "WHITESPACE":
                tokens.append((token_type, token_value))
            pos = match.end()
        return tokens

    def parse_term(self, tokens: List[tuple], pos: int) -> tuple[Union[str, int], int]:
        """Parse a single term (variable, atom, or number)."""
        if pos >= len(tokens):
            raise SyntaxError("Unexpected end of input while parsing term")

        token_type, token_value = tokens[pos]
        if token_type in ("ATOM", "VAR"):
            return token_value, pos + 1
        elif token_type == "NUM":
            return int(token_value), pos + 1
        else:
            raise SyntaxError(f"Expected term, got {token_type}")

    def parse_atom(self, tokens: List[tuple], pos: int) -> tuple[Atom, int]:
        """Parse a predicate with its arguments."""
        if pos >= len(tokens):
            raise SyntaxError("Unexpected end of input while parsing atom")

        token_type, token_value = tokens[pos]
        if token_type != "ATOM":
            raise SyntaxError(f"Expected predicate, got {token_type}")

        predicate = token_value
        pos += 1
        terms = []

        if pos < len(tokens) and tokens[pos][0] == "LP":
            pos += 1
            while True:
                term, pos = self.parse_term(tokens, pos)
                terms.append(term)

                if pos >= len(tokens):
                    raise SyntaxError("Unexpected end of input while parsing atom arguments")

                if tokens[pos][0] == "RP":
                    pos += 1
                    break
                elif tokens[pos][0] != "COMMA":
                    raise SyntaxError(f"Expected ',' or ')', got {tokens[pos][0]}")
                pos += 1

        return Atom(predicate, terms), pos

    def parse_conjunction(self, tokens: List[tuple], pos: int) -> tuple[Conjunction, int]:
        """Parse a conjunction of atoms or nested conjunctions."""
        operands: List[Union[Atom, Conjunction]] = []

        # Handle opening parenthesis
        has_parens = pos < len(tokens) and tokens[pos][0] == "LP"
        if has_parens:
            pos += 1

        while True:
            if pos >= len(tokens):
                raise SyntaxError("Unexpected end of input while parsing conjunction")

            # Handle nested conjunction
            if tokens[pos][0] == "LP":
                conj, pos = self.parse_conjunction(tokens, pos)
                operands.append(conj)
            else:
                atom, pos = self.parse_atom(tokens, pos)
                operands.append(atom)

            if pos >= len(tokens):
                raise SyntaxError("Unexpected end of input while parsing conjunction")

            # Handle closing parenthesis or end of conjunction
            if has_parens and tokens[pos][0] == "RP":
                pos += 1
                break
            elif not has_parens and tokens[pos][0] in ("DOT", "SEMI", "RP"):
                break
            elif tokens[pos][0] != "COMMA":
                raise SyntaxError(f"Expected ',', ';', ')', or '.', got {tokens[pos][0]}")
            pos += 1

        return Conjunction(operands), pos

    def parse_disjunction(self, tokens: List[tuple], pos: int) -> tuple[Disjunction, int]:
        """Parse a disjunction of conjunctions."""
        conjunctions = []

        while True:
            conj, pos = self.parse_conjunction(tokens, pos)
            conjunctions.append(conj)

            if pos >= len(tokens) or tokens[pos][0] in ("DOT", "RP"):
                break
            elif tokens[pos][0] != "SEMI":
                raise SyntaxError(f"Expected ';', ')', or '.', got {tokens[pos][0]}")
            pos += 1

        return Disjunction(conjunctions), pos

    def parse_rule(self, tokens: List[tuple], pos: int) -> tuple[Rule, int]:
        """Parse a rule (fact or rule with body)."""
        head, pos = self.parse_atom(tokens, pos)

        if pos >= len(tokens):
            raise SyntaxError("Unexpected end of input while parsing rule")

        if tokens[pos][0] == "IF":
            pos += 1
            body, pos = self.parse_disjunction(tokens, pos)
        else:
            body = None

        if pos >= len(tokens) or tokens[pos][0] != "DOT":
            raise SyntaxError("Expected '.' at end of rule")
        pos += 1

        return Rule(head, body), pos

    def parse_query(self, tokens: List[tuple], pos: int) -> tuple[Query, int]:
        """Parse a query."""
        if pos >= len(tokens) or tokens[pos][0] != "QUERY":
            raise SyntaxError("Expected '?-' at start of query")
        pos += 1

        body, pos = self.parse_conjunction(tokens, pos)

        if pos >= len(tokens) or tokens[pos][0] != "DOT":
            raise SyntaxError("Expected '.' at end of query")
        pos += 1

        return Query(body), pos

    def parse(self, text: str) -> Union[Rule, Query]:
        """
        Parse a Prolog/Datalog expression.
        See class docstring for examples.
        """
        tokens = self.tokenize(text)
        if not tokens:
            raise SyntaxError("Empty input")

        result: Union[Rule, Query]
        if tokens[0][0] == "QUERY":
            result, pos = self.parse_query(tokens, 0)
        else:
            result, pos = self.parse_rule(tokens, 0)

        if pos < len(tokens):
            raise SyntaxError("Unexpected tokens after parsing")

        return result
