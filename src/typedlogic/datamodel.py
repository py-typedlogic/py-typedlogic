"""
Data model for the typed-logic framework.

## Overview

This module defines the core classes and structures used to represent logical
constructs such as sentences, terms, predicates, and theories. It is based
on the Common Logic Interchange Format (CLIF) and the Common Logic Standard (CL),
with additions to make working with simple type systems easier.

Logical axioms are called [sentences](#typedlogic.datamodel.Sentence) which organized into [theories](#typedlogic.datamodel.Theory).,
 which can be loaded into a [solver](/integrations/solvers).

 While one of the goals of typed-logic is to be able to write logic intuitively in Python,
 this data model is independent of the mapping from the Python language to the logic language;
 it can be used independently of the python syntax.

Here is an example:

        >>> from typedlogic import Term, Forall, Implies
        >>> x = Variable('x')
        >>> y = Variable('y')
        >>> pdef = PredicateDefinition(predicate='FriendOf',
        ...                          arguments={'x': 'str', 'y': 'str'}),
        >>> theory = Theory(
        ...     name="My theory",
        ...     predicate_definitions=[pdef],
        ... )
        >>> s = Forall([x, y],
        ...            Implies(Term('friend_of', x, y),
        ...                    Term('friend_of', y, x)))
        >>> theory.add(s)

## Classes

"""
import operator
import types
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple, Type, Union, _SpecialForm, get_origin, Iterable, Iterator

SExpressionAtom = Any
SExpressionTerm = List["SExpression"]
SExpression = Union[SExpressionTerm, SExpressionAtom]


@dataclass
class PredicateDefinition:
    """
    Defines the name and arguments of a predicate.

    Example:

        >>> pdef = PredicateDefinition(predicate='FriendOf',
        ...                            arguments={'x': 'str', 'y': 'str'})

    The arguments are mappings between variable names and types.
    You can use either base types (e.g. 'str', 'int', 'float') or custom types.

    Custom types should be defined in the theory's `type_definitions` attribute.

        >>> pdef = PredicateDefinition(predicate='FriendOf',
        ...                            arguments={'x': 'Person', 'y': 'Person'})
        >>> theory = Theory(
        ...     name="My theory",
        ...     type_definitions={'Person': 'str'},
        ...     predicate_definitions=[pdef],
        ... )

    Model:

    ```mermaid
    classDiagram
    class PredicateDefinition {
        +String predicate
        +Dict arguments
        +String description
        +Dict metadata
    }
    PredicateDefinition --> "*" PredicateDefinition : parents
    ```

    """

    predicate: str
    arguments: Dict[str, str]
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    parents: Optional[List[str]] = None
    python_class: Optional[Type] = None

    def argument_base_type(self, arg: str) -> str:
        typ = self.arguments[arg]
        try:
            import pydantic

            if isinstance(typ, pydantic.fields.FieldInfo):
                typ = typ.annotation
        except ImportError:
            pass
        return str(typ)

    @classmethod
    def from_class(cls, python_class: Type) -> "PredicateDefinition":
        """
        Create a predicate definition from a python class

        :param predicate_class:
        :return:
        """
        return PredicateDefinition(
            predicate=python_class.__name__,
            arguments={k: v for k, v in python_class.__annotations__.items()},
        )


@dataclass
class Variable:
    """
    A variable in a logical sentence.

        >>> x = Variable('x')
        >>> y = Variable('y')
        >>> s = Forall([x, y],
        ...            Implies(Term('friend_of', x, y),
        ...                    Term('friend_of', y, x)))

    Variables can have domains (types) specified:

        >>> x = Variable('x', domain='str')
        >>> y = Variable('y', domain='str')
        >>> z = Variable('y', domain='int')
        >>> xa = Variable('xa', domain='int')
        >>> ya = Variable('ya', domain='int')
        >>> s = Forall([x, y, z],
        ...            Implies(And(Term('ParentOf', x, y),
        ...                        Term('Age', x, xa),
        ...                        Term('Age', y, ya)),
        ...                    Term('OlderThan', x, y)))

        The domains should be either base types or defined types in the theory's `type_definitions` attribute.

    """

    name: str
    domain: Optional[str] = None
    constraints: Optional[List[str]] = None

    def __eq__(self, other):
        return isinstance(other, Variable) and self.name == other.name

    def __str__(self):
        return "?" + self.name

    def __hash__(self):
        return hash(self.name)

    def as_sexpr(self) -> SExpression:
        sexpr = [type(self).__name__, self.name]
        if self.domain:
            return sexpr + [self.domain]
        else:
            return sexpr

    @staticmethod
    def create(names: str) -> tuple['Variable', ...]:
        return tuple(Variable(name.strip()) for name in names.split())


