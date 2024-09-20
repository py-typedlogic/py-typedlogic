from random import randint
from typing import List

from typedlogic import Sentence, Term
from typedlogic.integrations.frameworks.owldl import IRI, TopObjectProperty

from tests import tree_edges


class Path(TopObjectProperty):
    """A direct or indirect connection between two things"""

    transitive = True
    asymmetric = True

class Link(Path):
    """A direct connection between two things"""

    # NOTE: this is necessary because classvars are inherited
    transitive = False

def generate_ontology(*args, **kwargs) -> List[Sentence]:
    links: List[Sentence] = [Link(*e) for e in tree_edges(*args, **kwargs)]
    return links

def generate_benchmark_seed(*args, num_candidates=100, **kwargs):
    links = generate_ontology(*args, **kwargs)
    entities = set()
    for link in links:
        if isinstance(link, Term):
            entities.update(link.values)
    candidates = []
    def random_entity() -> IRI:
        return list(entities)[randint(0, len(candidates))]
    for i in range(0, num_candidates):
        candidates.append(Path(random_entity(), random_entity()))

