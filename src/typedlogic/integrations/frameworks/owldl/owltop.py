"""
OWL-DL Top Level Classes and Axioms.

In this integration, OWL-DL is treated as a subset of FOL, consisting of (a) Unary predicate
definitions (classes) and (b) Binary predicate definitions (Object and Data Properties).

This module also provides Pythonic integration through top-level classes that can be inherited
to defined OWL ontologies through Python classes. These Python classes can be treated as normal python
classes, they can be instantiated to create an ABox. They can also be translated into FOL axioms,
where they can be used for reasoning over ABoxes using a Solver.

This module is pure python and does not attempt to parse or serialize OWL - for that,
an integration with a framework such as Py-horned-owl is recommended.
"""
from abc import ABC
from dataclasses import dataclass, field
from decimal import Decimal
from functools import wraps
from typing import Any, Callable, ClassVar, Iterator, List, Mapping, Optional, Tuple, Type, Union

from typedlogic import And, Exists, Fact, Forall, Iff, Implies, Not, Or, Sentence, Term, Variable

I = Variable("I")
J = Variable("J")
K = Variable("K")
P = Variable("P")
C = Variable("C")
D = Variable("D")


# classes and properties are canonically declared as python classes (types);
# support str for forward references and to allow easier bridging with py-horned-owl
OntologyElementReference = str
IRI = str


@dataclass
class OntologyElement:
    """
    A class or property.

    Note this is designed to simulate python classes, such that it can be used in place
    of Thing, TopObjectProperty, TopDataProperty, etc.
    """

    __name__: OntologyElementReference
    owl_type: Optional[str] = None
    iri: Optional[IRI] = None

    def __str__(self):
        # return f"{self.owl_type}({self.__name__})"
        return self.__name__

    def __repr__(self):
        if self.iri:
            return f"{self.owl_type}({self.__name__}, {self.iri})"
        else:
            return f"{self.owl_type}({self.__name__})"


def as_list(e) -> List:
    if e == None:
        return []
    if isinstance(e, list):
        return e
    return [e]


def _conjunction(sentences: List[Sentence]) -> Sentence:
    if len(sentences) == 0:
        raise ValueError("Cannot create conjunction of zero sentences")
    if len(sentences) == 1:
        return sentences[0]
    return And(*sentences)


def individual_name(e: "Individual") -> str:
    if isinstance(e, str):
        return e
    if isinstance(e, OntologyElement):
        return e.__name__
    return str(e)


def class_name(ce: "Class") -> str:
    if isinstance(ce, str):
        return ce
    if isinstance(ce, OntologyElement):
        return ce.__name__
    return str(ce)


def object_property_name(op: "ObjectProperty") -> str:
    if isinstance(op, str):
        return op
    if isinstance(op, OntologyElement):
        return op.__name__
    return str(op)


def instance_of(inst_var: Variable, ce: "ClassExpression") -> Sentence:
    if isinstance(ce, AnonymousClassExpression):
        return ce.as_fol() or And()
    if isinstance(ce, str):
        return Term(ce, inst_var)
    return Term(ce.__name__, inst_var)


def instance_of_op(inst_var1: Variable, inst_var2: Variable, ope: "ObjectPropertyExpression") -> Optional[Sentence]:
    if isinstance(ope, InverseObjectProperty):
        return instance_of_op(inst_var2, inst_var1, ope.first)
    if isinstance(ope, str):
        return Term(ope, inst_var1, inst_var2)
    return Term(ope.__name__, inst_var1, inst_var2)


def instance_of_dp(inst_var1: Variable, inst_var2: Variable, dpe: "DataPropertyExpression") -> Optional[Sentence]:
    if isinstance(dpe, str):
        return Term(dpe, inst_var1, inst_var2)
    return Term(dpe.__name__, inst_var1, inst_var2)


@dataclass(frozen=True)
class Thing(Fact):
    """
    The top level class in OWL-DL. Everything is a Thing.

    For your object model to be included in the OWL-DL mapping, all your classes
    representing individuals should inherit from Thing.

    Basic Example:

    ```python
    class Person(Thing):
        '''A person'''

    class Pet(Thing):
        '''A pet'''
    ```

    Formally, OWL Classes are unary predicates, and instances are unary ground terms:

    ```python
    facts = [Person("P1"), Pet("Fido")]
    ```

    You can create more complex defined classes, using OWL Frame-style class definitions:

    ```python
    class HasPet(TopObjectProperty):
        '''A property that relates a person to a pet'''
        domain = Person
        range = Pet

    class PetOwner(Person):
        '''A person that owns a pet'''
        equivalent_to = Person & ObjectSomeValuesFrom(HasPet, Pet)
    ```

    A thing class can have ClassVars `equivalent_to`, `subclass_of`, ...
    Note these are class-level.

    We can create and reason over instances and facts:

    ```python
    facts = [Person("P1"), Pet("Fido"), HasPet("P1", "Fido")]
    reasoner = OWLReasoner()
    reasoner.init_from_file(Path(__file__))
    for f in facts:
        reasoner.add(f)
    model = reasoner.model()
    for t in model.ground_terms:
        print(t)
    ```

    Results will include:

    ```
    PetOwner(P1)
    ```

    Formally, the Thing class is a subclass of a typed-logic Fact, which instantiates an
    OWLCLass python metaclass:

    ```mermaid
    classDiagram
    class Thing {
        IRI iri
    }
    Fact <|-- Thing
    Thing --> `OWLCLass[[metaclass]]` : instance_of
    `OWLCLass[[metaclass]]` --> "*" ClassExpression : subclass_of
    `OWLCLass[[metaclass]]` --> "*" ClassExpression : equivalent_to
    `OWLCLass[[metaclass]]` --> "*" ClassExpression : disjoint_with
    `OWLCLass[[metaclass]]` --> "*" ClassExpression : disjoint_union_of
    ```

    """

    iri: IRI

    subclass_of: ClassVar[Optional["ClassExpression"]] = None
    equivalent_to: ClassVar[Optional["ClassExpression"]] = None
    disjoint_with: ClassVar[Optional["ClassExpression"]] = None
    disjoint_union_of: ClassVar[Optional[List["ClassExpression"]]] = None

    @classmethod
    def axioms_iter(cls) -> Iterator["Axiom"]:
        for parent in cls.__bases__:
            if issubclass(parent, Thing):
                yield SubClassOf(cls, parent)
        yield from [SubClassOf(cls, e) for e in as_list(cls.subclass_of)]
        yield from [DisjointClasses(cls, e) for e in as_list(cls.disjoint_with)]
        yield from [EquivalentClasses(cls, e) for e in as_list(cls.equivalent_to)]
        if cls.disjoint_union_of:
            yield DisjointUnion(cls, *cls.disjoint_union_of)

    @classmethod
    def axioms(cls) -> List["Axiom"]:
        return list(cls.axioms_iter())

    @classmethod
    def to_sentences(cls) -> List[Sentence]:
        return [a for a in [axiom.as_fol() for axiom in cls.axioms()] if a is not None]