class Sentence(ABC):
    """
    Base class for logical sentences.

    Do not use this class directly; use one of the subclasses instead.

    Model:

    ```mermaid
    classDiagram
    Sentence <|-- Term
    Sentence <|-- BooleanSentence
    Sentence <|-- QuantifiedSentence
    Sentence <|-- Extension
    ```


    """

    def __init__(self):
        self._annotations = {}

    def __and__(self, other):
        return And(self, other)

    def __or__(self, other):
        return Or(self, other)

    def __invert__(self):
        return Not(self)

    def __sub__(self):
        return NegationAsFailure(self)

    def __rshift__(self, other):
        return Implies(self, other)

    def __lshift__(self, other):
        return Implied(self, other)

    def __xor__(self, other):
        return Xor(self, other)

    def iff(self, other):
        return Iff(self, other)

    def __lt__(self, other):
        return Term(operator.lt.__name__, self, other)

    def __le__(self, other):
        return Term(operator.le.__name__, self, other)

    def __gt__(self, other):
        return Term(operator.gt.__name__, self, other)

    def __ge__(self, other):
        return Term(operator.ge.__name__, self, other)

    def __add__(self, other):
        return Term(operator.add.__name__, self, other)
    
    def __rmul__(self, other):
        # TODO: avoid circular import
        from typedlogic.extensions.probabilistic import Probability, That
        return Probability(self, That(other))

    @property
    def annotations(self) -> Dict[str, Any]:
        """
        Annotations for the sentence.

        Annotations are always logically silent, but can be used to store metadata or other information.

        :return:
        """
        return self._annotations or {}

    def add_annotation(self, key: str, value: Any):
        """
        Add an annotation to the sentence

        :param key:
        :param value:
        :return:
        """
        if not self._annotations:
            self._annotations = {}
        self._annotations[key] = value

    def as_sexpr(self) -> SExpression:
        raise NotImplementedError(f"type = {type(self)} // {self}")

    @property
    def arguments(self) -> List[Any]:
        raise NotImplementedError(f"type = {type(self)} // {self}")


def as_sexpr(s: Any) -> SExpression:
    if isinstance(s, (Sentence, Variable)):
        return s.as_sexpr()
    if isinstance(s, (Theory, SentenceGroup, PredicateDefinition)):
        sexpr: List[SExpression] = [type(s).__name__]
        for k, v in vars(s).items():
            sexpr.append([k, as_sexpr(v)])
        return sexpr
    if isinstance(s, (list, tuple)):
        return [as_sexpr(x) for x in s]
    if isinstance(s, dict):
        return ["dict", [as_sexpr(x) for x in s.items()]]
    if isinstance(s, Enum):
        return s.value
    if isinstance(s, (type, types.GenericAlias, _SpecialForm)):
        return str(s)
    if hasattr(s, "__origin__") and get_origin(s) is not None:
        return str(s)
    else:
        return s


