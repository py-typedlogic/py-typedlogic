"""
Data model for the typed-logic framework.

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

"""
import operator
import types
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Type, Union, _SpecialForm, get_origin

SExpressionAtom = Any
SExpressionTerm = List["SExpression"]
SExpression = Union[SExpressionTerm, SExpressionAtom]

@dataclass
class PredicateDefinition:
    """
    Defines the name and arguments of a predicate.

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
        return PredicateDefinition(predicate=python_class.__name__,
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

    @property
    def annotations(self):
        return self._annotations

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
    if hasattr(s, '__origin__') and get_origin(s) is not None:
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

    Keyword argument based initializaton is also supported:

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
            bindings = {f'arg{i}': arg for i, arg in enumerate(args)}
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
            return f'{self.predicate}'
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



class Extension(Sentence, ABC):
    """
    Use this class for framework-specific extensions.

    An example of this is the `Fact` class which subclasses Extension, and is intended to be
    subclasses by domain-specific classes representing predicate definitions, whose instances
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

    operands: Tuple = field(default_factory=tuple)

    def __init__(self, *operands, **kwargs):
        self.operands = operands
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
        return f'~{self.operands[0]}'

    def __repr__(self):
        return f'Not({repr(self.operands[0])})'

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
        return f'({self.operands[0]} {self.symbol} {self.operands[1]})'

    def __repr__(self):
        return f'{type(self).__name__}({repr(self.operands[0])}, {repr(self.operands[1])})'

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
        return f'({self.operands[0]} -> {self.operands[1]})'

    def __repr__(self):
        return f'Implies({repr(self.operands[0])}, {repr(self.operands[1])})'


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
        return f'({self.operands[0]} <- {self.operands[1]})'

    def __repr__(self):
        return f'Implied({repr(self.operands[0])}, {repr(self.operands[1])})'


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
        return f'({self.operands[0]} <-> {self.operands[1]})'

    def __repr__(self):
        return f'Iff({repr(self.operands[0])}, {repr(self.operands[1])})'


@dataclass
class NegationAsFailure(BooleanSentence):
    """
    A negated sentence, interpreted via negation as failure semantics.
    """

    def __init__(self, operand, **kwargs):
        super().__init__(operand, **kwargs)

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
        return f'∀{self._bindings_str()} : {self.sentence}'

    def __repr__(self):
        return f'Forall([{self._bindings_str()}] : {repr(self.sentence)})'


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
        return f'∃{self.sentence}'

    def __repr__(self):
        return f'Exists({self._bindings_str()} : {repr(self.sentence)})'

    def __hash__(self):
        return hash((self.quantifier, self._bindings_str(), self.sentence))


class SentenceGroupType(str, Enum):
    AXIOM = "axiom"
    GOAL = "goal"

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
        return [s for sg in self.sentence_groups or [] if sg.group_type == SentenceGroupType.GOAL for s in sg.sentences or []]

    def add(self, sentence: Sentence):
        """
        Add a sentence to the theory

        :param sentence:
        :return:
        """
        if isinstance(sentence, Extension):
            sentence = sentence.to_model_object()
        if not self.sentence_groups:
            self.sentence_groups = []
        self.sentence_groups.append(SentenceGroup(name="Sentences", sentences=[sentence]))

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
        return {
            "type": type(self).__name__,
            "arguments": [self.predicate] + [as_object(x) for x in self.values]
        }
    elif isinstance(self, Variable):
        return {
            "type": type(self).__name__,
            "arguments": self.as_sexpr()[1:]
        }
    elif isinstance(self, Sentence):
        return {
            "type": type(self).__name__,
            "arguments": [as_object(x) for x in self.arguments]
        }
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
    if isinstance(obj, dict):
        if "type" in obj:
            cls = globals()[obj["type"]]
            if cls in (PredicateDefinition, Theory, SentenceGroup):
                return cls(**{k: from_object(v) for k, v in obj.items() if k != "type"})
            else:
                return cls(*[from_object(x) for x in obj["arguments"]])
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