@dataclass(frozen=True)
class TopObjectProperty(Fact):
    """
    The top object property.

    Example:
    -------
    ```python
    class Person(Thing):
        '''A person'''

    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''
        domain = Person
        range = Person

    class HasAncestor(HasParent):
        '''A property that relates a person to their ancestor'''
        transitive = True
    ```

    Formally, OWL Object Properties are binary predicates, and instances are binary ground terms:

    ```python
    facts = [HasParent("P1", "P2"), HasAncestor("P1", "P3")]
    ```

    Formally, the TopObjectProperty class is a subclass of a 2-ary typed-logic Fact, which instantiates an
    OWLObjectProperty python metaclass:

    ```mermaid
    classDiagram
    class TopObjectProperty {
        IRI subject
        IRI object
    }
    Fact <|-- TopObjectProperty
    TopObjectProperty --> `OWLObjectProperty[[metaclass]]` : instance_of
    `OWLObjectProperty[[metaclass]]` --> "*" ObjectPropertyExpression : subproperty_of
    `OWLObjectProperty[[metaclass]]` --> "*" PropertyExpressionChain : subproperty_chain
    `OWLObjectProperty[[metaclass]]` --> "*" ClassExpression : domain
    `OWLObjectProperty[[metaclass]]` --> "*" ClassExpression : range

    class `OWLObjectProperty[[metaclass]]` {
       Boolean transitive
       Boolean symmetric
       Boolean asymmetric
       Boolean reflexive
      Boolean irreflexive
      Boolean functional
      Boolean inverse_functional
    }
    ```



    """

    subject: IRI
    object: IRI

    transitive: ClassVar[Optional[bool]] = None
    symmetric: ClassVar[Optional[bool]] = None
    asymmetric: ClassVar[Optional[bool]] = None
    reflexive: ClassVar[Optional[bool]] = None
    irreflexive: ClassVar[Optional[bool]] = None
    functional: ClassVar[Optional[bool]] = None
    inverse_functional: ClassVar[Optional[bool]] = None
    subproperty_of: ClassVar[Optional["ObjectPropertyExpression"]] = None
    subproperty_chain: ClassVar[Optional["PropertyExpressionChain"]] = None
    equivalent_to: ClassVar[Optional["ObjectPropertyExpression"]] = None
    disjoint_with: ClassVar[Optional["ObjectPropertyExpression"]] = None
    inverse_of: ClassVar[Optional["ObjectPropertyExpression"]] = None
    domain: ClassVar[Optional["ClassExpression"]] = None
    range: ClassVar[Optional["ClassExpression"]] = None

    @classmethod
    def some(cls, ce: "ClassExpression") -> "ObjectSomeValuesFrom":
        return ObjectSomeValuesFrom(cls, ce)

    @classmethod
    def only(cls, ce: "ClassExpression") -> "ObjectAllValuesFrom":
        return ObjectAllValuesFrom(cls, ce)

    @classmethod
    def value(cls, i: "Individual") -> "ObjectHasValue":
        return ObjectHasValue(cls, i)

    @classmethod
    def axioms_iter(cls) -> Iterator["Axiom"]:
        for parent in cls.__bases__:
            if issubclass(parent, TopObjectProperty):
                yield SubObjectPropertyOf(cls, parent)
        yield from [SubObjectPropertyOf(cls, e) for e in as_list(cls.subproperty_of)]
        yield from [SubObjectPropertyOf(chain, cls) for chain in as_list(cls.subproperty_chain)]
        yield from [ObjectPropertyDomain(cls, e) for e in as_list(cls.domain)]
        yield from [ObjectPropertyRange(cls, e) for e in as_list(cls.range)]
        if cls.transitive:
            yield from [TransitiveObjectProperty(cls)]
        if cls.symmetric:
            yield from [SymmetricObjectProperty(cls)]
        if cls.asymmetric:
            yield from [AsymmetricObjectProperty(cls)]
        if cls.reflexive:
            yield from [ReflexiveObjectProperty(cls)]
        if cls.irreflexive:
            yield from [IrreflexiveObjectProperty(cls)]
        if cls.functional:
            yield from [FunctionalObjectProperty(cls)]
        if cls.inverse_functional:
            yield from [InverseFunctionalObjectProperty(cls)]
        yield from [EquivalentObjectProperties(cls, e) for e in as_list(cls.equivalent_to)]
        yield from [DisjointObjectProperties(cls, e) for e in as_list(cls.disjoint_with)]
        if cls.inverse_of:
            yield from [InverseObjectProperties(cls, cls.inverse_of)]

    @classmethod
    def axioms(cls) -> List["Axiom"]:
        return list(cls.axioms_iter())

    @classmethod
    def to_sentences(cls) -> List[Sentence]:
        return [a for a in [axiom.as_fol() for axiom in cls.axioms()] if a is not None]


@dataclass(frozen=True)
class TopDataProperty(Fact):
    """
    The top data property.

    Example:
    -------
    ```python
    class Person(Thing):
        '''A person'''

    class HasAge(TopDataProperty):
        '''A property that relates a person to their age'''
        domain = Person
        range = int
    ```

    Formally, OWL Data Properties are binary predicates, and instances are binary ground terms:

    ```python
    facts = [HasAge("P1", 25)]
    ```

    Formally, the TopDataProperty class is a subclass of a 2-ary typed-logic Fact, which instantiates an
    OWLDataProperty python metaclass:

    ```mermaid
    classDiagram
    class TopDataProperty {
        IRI subject
        Union[str, int, float, bool, Decimal] object
    }
    Fact <|-- TopDataProperty
    TopDataProperty --> `OWLDataProperty[[metaclass]]` : instance_of
    `OWLDataProperty[[metaclass]]` --> "*" DataPropertyExpression : subproperty_of
    `OWLDataProperty[[metaclass]]` --> "*" ClassExpression : domain
    `OWLDataProperty[[metaclass]]` --> "*" DataRange : range
    class `OWLDataProperty[[metaclass]]` {
         Boolean functional
     }
     ```

    """

    subject: IRI
    object: Union[str, int, float, bool, Decimal]

    functional: ClassVar[Optional[bool]] = None
    subproperty_of: ClassVar[Optional["DataPropertyExpression"]] = None
    equivalent_to: ClassVar[Optional["DataPropertyExpression"]] = None
    disjoint_with: ClassVar[Optional["DataPropertyExpression"]] = None
    domain: ClassVar[Optional["ClassExpression"]] = None
    range: ClassVar[Optional["DataRange"]] = None

    @classmethod
    def axioms_iter(cls) -> Iterator["Axiom"]:
        for parent in cls.__bases__:
            if issubclass(parent, TopDataProperty):
                yield SubDataPropertyOf(cls, parent)
        yield from [SubDataPropertyOf(cls, e) for e in as_list(cls.subproperty_of)]
        yield from [DataPropertyDomain(cls, e) for e in as_list(cls.domain)]
        yield from [DataPropertyRange(cls, e) for e in as_list(cls.range)]
        if cls.functional:
            yield from [FunctionalDataProperty(cls)]
        yield from [EquivalentDataProperties(cls, e) for e in as_list(cls.equivalent_to)]
        yield from [DisjointDataProperties(cls, e) for e in as_list(cls.disjoint_with)]

    @classmethod
    def axioms(cls) -> List["Axiom"]:
        return list(cls.axioms_iter())

    @classmethod
    def to_sentences(cls) -> List[Sentence]:
        return [a for a in [axiom.as_fol() for axiom in cls.axioms()] if a is not None]