class Term(Sentence):
    """
    An atomic part of a sentence.

    A ground term is a term with no variables:

        >>> t = Term('FriendOf', 'Alice', 'Bob')
        >>> t
        FriendOf(Alice, Bob)
        >>> t.values
        ('Alice', 'Bob')
        >>> t.is_ground
        True

    Keyword argument based initialization is also supported:

        >>> t = Term('FriendOf', dict(about='Alice', friend='Bob'))
        >>> t.values
        ('Alice', 'Bob')
        >>> t.positional
        False

    Mappings:

     - Corresponds to AtomicSentence in Common Logic
    """

    def __init__(self, predicate: str, *args, **kwargs):
        self.predicate = predicate
        if not args:
            self.positional = None
            bindings = {}
        elif len(args) == 1 and isinstance(args[0], dict):
            bindings = args[0]
            self.positional = False
        else:
            bindings = {f"arg{i}": arg for i, arg in enumerate(args)}
            self.positional = True
        self.bindings = bindings
        self._annotations = kwargs

    @property
    def is_constant(self):
        """
        :return: True if the term is a constant (zero arguments)
        """
        return not self.bindings

    @property
    def is_ground(self):
        """
        :return: True if none of the arguments are variables
        """
        return not any(isinstance(v, Variable) for v in self.bindings.values())

    @property
    def values(self) -> Tuple[Any, ...]:
        """
        Representation of the arguments of the term as a fixed-position tuples
        :return:
        """
        return tuple([v for v in self.bindings.values()])

    @property
    def variables(self) -> List[Variable]:
        """
        :return: All of the arguments that are variables
        """
        return [v for v in self.bindings.values() if isinstance(v, Variable)]

    @property
    def variable_names(self) -> List[str]:
        return [v.name for v in self.bindings.values() if isinstance(v, Variable)]

    def make_keyword_indexed(self, keywords: List[str]):
        """
        Convert positional arguments to keyword arguments
        """
        if self.positional:
            self.bindings = {k: v for k, v in zip(keywords, self.bindings.values(), strict=False)}
            self.positional = False

    def __repr__(self):
        if not self.bindings:
            return f"{self.predicate}"
        elif self.positional:
            return f'{self.predicate}({", ".join(f"{v}" for v in self.bindings.values())})'
        else:
            return f'{self.predicate}({", ".join(f"{v}" for k, v in self.bindings.items())})'

    def __eq__(self, other):
        # return isinstance(other, Term) and self.predicate == other.predicate and self.bindings == other.bindings
        return isinstance(other, Term) and self.predicate == other.predicate and self.values == other.values

    def __hash__(self):
        return hash((self.predicate, tuple(self.values)))

    def as_sexpr(self) -> SExpression:
        return [self.predicate] + [as_sexpr(v) for v in self.bindings.values()]


class TermBag(Sentence):
    """
    A bag of terms.

    Example (using keyword arguments):

        >>> tb = TermBag('Distance', {'start': ['London', 'Paris', 'Tokyo'], 'end': ['Paris', 'Tokyo', 'New York'], 'miles': [344, 9561, 10838]})
        >>> tb
        Distance(London, Paris, 344), Distance(Paris, Tokyo, 9561), Distance(Tokyo, New York, 10838)

    Example (using positional arguments):

        >>> tb = TermBag('Distance', ['London', 'Paris', 'Tokyo'], ['Paris', 'Tokyo', 'New York'], [344, 9561, 10838])
        >>> tb
        Distance(London, Paris, 344), Distance(Paris, Tokyo, 9561), Distance(Tokyo, New York, 10838)

    """

    def __init__(self, predicate: str, *args, **kwargs):
        self.predicate = predicate
        bindings: Dict[str, List[Any]]
        if not args:
            self.positional = None
            bindings = {}
        elif len(args) == 1 and isinstance(args[0], dict):
            bindings = args[0]
            self.positional = False
        else:
            bindings = {f"arg{i}": arg for i, arg in enumerate(args)}
            self.positional = True
        self.bindings = bindings
        self._annotations = kwargs
        self._validate()

    def _validate(self):
        if not self.predicate:
            raise ValueError("No predicate provided")
        if not self.bindings:
            raise ValueError("No bindings provided")
        if not all(isinstance(v, List) for v in self.bindings.values()):
            raise ValueError("All bindings must be collections")

    @property
    def values(self) -> Tuple[List[Any], ...]:
        """
        Representation of the arguments of the term as a fixed-position tuples

        :return:
        """
        return tuple([v for v in self.bindings.values()])

    def make_keyword_indexed(self, keywords: List[str]):
        """
        Convert positional arguments to keyword arguments
        """
        if self.positional:
            self.bindings = {k: v for k, v in zip(keywords, self.bindings.values(), strict=False)}
            self.positional = False
        self._validate()

    def __repr__(self):
        terms = self.as_terms()
        return ", ".join(repr(t) for t in terms)

    def __eq__(self, other):
        # return isinstance(other, Term) and self.predicate == other.predicate and self.bindings == other.bindings
        return isinstance(other, TermBag) and self.predicate == other.predicate and self.values == other.values

    def __hash__(self):
        return hash((self.predicate, tuple(self.values)))

    def as_terms(self) -> List[Term]:
        tuples = zip(*self.values)
        return [Term(self.predicate, *tuple) for tuple in tuples]

    def as_sexpr(self) -> SExpressionTerm:
        return [t.as_sexpr() for t in self.as_terms()]


