"""Tests for typedlogic."""
from pathlib import Path
from random import randint
from typing import Iterable, Tuple

TESTS_DIR = Path(__file__).parent
INPUT_DIR = TESTS_DIR / "input"
OUTPUT_DIR = TESTS_DIR / "output"
SNAPSHOTS_DIR = TESTS_DIR / "__snapshots__"


def tree_edges(node: str, depth: int, num_children: int = 3, depth_variance = 0, num_children_variance = 0) -> Iterable[Tuple[str, str]]:
    """
    Generate parent-child tuples for trees of different shapes

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
        yield from tree_edges(child, depth-1, num_children)