@dataclass
class AnonymousIndividual(ABC):
    """
    An anonymous individual.
    """

    first: str


@dataclass
class Literal(ABC):
    """
    A literal.
    """

    pass


@dataclass
class SimpleLiteral:
    """
    A simple literal.
    """

    literal: str


@dataclass
class LanguageLiteral:
    """
    A language literal.

    Example:

        >>> v = LanguageLiteral("fromage", "en")
    """

    literal: str
    lang: str


@dataclass
class DatatypeLiteral:
    """
    A datatype literal.

    Example:

        >>> v = LanguageLiteral("12", "xsd:int")
    """

    literal: str
    datatype_iri: IRI


Class = Union[Type[Thing], OntologyElementReference, OntologyElement]
DataProperty = Union[Type[TopDataProperty], OntologyElementReference, OntologyElement]
Datatype = Union[IRI, Type[str], Type[int], Type[float], Type[bool]]
ObjectProperty = Union[Type[TopObjectProperty], OntologyElementReference, OntologyElement]

NamedIndividual = IRI
Individual = Union[NamedIndividual, "AnonymousIndividual", OntologyElement]
ClassExpression = Union[Class, "AnonymousClassExpression"]
ObjectPropertyExpression = Union[ObjectProperty, "InverseObjectProperty"]
DataPropertyExpression = DataProperty
DataRange = Union[Datatype, "AnonymousDataRange"]


@dataclass
class Axiom(ABC):
    """
    Abstract base class for axioms.

    Axioms can be declared implicitly, in "Frame-style" class definitions, or in
    an `__axioms__` module variable
    """

    frame_keyword: ClassVar[Optional[str]] = None
    annotations: ClassVar[Optional[Mapping[str, Any]]] = None

    # @abstractmethod
    def as_fol(self) -> Optional[Sentence]:
        return None


@dataclass
class SubClassOf(Axiom):
    """
    A sub-class-of axiom.

    Axioms can be declared explicitly:

    ```python
    class Person(Thing):
        '''A person'''

    class Employee(Thing):
        '''A person that is employed'''

    __axioms__ = [ SubClassOf(Employee, Person) ]
    ```

    However, it is more idiomatic to declare axioms implicitly in Frame-style class definitions:

    ```python
    class Person(Thing):
        '''A person'''

    class Employee(Thing):
        '''A person that is employed'''
        subclass_of = Person
    ```

    Note that when the superclass is a named class, the more pythonic equivalent is preferred:

    ```python
    class Employee(Person):
        '''A person that is employed'''
    ```

    Using an explicit class var is necessary when the superclass is an expression:

    ```python
    class Organization(Thing):
        '''An organization'''

    class EmployedBy(TopObjectProperty):
        domain = Employee
        range = Organization

    class Employee(Person):
        '''A person that is employed'''
        subclass_of = ObjectSomeValuesFrom(EmployedBy, Organization)
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- SubClassOf
    SubClassOf --> "*" ClassExpression : sub
    SubClassOf --> "*" ClassExpression : sup
    ```

    """

    frame_keyword = "subclass_of"
    sub: ClassExpression
    sup: ClassExpression

    def as_fol(self) -> Optional[Sentence]:
        return Forall([I], Implies(instance_of(I, self.sub), instance_of(I, self.sup)))

    def __repr__(self) -> str:
        return f"SubClassOf({self.sub}, {self.sup})"


@dataclass
class PropertyExpressionChain:
    """
    A chain of property expressions.

    Example:
    -------
    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''
        domain = Person
        range = Person

    class HasGrandparent(TopObjectProperty):
        '''A property that relates a person to their grandparent'''
        subproperty_chain = PropertyExpressionChain(HasParent, HasParent)
    ```

    UML:

    ```
    classDiagram
    PropertyExpressionChain --> "*" ObjectPropertyExpression : chain
    ```

    """

    chain: Tuple[ObjectPropertyExpression, ...]

    def __init__(self, *chain: ObjectPropertyExpression):
        self.chain = chain


@dataclass
class SubObjectPropertyOf(Axiom):
    """
    A sub-object-property-of axiom.

    Example of explicit declaration:

    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''
        domain = Person
        range = Person

    class HasGrandparent(TopObjectProperty):
        '''A property that relates a person to their grandparent'''

    __axioms__ = [ SubObjectPropertyOf(HasGrandparent, HasParent) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''
        domain = Person
        range = Person

    class HasGrandparent(TopObjectProperty):
        '''A property that relates a person to their grandparent'''
        subproperty_of = HasParent
    ```

    When the parent is a named class, the more pythonic equivalent is preferred:

    ```python
    class HasGrandparent(HasParent):
        '''A property that relates a person to their grandparent'''
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- SubObjectPropertyOf
    SubObjectPropertyOf --> "*" ObjectPropertyExpressionOrPropertyExpressionChain : sub
    SubObjectPropertyOf --> "*" ObjectPropertyExpression : sup
    ```

    """

    frame_keyword = "subproperty_of"
    sub: Union[ObjectPropertyExpression, PropertyExpressionChain]
    sup: ObjectPropertyExpression

    def as_fol(self) -> Optional[Sentence]:
        if isinstance(self.sup, PropertyExpressionChain):
            raise ValueError(f"Cannot have a chain as a super property - did you accidentally invert? {self}")
        if isinstance(self.sub, PropertyExpressionChain):
            chain_len = len(self.sub.chain)
            inst_vars = [Variable(f"J{i}") for i in range(chain_len + 1)]
            conjs = []
            for i in range(chain_len):
                conjs.append(instance_of_op(inst_vars[i], inst_vars[i + 1], self.sub.chain[i]))
            return Forall(inst_vars, Implies(And(*conjs), instance_of_op(inst_vars[0], inst_vars[-1], self.sup)))
        else:
            return Forall([P, I, J], Implies(instance_of_op(I, J, self.sub), instance_of_op(I, J, self.sup)))


@dataclass
class TransitiveObjectProperty(Axiom):
    """
    A transitive-object-property axiom.

    Example of explicit declaration:

    ```python
    class HasAncestor(TopObjectProperty):
        pass

    __axioms__ = [ TransitiveObjectProperty(HasAncestor) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class HasAncestor(TopObjectProperty):
        transitive = True
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- TransitiveObjectProperty
    TransitiveObjectProperty --> "1" ObjectPropertyExpression : first
    ```

    """

    frame_keyword = "transitive"
    first: ObjectPropertyExpression

    def as_fol(self) -> Optional[Sentence]:
        return Forall(
            [I, J, K],
            Implies(
                And(instance_of_op(I, J, self.first), instance_of_op(J, K, self.first)),
                instance_of_op(I, K, self.first),
            ),
        )


@dataclass
class InverseObjectProperties(Axiom):
    """
    An inverse-object-properties axiom.

    Example of explicit declaration:

    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''
        domain = Person
        range = Person

    class HasChild(TopObjectProperty):
        '''A property that relates a person to their child'''
        domain = Person
        range = Person

    __axioms__ = [ InverseObjectProperties(HasParent, HasChild) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''
        domain = Person
        range = Person
        inverse_of = HasChild
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- InverseObjectProperties
    InverseObjectProperties --> "1" ObjectPropertyExpression : first
    InverseObjectProperties --> "1" ObjectPropertyExpression : second
    ```
    """

    frame_keyword = "inverse_of"
    first: ObjectPropertyExpression
    second: ObjectPropertyExpression

    def as_fol(self) -> Optional[Sentence]:
        return Forall([I, J], Iff(instance_of_op(I, J, self.first), instance_of_op(J, I, self.second)))