class Extension(Sentence, ABC):
    """
    Use this abstract class for framework-specific extensions.

    An example of this is the `Fact` class which subclasses Extension, and is intended to be
    subclassed by domain-specific classes representing predicate definitions, whose instances
    map to terms.
    """

    @abstractmethod
    def to_model_object(self) -> Sentence:
        """
        Convert the extension to a standard model object.

        :return:
        """
        pass

    def as_sexpr(self) -> List[Any]:
        return self.to_model_object().as_sexpr()

    @property
    def arguments(self) -> List[Any]:
        return self.to_model_object().arguments


def term(predicate: Union[str, Type[Extension], Extension], *args, **kwargs) -> Term:
    """
    Create a term object.

    :param predicate:
    :param args:
    :param kwargs:
    :return: Term object
    """
    if isinstance(predicate, Extension):
        s = predicate.to_model_object()
        if isinstance(s, Term):
            return s
        else:
            raise ValueError(f"Cannot convert {predicate} to a Term")
    if isinstance(predicate, type):
        predicate = predicate.__name__
    return Term(predicate, *args, **kwargs)


@dataclass
class BooleanSentence(Sentence, ABC):
    """
    Base class for sentences that are boolean expressions

    Corresponds to BooleanSentence in CL

    ```mermaid
    classDiagram
    BooleanSentence <|-- And
    BooleanSentence <|-- Or
    BooleanSentence <|-- Not
    BooleanSentence <|-- Xor
    BooleanSentence <|-- ExactlyOne
    BooleanSentence <|-- Implication
    BooleanSentence <|-- Implied
    BooleanSentence <|-- Iff
    BooleanSentence <|-- NegationAsFailure
    BooleanSentence --> "*" Sentence : operands
    ```

    """

    operands: Tuple[Sentence, ...] = field(default_factory=tuple)
    # operands: Tuple[Union[Sentence, bool], ...] = field(default_factory=tuple)

    def __init__(self, *operands, **kwargs):
        def _as_sentence(s: Union[Sentence, bool]) -> Sentence:
            if isinstance(s, Sentence):
                return s
            elif isinstance(s, bool):
                return And() if s else Or()
            else:
                raise TypeError(f"Expected Sentence or bool, got {type(s)}")
        self.operands = tuple([_as_sentence(s) for s in operands])
        self._annotations = kwargs

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.operands == other.operands

    def as_sexpr(self) -> SExpression:
        return [type(self).__name__] + [as_sexpr(op) for op in self.operands]

    @property
    def arguments(self) -> List[Any]:
        return list(self.operands)


@dataclass
class And(BooleanSentence):
    """
    A conjunction of sentences.

        >>> x = Variable('x')
        >>> y = Variable('y')
        >>> s = And(Term('friend_of', x, y), Term('friend_of', y, x))

    You can also use syntactic sugar:

        >>> s = Term('friend_of', x, y) & Term('friend_of', y, x)

    Note however that precedence rules for `&` are different from `and`.

    In the context of a pylog program, you can also use `and`:

    ```assert FriendOf(x, y) & FriendOf(y, x)```

    As in CL, ``And()`` means True
    """

    def __init__(self, *operands, **kwargs):
        super().__init__(*operands, **kwargs)

    def __str__(self):
        return f'({") & (".join(str(op) for op in self.operands)})'

    def __repr__(self):
        return f'And({", ".join(repr(op) for op in self.operands)})'


