"""
Decorators for marking functions as axioms and goals.

Example:
-------
```python
    from dataclasses import dataclass
    from typedlogic import Fact
    from typedlogic.decorators import axiom, goal

    @dataclass
    class Dog(Fact):
        unique_name: str

    @dataclass
    class Cat(Fact):
        unique_name: str

    @axiom
    def disjointness(n: str):
        '''Nothing os both a dog and a cat'''
        assert not(Dog(n) and Cat(n))

    @goal
    def unit_test1():
        '''unit test: if Violet is a cat, then it must be provable that Violet is not a dog'''
        if Cat('Violet'):
           assert not Dog('Violet')
```

Note: when axioms are expressed directly in python programs, it is possible to use
logical connectives such as `and`, `or`, as well as `if...then` to express implication.

When working directly with objects in the datamodel, it's necessary to use symbols
such as `&` and `~`.

"""
from dataclasses import dataclass, fields
from functools import wraps
from typing import Callable

from typedlogic import FactMixin

AXIOM_REGISTRY = []


def axiom(func: Callable) -> Callable:
    """
    Decorator to mark a function as an axiom.

    The marked function is not intended to be executed in a standard python environment.

    The arguments to the function are treated as universally quantified variables

    Example usage:

        from dataclasses import dataclass
        from typedlogic import Fact
        from typedlogic.decorators import axiom, goal

        @dataclass
        class Dog(Fact):
            unique_name: str

        @dataclass
        class Cat(Fact):
            unique_name: str

        @axiom
        def disjointness(n: str):
            '''nothing is both a dog and a cat'''
            assert not(Dog(n) and Cat(n))

    The arguments of the wrapped functions are treated as universal quantifiers (Forall x: ...)

    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    AXIOM_REGISTRY.append(func)
    return wrapper


def goal(func: Callable) -> Callable:
    """
    Decorator to mark a function as a goal.

    The `prove_goals` function in a Solver object will attempt to prove the goal.

    The function is not intended to be called directly, but rather to be interpreted
    using logical semantics.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    # AXIOM_REGISTRY.append(func)
    return wrapper


def predicate(cls=None, *, exclude_from_hash=None, **kwargs):
    if exclude_from_hash is None:
        exclude_from_hash = []

    def wrapper(cls):
        if not issubclass(cls, FactMixin):
            cls = type(cls.__name__, (cls, FactMixin), dict(cls.__dict__))

        # Apply the dataclass decorator with eq=True and unsafe_hash=True
        cls = dataclass(eq=True, frozen=True, **kwargs)(cls)

        # Store original __hash__ and __eq__ methods
        original_hash = cls.__hash__
        original_eq = cls.__eq__

        def custom_hash(self):
            return hash(
                tuple(getattr(self, f.name) for f in fields(self) if f.name not in exclude_from_hash and f.compare)
            )

        def custom_eq(self, other):
            if not isinstance(other, self.__class__):
                return NotImplemented
            return all(
                getattr(self, f.name) == getattr(other, f.name)
                for f in fields(self)
                if f.name not in exclude_from_hash and f.compare
            )

        cls.__hash__ = custom_hash
        cls.__eq__ = custom_eq

        original_init = cls.__init__

        @wraps(original_init)
        def custom_init(*args, **kwargs):
            instance = original_init(*args, **kwargs)
            print(f"Predicate class created: {instance}")
            return instance

        cls.__init__ = custom_init

        return cls

    return wrapper if cls is None else wrapper(cls)
