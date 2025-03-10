"""
EXPERIMENT: see https://ericpony.github.io/z3py-tutorial/fixpoint-examples.htm

If this can be made more efficient we can generalize to a solver;
however it appears to be much slower than Souffle or SnakeLog
"""

import pytest
from z3 import *

from tests import tree_edges


@pytest.mark.parametrize(
    "depth,num_children,expected",
    [
        (1, 2, 4),
        (2, 2, 16),
        # (5, 2, 320),
        # (5, 3, 2004),
        # (7, 3, 24603),
    ],
)
def test_paths(depth, num_children, expected):
    fp = Fixedpoint()
    fp.set(engine="datalog")

    s = BitVecSort(16)
    edge = Function("edge", s, s, BoolSort())
    path = Function("path", s, s, BoolSort())
    a = Const("a", s)
    b = Const("b", s)
    c = Const("c", s)

    fp.register_relation(path, edge)
    fp.declare_var(a, b, c)
    fp.rule(path(a, b), edge(a, b))
    fp.rule(path(a, c), [edge(a, b), path(b, c)])

    pairs = list(tree_edges("a", depth, num_children))

    node_ids = set()
    for source, target in pairs:
        node_ids.add(source)
        node_ids.add(target)

    node_map = {}
    for ix, node_id in enumerate(node_ids):
        v = BitVecVal(ix + 1, s)
        node_map[node_id] = v
        print(f" Assigning {ix} {node_id} = {v}")

    # v1 = BitVecVal(1, s)
    # v2 = BitVecVal(2, s)
    # v3 = BitVecVal(3, s)
    # v4 = BitVecVal(4, s)

    for source, target in pairs:
        print(f"Adding edge {source} -> {target} [{node_map[source]} -> {node_map[target]}]")
        fp.fact(edge(node_map[source], node_map[target]))

    print("current set of rules", fp)

    total = 0
    for n1, n1v in node_map.items():
        for n2, n2v in node_map.items():
            if n1 != n2:
                result = fp.query(path(n1v, n2v))
                has_path = result != unsat
                if has_path:
                    total += 1
                    print(f"{n1} x {n2} = {has_path}")
                result = fp.query(edge(n1v, n2v))
                has_edge = result != unsat
                if has_edge:
                    total += 1
                    print(f"{n1} x {n2} = {has_edge}")
    assert total == expected