@dataclass
class Or(BooleanSentence):
    """
    A disjunction of sentences.

        >>> x = Variable('x')
        >>> y = Variable('y')
        >>> s = Or(Term('friend_of', x, y), Term('friend_of', y, x))
        >>> s.operands[0]
        friend_of(?x, ?y)

    You can also use syntactic sugar:

        >>> s = Term('friend_of', x, y) | Term('friend_of', y, x)

    Note however that precedence rules for `|` are different from `or`.

    In the context of a pylog program, you can also use `or`:

    ```assert FriendOf(x, y) | FriendOf(y, x)```

    As in CL, ``Or()`` means False
    """

    def __init__(self, *operands, **kwargs):
        super().__init__(*operands, **kwargs)

    def __str__(self):
        return f'({") | (".join(str(op) for op in self.operands)})'

    def __repr__(self):
        return f'Or({", ".join(repr(op) for op in self.operands)})'


@dataclass
class Not(BooleanSentence):
    """
    A complement of a sentence

        >>> x = Variable('x')
        >>> y = Variable('y')
        >>> s = Not(Term('friend_of', x, y))
        >>> s.negated
        friend_of(?x, ?y)

    You can also use syntactic sugar:

        >>> s = ~Term('friend_of', x, y)

    In the context of a pylog program, you can also use `not`:

    ```assert not FriendOf(x, y)```

    This SHOULD be interpreted as strict negation, not as failure.
    """

    def __init__(self, operand, **kwargs):
        super().__init__(operand, **kwargs)

    def __str__(self):
        return f"~{self.operands[0]}"

    def __repr__(self):
        return f"Not({repr(self.operands[0])})"

    @property
    def negated(self) -> Sentence:
        """
        The negated sentence
        :return: Sentence
        """
        return self.operands[0]


class Xor(BooleanSentence):
    """
    An exclusive or of sentences
    """

    def __init__(self, left, right, **kwargs):
        super().__init__(left, right, **kwargs)


@dataclass
class ExactlyOne(BooleanSentence):
    """
    Exactly one of the sentences is true

        >>> x = Variable('x')
        >>> s = ExactlyOne(Term('likes', x, "root beer"), Term('likes', x, "marmite"))

    """

    def __init__(self, *operands, **kwargs):
        super().__init__(*operands, **kwargs)

    def __str__(self):
        return f'({") x| (".join(str(op) for op in self.operands)})'

    def __repr__(self):
        return f'ExactlyOne({", ".join(repr(op) for op in self.operands)})'


@dataclass
class Implication(BooleanSentence, ABC):
    """
    An abstract grouping of sentences with an implication operator.

    ```mermaid
    classDiagram
    Implication <|-- Implies
    Implication <|-- Implied
    Implication <|-- Iff
    ```

    """

    def __init__(self, left, right, **kwargs):
        super().__init__(left, right, **kwargs)

    @property
    def symbol(self):
        raise NotImplementedError

    def __str__(self):
        return f"({self.operands[0]} {self.symbol} {self.operands[1]})"

    def __repr__(self):
        return f"{type(self).__name__}({repr(self.operands[0])}, {repr(self.operands[1])})"


@dataclass
class Implies(Implication):
    """
    An if-then implication.

    Corresponds to Implication in CommonLogic

        >>> x = Variable('x')
        >>> s = Iff(Term('likes', x, "root beer"), ~Term('likes', x, "marmite"))

    You can also use syntactic sugar:

        >>> s = Term('likes', x, "root beer") >> ~Term('likes', x, "marmite")

    """

    def __init__(self, antecedent, consequent, **kwargs):
        super().__init__(antecedent, consequent, **kwargs)

    @property
    def symbol(self):
        return "->"

    @property
    def antecedent(self):
        return self.operands[0]

    @property
    def consequent(self):
        return self.operands[1]

    def __str__(self):
        return f"({self.operands[0]} -> {self.operands[1]})"

    def __repr__(self):
        return f"Implies({repr(self.operands[0])}, {repr(self.operands[1])})"


