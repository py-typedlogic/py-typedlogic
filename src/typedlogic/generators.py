"""
Generators can be used to create universally quantified variables in a way
that preserves type safety.

Example:
-------
```python

TreeNodeType = str

class AncestorOf(BaseModel, Fact):
    ancestor: TreeNodeType
    descendant: TreeNodeType

@axiom
def ancestor_transitivity_axiom() -> bool:
    '''For all x,y,z, if AncestorOf(x,z) and AncestorOf(z,y), then AncestorOf(x,y)'''
    return all(
        AncestorOf(ancestor=x, descendant=y)
        for x, y, z in gen3(TreeNodeType, TreeNodeType, TreeNodeType)
        if AncestorOf(ancestor=x, descendant=z) and AncestorOf(ancestor=z, descendant=y)
    )
```

The above axiom defines a universally quantified statement over the variables x, y, and z, whose
range is all strings.

Note that while the semantics of the above program are consistent with Python semantics,
actually executing the above code would take infinite time as there are infinite strings.
Instead, the python is treated as a logical specification.

Composable Generators:
----------------------
You can also use the composable `Gen` class to define generators with type-safe composition:

```python
@axiom
def ancestor_transitivity_axiom() -> bool:
    '''For all x,y,z, if AncestorOf(x,z) and AncestorOf(z,y), then AncestorOf(x,y)'''
    return all(
        AncestorOf(ancestor=x, descendant=y)
        for x, y, z in Gen(TreeNodeType) * Gen(TreeNodeType) * Gen(TreeNodeType)
        if AncestorOf(ancestor=x, descendant=z) and AncestorOf(ancestor=z, descendant=y)
    )
```

The `*` operator creates a cartesian product of generators, maintaining type information
for the parser.

"""
from itertools import islice
from typing import Any, Callable, Generator, Generic, Iterator, List, Tuple, Type, TypeVar, Union

T = TypeVar("T")
T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")
U = TypeVar("U")


def gen(*types: Type[Any]) -> Generator[Tuple[Any, ...], None, None]:
    """
    A generator that yields tuples of values of the specified types.

    Note: this is more weakly typed than the arity-specific :ref:`gen1`, :ref:`gen2`, and :ref:`gen3` functions.

    .. note:: These are generally used in defining axioms using python syntax, rather than executed directly.

    :param types:
    :return:
    """
    while True:
        yield tuple(t() for t in types)  # Replace with actual logic


def gen1(type1: Type[T1]) -> Generator[T1, None, None]:
    """
    A generator that yields individual values of the specified type.

    .. note:: This is generally used in defining axioms using python syntax, rather than executed directly.

    :param type1:
    :return:
    """
    while True:
        yield type1()  # R


def gen2(type1: Type[T1], type2: Type[T2]) -> Generator[Tuple[T1, T2], None, None]:
    """
    A generator that yields arity 2 tuples of values of the specified types.

    .. note:: This is generally used in defining axioms using python syntax, rather than executed directly.

    :param type1:
    :param type2:
    :return:
    """
    while True:
        yield type1(), type2()  # Replace with actual logic


def gen3(type1: Type[T1], type2: Type[T2], type3: Type[T3]) -> Generator[Tuple[T1, T2, T3], None, None]:
    """
    A generator that yields arity 3 tuples of values of the specified types.

    .. note:: This is generally used in defining axioms using python syntax, rather than executed directly.

    :param type1:
    :param type2:
    :param type3:
    :return:
    """
    while True:
        yield type1(), type2(), type3()  # Replace with actual logic