@dataclass
class SymmetricObjectProperty(Axiom):
    """
    A symmetric-object-property axiom.

    Example of explicit declaration:

    ```python
    class HasSibling(TopObjectProperty):
        '''A property that relates a person to their sibling'''
        domain = Person
        range = Person

    __axioms__ = [ SymmetricObjectProperty(HasSibling) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class HasSibling(TopObjectProperty):
        '''A property that relates a person to their sibling'''
        domain = Person
        range = Person
        symmetric = True
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- SymmetricObjectProperty
    SymmetricObjectProperty --> "1" ObjectPropertyExpression : first
    ```

    """

    frame_keyword = "symmetric"
    first: ObjectPropertyExpression

    def as_fol(self) -> Optional[Sentence]:
        return Forall([I, J], Iff(instance_of_op(I, J, self.first), instance_of_op(J, I, self.first)))


@dataclass
class AsymmetricObjectProperty(Axiom):
    """
    An asymmetric-object-property axiom.

    Example of explicit declaration:

    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''
        domain = Person
        range = Person

    __axioms__ = [ AsymmetricObjectProperty(HasParent) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''
        domain = Person
        range = Person
        asymmetric = True
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- AsymmetricObjectProperty
    AsymmetricObjectProperty --> "1" ObjectPropertyExpression : first
    ```

    """

    frame_keyword = "asymmetric"
    first: ObjectPropertyExpression

    def as_fol(self) -> Optional[Sentence]:
        return Forall([I, J], Implies(instance_of_op(I, J, self.first), Not(instance_of_op(J, I, self.first))))


@dataclass
class ReflexiveObjectProperty(Axiom):
    """
    A reflexive-object-property axiom.

    Example of explicit declaration:

    ```python
    class RelatedTo(TopObjectProperty):
        '''A property that relates a thing to itself'''
        domain = Thing
        range = Thing

    __axioms__ = [ ReflexiveObjectProperty(RelatedTo) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class RelatedTo(TopObjectProperty):
        '''A property that relates a thing to itself'''
        domain = Thing
        range = Thing
        reflexive = True
    ```

    In practice, relfexive axioms are too strong, but we include them for completeness.

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- ReflexiveObjectProperty
    ReflexiveObjectProperty --> "1" ObjectPropertyExpression : first
    ```

    """

    frame_keyword = "reflexive"
    first: ObjectPropertyExpression

    def as_fol(self) -> Optional[Sentence]:
        return Forall([I, C], Implies(instance_of(I, Thing), instance_of_op(I, I, self.first)))


@dataclass
class IrreflexiveObjectProperty(Axiom):
    """
    An irreflexive-object-property axiom.

    Example of explicit declaration:

    ```python

    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''
        domain = Person
        range = Person

    __axioms__ = [ IrreflexiveObjectProperty(HasParent) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''
        domain = Person
        range = Person
        irreflexive = True
    ```

    """

    frame_keyword = "irreflexive"
    first: ObjectPropertyExpression

    def as_fol(self) -> Optional[Sentence]:
        refl_s = instance_of_op(I, I, self.first)
        if refl_s:
            return Not(Exists([I], refl_s))
        return None


@dataclass
class FunctionalObjectProperty(Axiom):
    """
    A functional-object-property axiom.

    Example of explicit declaration:

    ```python

    class HasBiologicalMother(TopObjectProperty):
        '''A property that relates a person to their biological mother'''
        domain = Person
        range = Person

    __axioms__ = [ FunctionalObjectProperty(HasBiologicalMother) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class HasBiologicalMother(TopObjectProperty):
        '''A property that relates a person to their biological mother'''
        domain = Person
        range = Person
        functional = True
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- FunctionalObjectProperty
    FunctionalObjectProperty --> "1" ObjectPropertyExpression : first
    ```

    """

    frame_keyword = "functional"
    first: ObjectPropertyExpression

    def as_fol(self) -> Optional[Sentence]:
        return Forall(
            [I, J, K],
            Implies(And(instance_of_op(I, J, self.first), instance_of_op(I, K, self.first)), Term("eq", J, K)),
        )


@dataclass
class InverseFunctionalObjectProperty(Axiom):
    """
    An inverse-functional-object-property axiom.

    Example of explicit declaration:

    ```python
    class BiologicalMotherOf(TopObjectProperty):
        '''A property that relates a person to their biological mother'''
        domain = Person
        range = Person

    __axioms__ = [ InverseFunctionalObjectProperty(BiologicalMotherOf) ]

    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class BiologicalMotherOf(TopObjectProperty):
        '''A property that relates a person to their biological mother'''
        domain = Person
        range = Person
        inverse_functional = True
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- InverseFunctionalObjectProperty
    InverseFunctionalObjectProperty --> "1" ObjectPropertyExpression : first
    ```
    """

    frame_keyword = "inverse_functional"
    first: ObjectPropertyExpression

    def as_fol(self) -> Optional[Sentence]:
        return Forall(
            [I, J, K],
            Implies(And(instance_of_op(I, J, self.first), instance_of_op(K, J, self.first)), Term("eq", I, K)),
        )


@dataclass
class FunctionalDataProperty(Axiom):
    """
    A functional-data-property axiom.

    Example of explicit declaration:

    ```python
    class HasAge(TopDataProperty):
        '''A property that relates a person to their age'''
        domain = Person
        range = int

    __axioms__ = [ FunctionalDataProperty(HasAge) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class HasAge(TopDataProperty):
        '''A property that relates a person to their age'''
        domain = Person
        range = int
        functional = True
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- FunctionalDataProperty
    FunctionalDataProperty --> "1" DataPropertyExpression : first
    ```

    """

    frame_keyword = "functional"
    first: DataPropertyExpression

    def as_fol(self) -> Optional[Sentence]:
        return Forall(
            [I, J, K],
            Implies(And(instance_of_dp(I, J, self.first), instance_of_dp(I, K, self.first)), Term("eq", J, K)),
        )


@dataclass
class SubDataPropertyOf(Axiom):
    """
    A sub-data-property-of axiom.

    Example of explicit declaration:

    ```python
    class HasAge(TopDataProperty):
        '''A property that relates a thing to their age'''
        range = int

    class PersonAge(TopDataProperty):
        '''A property that relates a person to their age'''
        domain = Person

    __axioms__ = [ SubDataPropertyOf(PersonAge, HasAge) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class PersonAge(TopDataProperty):
        '''A property that relates a person to their age'''
        domain = Person
        range = int
        subproperty_of = HasAge
    ```

    When the parent is a named class, the more pythonic equivalent is preferred:

    ```python
    class PersonAge(HasAge):
        '''A property that relates a person to their age'''
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- SubDataPropertyOf
    SubDataPropertyOf --> "*" DataPropertyExpression : sub
    SubDataPropertyOf --> "*" DataPropertyExpression : sup
    ```
    """

    frame_keyword = "subproperty_of"
    sub: DataPropertyExpression
    sup: DataPropertyExpression

    def as_fol(self) -> Optional[Sentence]:
        return Forall([P, I, J], Implies(instance_of_dp(I, J, self.sub), instance_of_dp(I, J, self.sup)))