@dataclass
class Implied(Implication):
    """
    An implication of the form consequent <- antecedent

    Inverse of `Implies`
    """

    def __init__(self, consequent, antecedent, **kwargs):
        super().__init__(consequent, antecedent, **kwargs)

    @property
    def symbol(self):
        return "<-"

    @property
    def antecedent(self):
        return self.operands[1]

    @property
    def consequent(self):
        return self.operands[0]

    def __str__(self):
        return f"({self.operands[0]} <- {self.operands[1]})"

    def __repr__(self):
        return f"Implied({repr(self.operands[0])}, {repr(self.operands[1])})"


@dataclass
class Iff(Implication):
    """
    An equivalence of sentences

    Corresponds to Biconditional in CommonLogic.

        >>> x = Variable('x')
        >>> s = Iff(Term('likes', x, "jaffa cakes"), Term('likes', x, "marmite"))

    """

    def __init__(self, left, right, **kwargs):
        super().__init__(left, right, **kwargs)

    @property
    def symbol(self):
        return "<->"

    @property
    def left(self):
        return self.operands[0]

    @property
    def right(self):
        return self.operands[1]

    def __str__(self):
        return f"({self.operands[0]} <-> {self.operands[1]})"

    def __repr__(self):
        return f"Iff({repr(self.operands[0])}, {repr(self.operands[1])})"


@dataclass
class NegationAsFailure(BooleanSentence):
    """
    A negated sentence, interpreted via negation as failure semantics.
    """

    def __init__(self, operand, **kwargs):
        super().__init__(operand, **kwargs)

    def __str__(self):
        return f"NegationAsFailure{self.operands[0]}"

    def __repr__(self):
        return f"NegationAsFailure({repr(self.operands[0])})"

    @property
    def negated(self):
        return self.operands[0]


# deprecate this?
def not_provable(predicate):
    """Function for Negation as Failure"""
    return NegationAsFailure(predicate)


@dataclass
class QuantifiedSentence(Sentence, ABC):
    """
    A sentence with a logical quantifier.

    ```mermaid
    classDiagram
    QuantifiedSentence <|-- Forall
    QuantifiedSentence <|-- Exists
    QuantifiedSentence --> "*" Variable : variables
    ```

    """

    variables: List[Variable]
    sentence: Sentence
    _annotations: Optional[Dict[str, Any]] = None

    @property
    def quantifier(self) -> str:
        raise NotImplementedError

    def _bindings_str(self) -> str:
        return ", ".join(f"{v.name}: {v.domain}" for v in self.variables)

    def __hash__(self):
        return hash((self.quantifier, tuple(self.variables), self.sentence))

    def as_sexpr(self) -> SExpression:
        return [type(self).__name__, [v.as_sexpr() for v in self.variables], self.sentence.as_sexpr()]

    @property
    def arguments(self) -> List[Any]:
        return [self.variables, self.sentence]


@dataclass
class Forall(QuantifiedSentence):
    """
    Universal quantifier.

        >>> x = Variable('x')
        >>> y = Variable('y')
        >>> s = Forall([x, y], Implies(Term('friend_of', x, y), Term('friend_of', y, x)))

    """

    @property
    def quantifier(self) -> str:
        return "all"

    def __str__(self):
        return f"∀{self._bindings_str()} : {self.sentence}"

    def __repr__(self):
        return f"Forall([{self._bindings_str()}] : {repr(self.sentence)})"


@dataclass
class Exists(QuantifiedSentence):
    """
    Existential quantifier.

        >>> x = Variable('x')
        >>> y = Variable('y')
        >>> s = ~Exists([x, y], And(Term('friend_of', x, y), Term('enemy_of', x, y)))

    """

    @property
    def quantifier(self) -> str:
        return "exists"

    def __str__(self):
        return f"∃{self.sentence}"

    def __repr__(self):
        return f"Exists({self._bindings_str()} : {repr(self.sentence)})"

    def __hash__(self):
        return hash((self.quantifier, self._bindings_str(), self.sentence))


