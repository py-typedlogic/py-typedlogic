from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class Node:
    name: str
    positive_edges: Set[str] = field(default_factory=set)
    negative_edges: Set[str] = field(default_factory=set)
    index: int = -1
    lowlink: int = -1
    on_stack: bool = False


@dataclass
class Graph:
    nodes: Dict[str, Node] = field(default_factory=dict)
    stack: List[Node] = field(default_factory=list)
    index: int = 0
    sccs: List[List[str]] = field(default_factory=list)

    def add_edge(self, u: str, v: str, is_negative: bool = False) -> None:
        if u not in self.nodes:
            self.nodes[u] = Node(u)
        if v not in self.nodes:
            self.nodes[v] = Node(v)
        if is_negative:
            self.nodes[u].negative_edges.add(v)
        else:
            self.nodes[u].positive_edges.add(v)

    def tarjan(self) -> List[List[str]]:
        for node in self.nodes.values():
            if node.index == -1:
                self._strong_connect(node)
        return self.sccs

    def _strong_connect(self, v: Node) -> None:
        v.index = self.index
        v.lowlink = self.index
        self.index += 1
        self.stack.append(v)
        v.on_stack = True

        for w_name in v.positive_edges.union(v.negative_edges):
            w = self.nodes[w_name]
            if w.index == -1:
                self._strong_connect(w)
                v.lowlink = min(v.lowlink, w.lowlink)
            elif w.on_stack:
                v.lowlink = min(v.lowlink, w.index)

        if v.lowlink == v.index:
            scc = []
            while True:
                w = self.stack.pop()
                w.on_stack = False
                scc.append(w.name)
                if w == v:
                    break
            self.sccs.append(scc)

    def is_stratified(self) -> Tuple[bool, Optional[Tuple[str, str]]]:
        """
        Determine if the Datalog program represented by this graph is stratified.

        A Datalog program is stratified if there are no negative edges between
        predicates within the same strongly connected component (SCC).

        The method works as follows:
        1. Create a mapping from each node to its SCC index.
        2. For each node in the graph:
           a. Find its SCC index.
           b. Check all its negative edges.
           c. If any negative edge points to a node in the same SCC,
              the program is not stratified.

        Returns
        -------
            bool: True if the program is stratified, False otherwise.

        Time complexity: O(N + E), where N is the number of nodes and E is the
        total number of edges (positive and negative) in the graph.

        """
        scc_map = {node: scc_index for scc_index, scc in enumerate(self.sccs) for node in scc}
        for node_name, node in self.nodes.items():
            scc_index = scc_map[node_name]
            for neg_edge in node.negative_edges:
                if scc_map[neg_edge] == scc_index:
                    return False, (node_name, neg_edge)  # Negative edge within the same SCC
        return True, None


def analyze_datalog_program(
    rules: List[Tuple[str, List[Tuple[str, bool]]]]
) -> Tuple[bool, Optional[Tuple[str, str]], List[List[str]]]:
    """
    Analyze a Datalog program for stratification using Tarjan's algorithm.

    Args:
    ----
    rules (List[Tuple[str, List[Tuple[str, bool]]]]): A list of rules, where each rule is represented
        as (head, [(body_pred1, is_negative1), (body_pred2, is_negative2), ...])

    Returns:
    -------
    Tuple[bool, List[List[str]]]: A tuple containing:
        - Boolean indicating whether the program is stratified
        - List of strongly connected components

    Example:
    -------
    >>> rules = [
    ...     ('p', [('q', False), ('r', True)]),  # p depends on q (positive) and r (negative)
    ...     ('q', [('s', False)]),               # q depends on s
    ...     ('r', [('t', False)]),               # r depends on t
    ...     ('s', [('p', False)]),               # s depends on p
    ...     ('t', [('u', False)])                # t depends on u
    ... ]
    >>> is_stratified, _, sccs = analyze_datalog_program(rules)
    >>> is_stratified
    True
    >>> sorted(map(sorted, sccs))  # SCCs might be in different order, so we sort them
    [['p', 'q', 's'], ['r'], ['t'], ['u']]

    Example 2 (Non-Stratified Program):
    >>> non_stratified_rules = [
    ...     ('p', [('q', False), ('r', True)]),  # p depends on q (positive) and r (negative)
    ...     ('q', [('s', False)]),               # q depends on s
    ...     ('r', [('p', False)]),               # r depends on p (creating a cycle with negative edge)
    ...     ('s', [('p', False)])                # s depends on p
    ... ]
    >>> is_stratified, e, sccs = analyze_datalog_program(non_stratified_rules)
    >>> is_stratified
    False
    >>> e
    ('p', 'r')

    """
    g = Graph()
    for head, body in rules:
        for pred, is_negative in body:
            g.add_edge(head, pred, is_negative)

    sccs = g.tarjan()
    is_stratified, causal_edge = g.is_stratified()

    return is_stratified, causal_edge, sccs