@dataclass
class EquivalentClasses(Axiom):
    """
    An equivalent-classes axiom.

    Example of explicit declaration:

    ```python
    class Food(Thing):
        pass

    class Beverage(Thing):
        pass

    class MenuItem(Thing):
        pass

    __axioms__ = [ EquivalentClasses(MenuItem, ObjectUnionOf(Food, Beverage)) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class MenuItem(Thing):
        equivalent_to = ObjectUnionOf(Food, Beverage)
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- EquivalentClasses
    EquivalentClasses --> "*" ClassExpression : operands
    ```
    """

    operands: Tuple[ClassExpression, ...] = field(default_factory=tuple)

    def __init__(self, *operands: ClassExpression):
        self.operands = operands

    def as_fol(self) -> Optional[Sentence]:
        num_ops = len(self.operands)
        sentences: List[Sentence] = []
        for i in range(num_ops - 1):
            for j in range(i + 1, num_ops):
                sentences.append(Iff(instance_of(I, self.operands[i]), instance_of(I, self.operands[j])))
        return Forall([I], _conjunction(sentences))


@dataclass
class EquivalentObjectProperties(Axiom):
    """
    An equivalent-object-properties axiom.

    Example of explicit declaration:

    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''
        domain = Person
        range = Person

    class HasChild(TopObjectProperty):
        '''A property that relates a person to their child'''
        domain = Person
        range = Person

    __axioms__ = [ EquivalentObjectProperties(HasParent, ObjectInverseOf(HasChild)) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class HasChild(TopObjectProperty):
        equivalent_to = ObjectInverseOf(HasParent)
    ```

    In this particular case, a simpler more conventional way to declare the inverse is:

    ```python
    class HasChild(TopObjectProperty):
        range = Person
        domain = Person
        inverse_of = HasParent
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- EquivalentObjectProperties
    EquivalentObjectProperties --> "*" ObjectPropertyExpression : operands
    ```

    """

    operands: Tuple[ObjectPropertyExpression, ...] = field(default_factory=tuple)

    def __init__(self, *operands: ObjectPropertyExpression):
        self.operands = operands

    def as_fol(self) -> Optional[Sentence]:
        num_ops = len(self.operands)
        sentences: List[Sentence] = []
        for i in range(num_ops - 1):
            for j in range(i + 1, num_ops):
                sentences.append(Iff(instance_of_op(I, J, self.operands[i]), instance_of_op(I, J, self.operands[j])))
        return Forall([I, J], _conjunction(sentences))


@dataclass
class EquivalentDataProperties(Axiom):
    """
    An equivalent-data-properties axiom.

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- EquivalentDataProperties
    EquivalentDataProperties --> "*" DataPropertyExpression : operands
    ```
    """

    operands: Tuple[DataPropertyExpression, ...] = field(default_factory=tuple)

    def __init__(self, *operands: DataPropertyExpression):
        self.operands = operands

    def as_fol(self) -> Optional[Sentence]:
        num_ops = len(self.operands)
        sentences: List[Sentence] = []
        for i in range(num_ops - 1):
            for j in range(i + 1, num_ops):
                sentences.append(Iff(instance_of_dp(I, J, self.operands[i]), instance_of_dp(I, J, self.operands[j])))
        return Forall([I, J], _conjunction(sentences))


@dataclass
class DisjointObjectProperties(Axiom):
    """
    A disjoint-object-properties axiom.

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- DisjointObjectProperties
    DisjointObjectProperties --> "*" ObjectPropertyExpression : operands
    ```
    """

    operands: Tuple[ObjectPropertyExpression, ...] = field(default_factory=tuple)

    def __init__(self, *operands: ObjectPropertyExpression):
        self.operands = operands

    def as_fol(self) -> Optional[Sentence]:
        num_ops = len(self.operands)
        sentences: List[Sentence] = []
        for i in range(num_ops - 1):
            for j in range(i + 1, num_ops):
                sentences.append(
                    Not(And(instance_of_op(I, J, self.operands[i]), instance_of_op(I, J, self.operands[j])))
                )
        return Not(Exists([I, J], Or(*sentences)))


@dataclass
class DisjointDataProperties(Axiom):
    """
    A disjoint-data-properties axiom.

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- DisjointDataProperties
    DisjointDataProperties --> "*" DataPropertyExpression : operands
    ```
    """

    operands: Tuple[DataPropertyExpression, ...] = field(default_factory=tuple)

    def __init__(self, *operands: DataPropertyExpression):
        self.operands = operands

    def as_fol(self) -> Optional[Sentence]:
        num_ops = len(self.operands)
        sentences: List[Sentence] = []
        for i in range(num_ops - 1):
            for j in range(i + 1, num_ops):
                sentences.append(
                    Not(And(instance_of_dp(I, J, self.operands[i]), instance_of_dp(I, J, self.operands[j])))
                )
        return Not(Exists([I, J], Or(*sentences)))


@dataclass
class DisjointClasses(Axiom):
    """
    A disjoint-classes axiom.

    Example of explicit declaration:

    ```python
    class Food(Thing):
        pass

    class Beverage(Thing):
        pass

    __axioms__ = [ DisjointClasses(Food, Beverage) ]
    ```

    Sometimes, the more Frame-style equivalent is preferred:

    ```python
    class Food(Thing):
        pass

    class Beverage(Thing):
        disjoint_with = Food
    ```

    However, the choice of which element of the tuple is the first class is arbitrary,
    so declaration of a top level axiom may be simpler (especially when more than
    two classes are members, or class expressions are involved).

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- DisjointClasses
    DisjointClasses --> "*" ClassExpression : operands
    ```
    """

    operands: Tuple[ClassExpression, ...] = field(default_factory=tuple)

    def __init__(self, *operands: ClassExpression):
        self.operands = operands

    def as_fol(self) -> Optional[Sentence]:
        num_ops = len(self.operands)
        sentences: List[Sentence] = []
        for i in range(num_ops - 1):
            for j in range(i + 1, num_ops):
                sentences.append(Not(And(instance_of(I, self.operands[i]), instance_of(I, self.operands[j]))))
        return Not(Exists([I], Or(*sentences)))


@dataclass
class DisjointUnion(Axiom):
    """
    A disjoint-union axiom.

    Example of explicit declaration:

    ```python
    class Food(Thing):
        pass

    class Beverage(Thing):
        pass

    class MenuItem(Thing):
        pass

    __axioms__ = [ DisjointUnion(MenuItem, Food, Beverage) ]
    ```

    Sometimes, the more Frame-style equivalent is preferred:

    ```python
    class Food(Thing):
        pass

    class Beverage(Thing):
        disjoint_union_of = MenuItem
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- DisjointUnion
    DisjointUnion --> "1" ClassExpression : first
    DisjointUnion --> "*" ClassExpression : operands
    ```
    """

    first: Class
    operands: Tuple[ClassExpression, ...] = field(default_factory=tuple)

    def __init__(self, first: Class, *operands: ClassExpression):
        self.first = first
        self.operands = operands

    def as_fol(self) -> Optional[Sentence]:
        eq = Forall([I], Iff(instance_of(I, self.first), Or(*[instance_of(I, op) for op in self.operands])))
        num_ops = len(self.operands)
        disj: List[Sentence] = []
        for i in range(num_ops - 1):
            for j in range(i + 1, num_ops):
                disj.append(Not(And(instance_of(I, self.operands[i]), instance_of(I, self.operands[j]))))
        return And(eq, Not(Exists([I], Or(*disj))))


