from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Node:
    id: int
    edges: List[int] = field(default_factory=list)
    index: int = -1
    lowlink: int = -1
    on_stack: bool = False


@dataclass
class Graph:
    nodes: Dict[int, Node] = field(default_factory=dict)
    stack: List[Node] = field(default_factory=list)
    index: int = 0
    sccs: List[List[int]] = field(default_factory=list)

    def add_edge(self, u: int, v: int) -> None:
        if u not in self.nodes:
            self.nodes[u] = Node(u)
        if v not in self.nodes:
            self.nodes[v] = Node(v)
        self.nodes[u].edges.append(v)

    def tarjan(self) -> List[List[int]]:
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

        for w_id in v.edges:
            w = self.nodes[w_id]
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
                scc.append(w.id)
                if w == v:
                    break
            self.sccs.append(scc)


def main():
    g = Graph()
    edges = [(0, 1), (1, 2), (2, 0), (1, 3), (3, 4), (4, 3)]
    for u, v in edges:
        g.add_edge(u, v)

    sccs = g.tarjan()
    print("Strongly Connected Components:")
    for i, scc in enumerate(sccs, 1):
        print(f"SCC {i}: {scc}")


if __name__ == "__main__":
    main()
