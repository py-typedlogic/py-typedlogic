"""
Generators can be used to create universally quantified variables in a way
that preserves type safety.

Example:

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
"""
from typing import TypeVar, Type, Any, Generator, Tuple

T = TypeVar('T')
T1 = TypeVar('T1')
T2 = TypeVar('T2')
T3 = TypeVar('T3')


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