@dataclass
class AnonymousClassExpression(ABC):
    """
    An base class for anonymous class expressions.
    """

    def as_fol(self) -> Optional[Sentence]:
        raise NotImplementedError(f"{self} Must implement as_fol method")


@dataclass
class InverseObjectProperty:
    """
    An inverse object property expression.

    Example:
    -------
    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''
        domain = Person
        range = Person

    class HasChild(TopObjectProperty):
        '''A property that relates a person to their child'''

    __axioms__ = [ EquivalentObjectProperties(HasParent, InverseObjectProperty(HasChild)) ]
    ```

    UML:

    ```mermaid
    classDiagram
    InverseObjectProperty --> "1" ObjectPropertyExpression : property
    ```

    """

    first: ObjectProperty

    def as_fol(self) -> Optional[Sentence]:
        raise AssertionError("Not to be called directly")


@dataclass
class ObjectIntersectionOf(AnonymousClassExpression):
    """
    A ClassExpression that is the intersection of a list of ClassExpressions.

    Example of explicit axiom declaration:

    ```python
    class Pizza(Thing):
        pass

    class Cheesy(Thing):
        pass

    class CheesyPizza(Thing):
        pass

    __axioms__ = [ EquivalentClasses(CheesyPizza, ObjectIntersectionOf(Pizza, Cheesy)) ]
    ```

    It is more idiomatic to declare axioms implicitly in Frame-style class definitions:

    ```python
    class CheesyPizza(Thing):
        equivalent_to = ObjectIntersectionOf(Pizza, Cheesy)
    ```

    UML:

    ```mermaid
    classDiagram
    AnonymousClassExpression <|-- ObjectIntersectionOf
    ObjectIntersectionOf --> "*" ClassExpression : operands
    ```

    """

    operands: Tuple[ClassExpression, ...] = field(default_factory=tuple)

    def __init__(self, *operands: ClassExpression):
        self.operands = operands

    def as_fol(self) -> Sentence:
        return And(*[instance_of(I, op) for op in self.operands])


@dataclass
class ObjectUnionOf(AnonymousClassExpression):
    """
    A ClassExpression that is the union of a list of ClassExpressions.

    Example of explicit axiom declaration:

    ```python
    class Pizza(Thing):
        pass

    class CheeseOnToast(Thing):
        pass

    class Pizzaesque(Thing)
        pass

    __axioms__ = [ EquivalentClasses(Pizzaesque, ObjectUnionOf(Pizza, CheeseOnToast)) ]
    ```

    It is more idiomatic to declare axioms implicitly in Frame-style class definitions

    ```python
    class Pizzaesque(Thing):
        equivalent_to = ObjectUnionOf(Pizza, CheeseOnToast)
    ```

    UML:

    ```mermaid
    classDiagram
    AnonymousClassExpression <|-- ObjectUnionOf
    ObjectUnionOf --> "*" ClassExpression : operands
    ```
    """

    operands: Tuple[ClassExpression, ...] = field(default_factory=tuple)

    def __init__(self, *operands: ClassExpression):
        self.operands = operands

    def as_fol(self) -> Optional[Sentence]:
        return Or(*[instance_of(I, op) for op in self.operands])


@dataclass
class ObjectComplementOf(AnonymousClassExpression):
    """
    A ClassExpression that is the complement of a ClassExpression.

    Example of explicit axiom declaration:

    ```python
    class Pizza(Thing):
        pass

    class MeatPizza(Thing):
        pass

    class VegetarianPizza(Thing):
        pass

    __axioms__ = [ EquivalentClasses(VegetarianPizza, ObjectIntersectionOf(Pizza, ObjectComplementOf(MeatPizza))) ]
    ```

    It is more idiomatic to declare axioms implicitly in Frame-style class definitions

    ```python
    class VegetarianPizza(Thing):
        equivalent_to = ObjectIntersectionOf(Pizza, ObjectComplementOf(MeatPizza))
    ```

    UML:

    ```mermaid
    classDiagram
    AnonymousClassExpression <|-- ObjectComplementOf
    ObjectComplementOf --> "1" ClassExpression : first
    ```
    """

    first: ClassExpression

    def as_fol(self) -> Optional[Sentence]:
        return Not(instance_of(I, self.first))


@dataclass
class ObjectOneOf(AnonymousClassExpression):
    """
    A ClassExpression that is the set of individuals.

    Example of explicit axiom declaration:

    ```python
    class Unit(Thing):
        pass

    inch = Unit("inch")
    cm = Unit("cm")
    m = Unit("m")

    class LengthUnit(Unit):
        pass

    __axioms__ = [ EquivalentClasses(LengthUnit, ObjectOneOf(inch, cm, m)) ]
    ```

    It is more idiomatic to declare axioms implicitly in Frame-style class definitions

    ```python
    class LengthUnit(Unit):
        equivalent_to = ObjectOneOf(inch, cm, m)
    ```

    UML:

    ```mermaid
    classDiagram
    AnonymousClassExpression <|-- ObjectOneOf
    ObjectOneOf --> "*" Individual : operands
    ```
    """

    operands: Tuple[Individual, ...] = field(default_factory=tuple)

    def __init__(self, *operands: Individual):
        self.operands = operands

    def as_fol(self) -> Optional[Sentence]:
        return Or(*[Term("eq", I, individual_name(ind)) for ind in self.operands])


@dataclass
class ObjectSomeValuesFrom(AnonymousClassExpression):
    """
    A ClassExpression representing an existential restriction.

    Example of explicit axiom declaration:

    ```python
    class HasChil(TopObjectProperty):
        '''A property that relates a person to their child'''
        domain = Person
        range = Person

    class Parent(Thing):
        pass

    __axioms__ = [ EquivalentClasses(Parent, ObjectSomeValuesFrom(HasChild, Person)) ]
    ```

    It is more idiomatic to declare axioms implicitly in Frame-style class definitions:

    ```python
    class Parent(Thing):
        equivalent_to = ObjectSomeValuesFrom(HasChild, Person)
    ```

    UML:

    ```mermaid
    classDiagram
    AnonymousClassExpression <|-- ObjectSomeValuesFrom
    ObjectSomeValuesFrom --> "1" ObjectPropertyExpression : ope
    ObjectSomeValuesFrom --> "1" ClassExpression : bce
    ```

    """

    ope: ObjectPropertyExpression
    bce: ClassExpression

    def as_fol(self) -> Optional[Sentence]:
        return Exists([J], And(instance_of_op(I, J, self.ope), instance_of(J, self.bce)))