@dataclass
class CardinalityConstraint(Term):
    """
    A constraint on the cardinality of a set of terms.

    Example:

        >>> h = Variable("h")
        >>> f = Variable("f")
        >>> hp = Term("has_part", h, f)
        >>> s = Forall([h], CardinalityConstraint(Term("has_part", h, f), Term("has_part", h, f), 5, 5))

    """

    def __init__(self, template: Optional[Sentence], conditions: Sentence, minimum_number: Optional[int] = None, maximum_number: Optional[int] = None):
        """
        Initialize a CardinalityConstraint.

        :param template: The template sentence that defines the terms.
        :param conditions: The conditions that the terms must satisfy.
        :param minimum_number: The minimum number of terms that must satisfy the conditions.
        :param maximum_number: The maximum number of terms that can satisfy the conditions.
        """
        if not template:
            template = conditions
        super().__init__("CardinalityConstraint",
                         dict(template=template, conditions=conditions,
                              minimum_number=minimum_number, maximum_number=maximum_number))

    # TODO: decide on general strategy for extending Terms

    #template: Sentence
    #conditions: Sentence
    #minimum_number: Optional[int] = None
    #maximum_number: Optional[int] = None

    @property
    def template(self):
        return self.bindings.get("template")

    @property
    def conditions(self):
        return self.bindings.get("conditions")

    @property
    def minimum_number(self) -> Optional[int]:
        return self.bindings.get("minimum_number")

    @property
    def maximum_number(self) -> Optional[int]:
        return self.bindings.get("maximum_number")

    def __str__(self):
        return f"{self.minimum_number} <= {{ {self.template} : {self.conditions} }} <= {self.maximum_number}"

    def __repr__(self):
        return f"CardinalityConstraint({self.template}, {self.conditions}, {self.minimum_number}, {self.maximum_number})"

    def __hash__(self):
        return hash((self.template, self.conditions, str(self.maximum_number), str(self.minimum_number)))


class SentenceGroupType(str, Enum):
    AXIOM = "axiom"
    GOAL = "goal"
    # PROBABILISTIC_AXIOM = "probabilistic_axiom"


@dataclass
class SentenceGroup:
    """
    A logical grouping of related sentences with common documentation.

    One way to collect these is via a decorated python function.

    ```mermaid
    classDiagram
    class SentenceGroup {
        +String name
        +SentenceGroupType group_type
        +String docstring
        +Dict annotations
    }
    SentenceGroup --> "*" Sentence : sentences

    """

    name: str
    group_type: Optional[SentenceGroupType] = None
    docstring: Optional[str] = None
    sentences: Optional[List[Sentence]] = None
    _annotations: Optional[Dict[str, Any]] = None


DefinedType = Union["DefinedUnionType", str]
DefinedUnionType = List[DefinedType]


