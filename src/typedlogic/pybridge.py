from abc import ABC
from typing import Tuple, Mapping, Any, Dict, Type

import pydantic
from pydantic import BaseModel

from typedlogic import Sentence, Term
from typedlogic.datamodel import Extension


class FactMixin(Extension, ABC):
    """
    Mixin class for facts

    You can use this if you want to effectively inherit from Fact, but want to base your
    classes using your own base class, or something like the Pydantic BaseModel.
    """
    def to_model_object(self) -> Sentence:
        return fact_to_term(self)


class Fact(FactMixin, ABC):
    """
    Abstract base class for grounded facts (unit clauses).

    This class should be subclassed to make domain-specific Fact subclasses.

    E.g

        >>> from pydantic import BaseModel
        >>> class Person(BaseModel, FactMixin):
        ...     name: str
        ...     age: int

    You can then instantiate individual facts:

        >>> p = Person(name="Alice", age=30)

    You can introspect the fact to get the predicate and arguments:

        >>> fact_predicate(p)
        'Person'

        >>> assert fact_arg_py_types(p) == {'name': str, 'age': int}

    """
    pass


def fact_args(fact: FactMixin) -> Tuple[str, ...]:
    """Return the arguments of a predicate"""
    return tuple(vars(fact).keys())


def fact_arg_map(fact: FactMixin) -> Mapping[str, Any]:
    """Return the arguments of a predicate"""
    return vars(fact)


def fact_arg_py_types(fact: FactMixin) -> Dict[str, Type]:
    """
    Introspect the predicate class to get typing information
    """
    return {k: type(v) for k, v in vars(fact).items()}


def fact_arg_values(fact: FactMixin) -> Tuple[Any, ...]:
    """Return the predicate of a sentence"""
    return tuple(vars(fact).values())


def fact_predicate(fact: FactMixin) -> str:
    """Return the predicate of a sentence"""
    return type(fact).__name__


def fact_to_term(fact: FactMixin) -> Term:
    """Convert a fact to a term"""
    return Term(fact_predicate(fact), fact_arg_map(fact))