@dataclass
class ObjectAllValuesFrom(AnonymousClassExpression):
    """
    A ClassExpression representing a universal restriction.

    Example of explicit axiom declaration:

    ```python
    class Pizza(Thing):
        pass

    class Eats(TopObjectProperty):
        domain = Person
        range = Thing

    class Pizzavore(TopObjectProperty):
        pass

    __axioms__ = [ EquivalentClasses(Pizzavore, ObjectAllValuesFrom(Eats, Pizza)) ]
    ```

    It is more idiomatic to declare axioms implicitly in Frame-style class definitions

    ```python
    class Pizzavore(Thing):
        equivalent_to = ObjectAllValuesFrom(Eats, Pizza)
    ```

    UML:

    ```mermaid
    classDiagram
    AnonymousClassExpression <|-- ObjectAllValuesFrom
    ObjectAllValuesFrom --> "1" ObjectPropertyExpression : ope
    ObjectAllValuesFrom --> "1" ClassExpression : bce
    ```

    """

    ope: ObjectPropertyExpression
    bce: ClassExpression

    def as_fol(self) -> Optional[Sentence]:
        return Forall([J], Implies(instance_of_op(I, J, self.ope), instance_of(J, self.bce)))


@dataclass
class ObjectHasValue(AnonymousClassExpression):
    """
    A ClassExpression representing a value restriction.

    Example of explicit axiom declaration:

    ```python

    class Topping(Thing):
        pass

    class Pizza(Thing):
        pass

    class ToppedWith(TopObjectProperty):
        domain = Pizza
        range = Topping

    class MushroomPizza(Topping):
        pass

    __axioms__ = [ EquivalentClasses(MushroomPizza, ObjectHasValue(ToppedWith, Topping("mushroom")) ]
    ```

    It is more idiomatic to declare axioms implicitly in Frame-style class definitions:

    ```python
    class MushroomPizza(Topping):
        equivalent_to = ObjectHasValue(ToppedWith, Topping("mushroom"))
    ```

    """

    ope: ObjectPropertyExpression
    i: Individual

    def as_fol(self) -> Optional[Sentence]:
        return Exists([J], And(instance_of_op(I, J, self.ope), Term("eq", J, self.i)))


@dataclass
class ObjectHasSelf(AnonymousClassExpression):
    """
    A ClassExpression representing a self restriction.

    Example of explicit axiom declaration:

    ```python
    class Person(Thing):
        pass

    class Loves(TopObjectProperty):
        domain = Person
        range = Thing

    class Narcissist(Thing):
        pass

    __axioms__ = [ EquivalentClasses(Narcissist, ObjectHasSelf(Loves)) ]
    ```

    It is more idiomatic to declare axioms implicitly in Frame-style class definitions:

    ```python
    class Narcissist(Thing):
        equivalent_to = ObjectHasSelf(Loves)
    ```

    UML:

    ```mermaid
    classDiagram
    AnonymousClassExpression <|-- ObjectHasSelf
    ObjectHasSelf --> "1" ObjectPropertyExpression :

    """

    ope: ObjectPropertyExpression

    def as_fol(self) -> Optional[Sentence]:
        return instance_of_op(I, I, self.ope)


@dataclass
class ObjectMinCardinality(AnonymousClassExpression):
    """
    A ClassExpression representing a minimum cardinality restriction.

    Example of explicit axiom declaration:

    ```python
    class HasChild(TopObjectProperty):
        '''A property that relates a person to their child'''
        domain = Person
        range = Person

    class ParentOfTwoPlus(Thing):
        pass

    __axioms__ = [ EquivalentClasses(ParentOfTwoPlus, ObjectMinCardinality(2, HasChild, Person)) ]
    ```

    It is more idiomatic to declare axioms implicitly in Frame-style class definitions:

    ```python
    class ParentOfTwoPlus(Thing):
        equivalent_to = ObjectMinCardinality(2, HasChild, Person)
    ```

    UML:

    ```mermaid
    classDiagram
    AnonymousClassExpression <|-- ObjectMinCardinality
    ObjectMinCardinality --> "1" int : n
    ObjectMinCardinality --> "1" ObjectPropertyExpression : ope
    ObjectMinCardinality --> "1" ClassExpression : bce
    ```

    """

    n: int
    ope: ObjectPropertyExpression
    bce: ClassExpression

    # TODO: Aggregates
    # def as_fol(self) -> Optional[Sentence]:
    #   return Forall([J], Implies(instance_of_op(I, J, self.ope), instance_of(J, self.bce)))


@dataclass
class ObjectMaxCardinality(AnonymousClassExpression):
    """
    A ClassExpression representing a maximum cardinality restriction.

    Example of explicit axiom declaration:

    ```python
    class HasChild(TopObjectProperty):
        '''A property that relates a person to their child'''
        domain = Person
        range = Person

    class ParentOfOne(Thing):
        pass

    __axioms__ = [ EquivalentClasses(ParentOfOne, ObjectMinCardinality(0, HasChild, Person) & ObjectMaxCardinality(1, HasChild, Person)) ]
    ```

    It is more idiomatic to declare axioms implicitly in Frame-style class definitions:

    ```python
    class ParentOfOne(Thing):
        equivalent_to = ObjectMinCardinality(0, HasChild, Person) & ObjectMaxCardinality(1, HasChild, Person)
    ```

    UML:

    ```mermaid
    classDiagram
    AnonymousClassExpression <|-- ObjectMaxCardinality
    ObjectMaxCardinality --> "1" int : n
    ObjectMaxCardinality --> "1" ObjectPropertyExpression : ope
    ObjectMaxCardinality --> "1" ClassExpression : bce
    ```

    """

    n: int
    ope: ObjectPropertyExpression
    bce: ClassExpression

    # TODO: Aggregates


@dataclass
class ObjectExactCardinality(AnonymousClassExpression):
    """
    A ClassExpression representing an exact cardinality restriction.

    Example of explicit axiom declaration:

    ```python
    class HasChild(TopObjectProperty):
        '''A property that relates a person to their child'''
        domain = Person
        range = Person

    class ParentOfOne(Thing):
        pass

    __axioms__ = [ EquivalentClasses(ParentOfOne, ObjectExactCardinality(1, HasChild, Person)) ]
    ```

    It is more idiomatic to declare axioms implicitly in Frame-style class definitions:

    ```python
    class ParentOfOne(Thing):
        equivalent_to = ObjectExactCardinality(1, HasChild, Person)
    ```

    UML:

    ```mermaid
    classDiagram
    AnonymousClassExpression <|-- ObjectExactCardinality
    ObjectExactCardinality --> "1" int : n
    ObjectExactCardinality --> "1" ObjectPropertyExpression : ope
    ObjectExactCardinality --> "1" ClassExpression : bce
    ```

    """

    n: int
    ope: ObjectPropertyExpression
    bce: ClassExpression

    # TODO: Aggregates


@dataclass
class AnonymousDataRange(ABC):
    """
    An base class for anonymous data ranges.
    """

    pass


@dataclass
class DatatypeDefinition:
    """
    A datatype definition.
    """

    dt: Datatype
    dr: DataRange


@dataclass
class DataIntersectionOf(AnonymousDataRange):
    """
    A DataRange that is the conjunction of DataRanges.
    """

    operands: Tuple[DataRange, ...] = field(default_factory=tuple)

    def __init__(self, *operands: DataRange):
        self.operands = operands


