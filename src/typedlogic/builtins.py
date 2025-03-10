"""
Mappings for builtin functions and datatypes.
"""
import operator as op
from typing import Callable, Mapping

NUMERIC_BUILTINS: Mapping[str, Callable] = {
    "ge": op.ge,
    "gt": op.gt,
    "le": op.le,
    "lt": op.lt,
    "eq": op.eq,
    "ne": op.ne,
    "add": op.add,
    "sub": op.sub,
    "mul": op.mul,
    "truediv": op.truediv,
    "pow": op.pow,
    "xor": op.xor,
    "neg": op.neg,
}

NAME_TO_INFIX_OP: Mapping[str, str] = {
    "add": "+",
    "sub": "-",
    "mul": "*",
    "truediv": "/",
    "floordiv": "//",
    "mod": "%",
    "pow": "**",
    "lshift": "<<",
    "rshift": ">>",
    "or": "|",
    "xor": "^",
    "and": "&",
    "matmul": "@",
    # Comparison operators
    "eq": "==",
    "ne": "!=",
    "lt": "<",
    "le": "<=",
    "gt": ">",
    "ge": ">=",
    "is": "is",
    "is_not": "is not",
    "in": "in",
    "not_in": "not in",
}