class Gen(Generic[T]):
    """
    A composable generator with type signatures for logical specifications.

    This class enables creating type-safe, composable generators that can be combined
    using operators like `*` (cartesian product) and `+` (interleaving).

    .. note:: Like the gen1/gen2/gen3 functions, Gen is used for logical specifications
              and is parsed by the AST parser rather than executed directly.

    Example:
    --------
    ```python
    @axiom
    def my_axiom() -> bool:
        return all(
            P(x, y, z)
            for x, y, z in Gen(str) * Gen(int) * Gen(float)
            if Q(x, y)
        )
    ```

    :param type_or_factory: Either a type (for logical specifications) or a callable
                            that returns an iterator (for runtime execution)
    """

    def __init__(
        self,
        type_or_factory: Union[Type[T], Callable[[], Iterator[T]]],
    ):
        """
        Initialize a generator.

        :param type_or_factory: Either a Type for specification purposes, or a callable
                                that returns an iterator for runtime execution
        """
        if isinstance(type_or_factory, type):
            # Store the type for AST parsing
            self._type: Type[T] = type_or_factory
            self._types: Tuple[Type[Any], ...] = (type_or_factory,)
            # Create a simple factory that instantiates the type
            self._factory: Callable[[], Iterator[T]] = lambda: self._infinite_type_iter(type_or_factory)
        else:
            # It's a factory function
            self._type = None  # type: ignore[assignment]
            self._types = ()
            self._factory = type_or_factory

    @staticmethod
    def _infinite_type_iter(t: Type[T]) -> Iterator[T]:
        """Generate infinite instances of a type (for specification purposes)."""
        while True:
            yield t()

    @property
    def types(self) -> Tuple[Type[Any], ...]:
        """Return the tuple of types this generator produces."""
        return self._types

    def __iter__(self) -> Iterator[T]:
        """Return a fresh iterator."""
        return self._factory()

    def __mul__(self, other: "Gen[U]") -> "Gen[Tuple[T, U]]":
        """
        Combine two generators to produce a cartesian product.

        The result flattens nested tuples so that `Gen(A) * Gen(B) * Gen(C)` yields
        `(a, b, c)` rather than `((a, b), c)`.

        Example:
        --------
        ```python
        Gen(int) * Gen(str)  # produces Iterator[Tuple[int, str]]
        Gen(int) * Gen(str) * Gen(float)  # produces Iterator[Tuple[int, str, float]]
        ```

        :param other: Another Gen to combine with
        :return: A new Gen producing tuples from the cartesian product
        """

        def combined() -> Iterator[Tuple[Any, ...]]:
            for left in self:
                for right in other:
                    # Flatten: if left is already a tuple from a previous *, extend it
                    if isinstance(left, tuple):
                        yield (*left, right)
                    else:
                        yield (left, right)

        result: Gen[Tuple[T, U]] = Gen(combined)  # type: ignore[arg-type]
        # Combine types from both generators
        result._types = self._types + other._types
        return result

    def __add__(self, other: "Gen[T]") -> "Gen[T]":
        """
        Interleave two generators.

        Elements are yielded alternating from each generator until one is exhausted,
        then remaining elements from the other generator are yielded.

        Example:
        --------
        ```python
        gen1 + gen2  # produces elements alternating from both
        ```

        :param other: Another Gen to interleave with
        :return: A new Gen with interleaved elements
        """

        def combined() -> Iterator[T]:
            iter1, iter2 = iter(self), iter(other)
            while True:
                try:
                    yield next(iter1)
                except StopIteration:
                    yield from iter2
                    break
                try:
                    yield next(iter2)
                except StopIteration:
                    yield from iter1
                    break

        result = Gen(combined)  # type: ignore[arg-type]
        result._types = self._types  # Keep same types (assuming same type for +)
        return result

    def map(self, f: Callable[[T], U]) -> "Gen[U]":
        """
        Apply a function to each element.

        :param f: A function to apply to each element
        :return: A new Gen with the function applied
        """

        def mapped() -> Iterator[U]:
            return (f(x) for x in self)

        result = Gen(mapped)  # type: ignore[arg-type]
        return result

    def filter(self, predicate: Callable[[T], bool]) -> "Gen[T]":
        """
        Filter elements by a predicate.

        :param predicate: A function returning True for elements to keep
        :return: A new Gen with only matching elements
        """

        def filtered() -> Iterator[T]:
            return (x for x in self if predicate(x))

        result: Gen[T] = Gen(filtered)  # type: ignore[arg-type]
        result._types = self._types
        return result

    def take(self, n: int) -> "Gen[T]":
        """
        Take first n elements.

        :param n: Number of elements to take
        :return: A new Gen yielding at most n elements
        """

        def limited() -> Iterator[T]:
            return islice(self, n)

        result: Gen[T] = Gen(limited)  # type: ignore[arg-type]
        result._types = self._types
        return result

    def __repr__(self) -> str:
        if self._types:
            type_names = ", ".join(t.__name__ if hasattr(t, "__name__") else str(t) for t in self._types)
            return f"Gen({type_names})"
        return "Gen(<factory>)"


def gen_range(start: int, end: int) -> Gen[int]:
    """
    Generate integers in a range [start, end).

    :param start: Start of range (inclusive)
    :param end: End of range (exclusive)
    :return: A Gen yielding integers in the range
    """
    return Gen(lambda: iter(range(start, end)))


def gen_list(items: List[T]) -> Gen[T]:
    """
    Generate from a list (cycles through it infinitely).

    :param items: List of items to cycle through
    :return: A Gen yielding items from the list
    """

    def factory() -> Iterator[T]:
        if not items:
            return
        while True:
            yield from items

    return Gen(factory)


def gen_const(value: T) -> Gen[T]:
    """
    Generate the same value infinitely.

    :param value: The value to yield
    :return: A Gen yielding the value infinitely
    """

    def factory() -> Iterator[T]:
        while True:
            yield value

    return Gen(factory)


def gen_product(*gens: Gen[Any]) -> Gen[Tuple[Any, ...]]:
    """
    Combine N generators into a single generator of tuples (cartesian product).

    This is a helper function that combines multiple generators using the `*` operator.

    Example:
    --------
    ```python
    gen_product(Gen(int), Gen(str), Gen(float))
    # equivalent to: Gen(int) * Gen(str) * Gen(float)
    ```

    :param gens: Variable number of Gen instances
    :return: A Gen producing tuples from the cartesian product
    """
    if not gens:
        return Gen(lambda: iter([()]))

    result = gens[0]
    for g in gens[1:]:
        result = result * g

    return result  # type: ignore[return-value]