@dataclass
class DataUnionOf(AnonymousDataRange):
    """
    A DataRange that is the disjunction of DataRanges.
    """

    operands: Tuple[DataRange, ...] = field(default_factory=tuple)

    def __init__(self, *operands: DataRange):
        self.operands = operands


@dataclass
class DataComplementOf(AnonymousDataRange):
    """
    A DataRange that is the complement of a DataRange.
    """

    first: DataRange


@dataclass
class DataOneOf(AnonymousDataRange):
    """
    A DataRange that is the set of literals
    """

    operands: Tuple[Literal, ...] = field(default_factory=tuple)

    def __init__(self, *operands: Literal):
        self.operands = operands


@dataclass
class DataSomeValuesFrom(AnonymousDataRange):
    """
    A DataRange representing an existential restriction.
    """

    dp: DataPropertyExpression
    dr: DataRange


@dataclass
class FacetRestriction:
    """
    A restriction on a datatype.
    """

    f: IRI
    l: Literal

    def as_fol(self) -> Optional[Sentence]:
        return None


@dataclass
class DatatypeRestriction(AnonymousDataRange):
    """
    A DataRange representing a datatype restriction.
    """

    first: Datatype
    second: List[FacetRestriction]

    def as_fol(self) -> Optional[Sentence]:
        return None


@dataclass
class ObjectPropertyDomain(Axiom):
    """
    An object-property-domain axiom.

    Example of explicit declaration:

    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''

    class Person(Thing):
        pass

    __axioms__ = [ ObjectPropertyDomain(HasParent, Person) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''
        domain = Person
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- ObjectPropertyDomain
    ObjectPropertyDomain --> "1" ObjectPropertyExpression : ope
    ObjectPropertyDomain --> "1" ClassExpression : ce
    ``
    """

    frame_keyword = "domain"
    ope: ObjectPropertyExpression
    ce: ClassExpression

    def as_fol(self) -> Optional[Sentence]:
        return Forall([I, J], Implies(instance_of_op(I, J, self.ope), instance_of(I, self.ce)))


@dataclass
class DataPropertyDomain(Axiom):
    """
    A data-property-domain axiom.

    Example of explicit declaration:

    ```python
    class HasAge(TopDataProperty):
        '''A property that relates a person to their age'''

    class Person(Thing):
        pass

    __axioms__ = [ DataPropertyDomain(HasAge, int) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class HasAge(TopDataProperty):
        '''A property that relates a person to their age'''
        domain = Person
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- DataPropertyDomain
    DataPropertyDomain --> "1" DataPropertyExpression : dp
    DataPropertyDomain --> "1" ClassExpression : ce
    ``
    """

    frame_keyword = "domain"
    dp: DataPropertyExpression
    ce: ClassExpression

    def as_fol(self) -> Optional[Sentence]:
        return Forall([I, J], Implies(instance_of_dp(I, J, self.dp), instance_of(I, self.ce)))


@dataclass
class ObjectPropertyRange(Axiom):
    """
    An object-property-range axiom.

    Example of explicit declaration:

    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''

    class Person(Thing):
        pass

    __axioms__ = [ ObjectPropertyRange(HasParent, Person) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''
        range = Person
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- ObjectPropertyRange
    ObjectPropertyRange --> "1" ObjectPropertyExpression : ope
    ObjectPropertyRange --> "1" ClassExpression : ce
    ``
    """

    frame_keyword = "range"
    ope: ObjectPropertyExpression
    ce: ClassExpression

    def as_fol(self) -> Optional[Sentence]:
        return Forall([I, J], Implies(instance_of_op(I, J, self.ope), instance_of(J, self.ce)))


@dataclass
class DataPropertyRange(Axiom):
    """
    A data-property-range axiom.

    Example of explicit declaration:

    ```python
    class HasAge(TopDataProperty):
        '''A property that relates a person to their age'''

    class Person(Thing):
        pass

    __axioms__ = [ DataPropertyRange(HasAge, int) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class HasAge(TopDataProperty):
        '''A property that relates a person to their age'''
        range = int
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- DataPropertyRange
    DataPropertyRange --> "1" DataPropertyExpression : dp
    DataPropertyRange --> "1" DataRange : dr
    ``
    """

    frame_keyword = "range"
    dp: DataPropertyExpression
    dr: DataRange

    # TODO
    # def as_fol(self) -> Optional[Sentence]:
    #    return Forall([I, J], Implies(instance_of_dp(I, J, self.dp), instance_of(J, self.dr)))


@dataclass
class ClassAssertion(Axiom):
    """
    A class-assertion axiom.

    Example of explicit declaration:

    ```python
    class Person(Thing):
        pass

    alice = Person("Alice")

    __axioms__ = [ ClassAssertion(alice, Person) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class Person(Thing):
        pass

    alice = Person("Alice")
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- ClassAssertion
    ClassAssertion --> "1" Individual : i
    ClassAssertion --> "1" ClassExpression : ce
    ``
    """

    ce: ClassExpression
    i: Individual

    def as_fol(self) -> Optional[Sentence]:
        # TODO:
        if isinstance(self.ce, AnonymousClassExpression):
            return And(instance_of(I, self.ce))
        return Term(class_name(self.ce), individual_name(self.i))


@dataclass
class ObjectPropertyAssertion(Axiom):
    """
    An object-property-assertion axiom.

    Example of explicit declaration:

    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''

    alice = Person("Alice")
    bob = Person("Bob")

    __axioms__ = [ ObjectPropertyAssertion(HasParent, alice, bob) ]
    ```

    Normally, the more Frame-style equivalent is preferred:

    ```python
    class HasParent(TopObjectProperty):
        '''A property that relates a person to their parent'''

    alice = Person("Alice")
    bob = Person("Bob")

    alice.has_parent = bob
    ```

    UML:

    ```mermaid
    classDiagram
    Axiom <|-- ObjectPropertyAssertion
    ObjectPropertyAssertion --> "1" ObjectPropertyExpression : ope
    ObjectPropertyAssertion --> "1" Individual : i
    ObjectPropertyAssertion --> "1" Individual : j
    ``
    """

    ope: ObjectPropertyExpression
    i: Individual
    j: Individual

    def as_fol(self) -> Optional[Sentence]:
        if isinstance(self.ope, InverseObjectProperty):
            return ObjectPropertyAssertion(self.ope.first, self.j, self.i).as_fol()
        ope = object_property_name(self.ope)
        i_name = individual_name(self.i)
        j_name = individual_name(self.j)
        return Term(ope, i_name, j_name)


@dataclass(frozen=True)
class Ontology(Fact):
    """
    An ontology.

    Note that an explicit declaration of an ontology is optional, as an ontology
    is inferred to be present in any python modules that contain declarations.

    Example:
    -------
    ```python
    class Animal(Thing):
        pass

    class Cat(Animal):
        pass

    class MyOntology(Ontology):
        iri = "http://example.org/ontology"
        axioms = [SubClassOf(Cat, Animal)]
    ```

    """

    axioms: ClassVar[Optional[List["Axiom"]]] = None

    @classmethod
    def to_sentences(cls) -> List[Sentence]:
        return [a for a in [axiom.as_fol() for axiom in cls.axioms or []] if a is not None]


OWL_AXIOM_REGISTRY = []


def owl_axioms(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    OWL_AXIOM_REGISTRY.append(func)
    return wrapper
