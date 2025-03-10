"""Tests for typedlogic."""
from importlib.util import find_spec
from pathlib import Path
from random import randint
from typing import Iterable, Tuple

import pytest

TESTS_DIR = Path(__file__).parent
TEST_THEOREMS_DIR = TESTS_DIR / "theorems"
INPUT_DIR = TESTS_DIR / "input"
OUTPUT_DIR = TESTS_DIR / "output"
SNAPSHOTS_DIR = TESTS_DIR / "__snapshots__"


def tree_edges(
    node: str, depth: int, num_children: int = 3, depth_variance=0, num_children_variance=0
) -> Iterable[Tuple[str, str]]:
    """
    Generate parent-child tuples for trees of different shapes

    TODO: this should move to individual theories

    :param node:
    :param depth:
    :param num_children:
    :return:
    """
    if depth <= 0 + randint(-depth_variance, depth_variance):
        return
    for i in range(num_children + randint(-num_children_variance, num_children_variance)):
        child = f"{node}.{i}"
        yield node, child
        yield from tree_edges(child, depth - 1, num_children)


def skip_if_extra_not_installed(extra_name):
    def decorator(func):
        try:
            # Try to find the module
            if find_spec(extra_name) is None:
                return pytest.mark.skip(reason=f"Extra '{extra_name}' is not installed")(func)
        except ImportError:
            return pytest.mark.skip(reason=f"Extra '{extra_name}' is not installed")(func)
        return func

    return decorator


def requires_extra(extra_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                # Attempt to import the module
                __import__(extra_name)
            except ImportError:
                pytest.skip(f"Test requires the '{extra_name}' extra to be installed")
            return func(*args, **kwargs)

        return wrapper

    return decorator