@dataclass
class Theory:
    """
    A collection of predicate definitions and sentences.

    Analogous to a Text in CommonLogic.

    ```mermaid
    classDiagram
    class Theory {
        +String name
        +Dict constants
        +Dict type_definitions
        +List predicate_definitions
        +List sentence_groups
        +List ground_terms
        +Dict annotations
    }
    Theory --> "*" DefinedType : type_definitions
    Theory --> "*" PredicateDefinition : predicate_definitions
    Theory --> "*" Term : ground_terms
    Theory --> "*" SentenceGroup : sentence_groups
    ```

    """

    name: Optional[str] = None
    constants: Dict[str, Any] = field(default_factory=dict)
    type_definitions: Dict[str, DefinedType] = field(default_factory=dict)
    predicate_definitions: List[PredicateDefinition] = field(default_factory=list)
    sentence_groups: List[SentenceGroup] = field(default_factory=list)
    ground_terms: List[Term] = field(default_factory=list)
    _annotations: Optional[Dict[str, Any]] = None
    source_module_name: Optional[str] = None

    @property
    def predicate_definition_map(self) -> Mapping[str, PredicateDefinition]:
        return {pd.predicate: pd for pd in self.predicate_definitions}

    @property
    def sentences(self) -> List[Sentence]:
        """
        Return all sentences in the theory

        :return:
        """
        if self.sentence_groups:
            return [s for sg in self.sentence_groups for s in sg.sentences or []]
        return []

    @property
    def goals(self) -> List[Sentence]:
        """
        Return all goal sentences in the theory

        :return:
        """
        return [
            s
            for sg in self.sentence_groups or []
            if sg.group_type == SentenceGroupType.GOAL
            for s in sg.sentences or []
        ]

    def add(self, sentence: Sentence):
        """
        Add a sentence to the theory

        :param sentence:
        :return:
        """
        if isinstance(sentence, Extension):
            sentence = sentence.to_model_object()
        if isinstance(sentence, TermBag):
            for t in sentence.as_terms():
                self.add(t)
            return
        if not self.sentence_groups:
            self.sentence_groups = []
        self.sentence_groups.append(SentenceGroup(name="Sentences", sentences=[sentence]))

    def extend(self, sentences: Iterable[Sentence]):
        """
        Add a list of sentences to the theory

        :param sentences:
        :return:
        """
        for s in sentences:
            self.add(s)

    def remove(self, sentence: Sentence, strict=False):
        """
        Remove a sentence to the theory

        :param sentence:
        :param strict:
        :return:
        """
        if isinstance(sentence, Extension):
            sentence = sentence.to_model_object()
        if not self.sentence_groups:
            if strict:
                raise ValueError("No sentences to remove from")
            return
        n = 0
        for sg in self.sentence_groups:
            if sg.sentences and sentence in sg.sentences:
                sg.sentences.remove(sentence)
                n += 1
        if n != 1 and strict:
            raise ValueError(f"Removed {n} sentences")

    def unroll_type(self, typ: DefinedType) -> List[str]:
        """
        Unroll a defined type into its components

        :param typ:
        :return:
        """
        if isinstance(typ, str):
            if typ in self.type_definitions:
                return self.unroll_type(self.type_definitions[typ])
            return [typ]
        if isinstance(typ, list):
            ts = []
            for t in typ:
                ts.extend(self.unroll_type(t))
            return ts
        raise ValueError(f"Unknown type {typ}")


def as_object(self: Any, parent=None) -> Any:
    if parent == "constants":
        # TODO
        return {}
    if isinstance(self, Extension):
        return as_object(self.to_model_object())
    elif isinstance(self, Term):
        return {"type": type(self).__name__, "arguments": [self.predicate] + [as_object(x) for x in self.values]}
    elif isinstance(self, Variable):
        return {"type": type(self).__name__, "arguments": self.as_sexpr()[1:]}
    elif isinstance(self, Sentence):
        return {"type": type(self).__name__, "arguments": [as_object(x) for x in self.arguments]}
    elif isinstance(self, (PredicateDefinition, Theory, SentenceGroup)):
        return {
            "type": type(self).__name__,
            **{k: as_object(v, k) for k, v in vars(self).items() if v is not None},
        }
    elif isinstance(self, Enum):
        return self.value
    elif isinstance(self, list):
        return [as_object(x) for x in self]
    else:
        return self


def from_object(obj: Any) -> Any:
    """
    Convert a dictionary representation of a sentence or theory back to the original object.

    Example:

        >>> from_object({"type": "Term", "arguments": ["FriendOf", "Alice", "Bob"]})
        FriendOf(Alice, Bob)

    :param obj:
    :return:
    """
    if isinstance(obj, dict):
        # type designation
        if "type" in obj:
            cls = globals()[obj["type"]]
            if cls in (PredicateDefinition, Theory, SentenceGroup):
                return cls(**{k: from_object(v) for k, v in obj.items() if k != "type"})
            else:
                args = obj.get("arguments", [])
                if issubclass(cls, Term) and cls != Term:
                    args = args[1:]  # skip the predicate name for Term subclasses
                args_tr = [from_object(x) for x in args]
                return cls(*args_tr)
        else:
            return obj
    if isinstance(obj, list):
        return [from_object(x) for x in obj]
    return obj


class NotInProfileError(ValueError):
    """
    Raised when a sentence is not in some profile
    """

    pass
