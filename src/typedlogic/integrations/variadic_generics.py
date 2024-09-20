"""
from typing import Generator, Tuple, Type, TypeVar, TypeVarTuple

class GenVar(Generic[T]):
    def __init__(self, typ: Type[T]):
        self.type = typ


Ts = TypeVarTuple('Ts')

def gen(*types: Tuple[Type[*Ts]]) -> Generator[Tuple[*Ts], None, None]:
    while True:
        yield tuple(t() for t in types)  # Replace with actual logic

# Usage example
for x, y, z in gen(str, int, float):
    print(x, y, z)  # x is recognized as str, y as int, z as float
"""
