from random import randint
from typing import List

import pytest
from typedlogic import Sentence
from typedlogic.evaluation import Benchmark, BenchmarkSeed, benchmark_from_seed
from typedlogic.parsers.pyparser import PythonParser

from tests import tree_edges


@pytest.fixture
def path_benchmark() -> Benchmark:
    return _path_benchmark(depth=3)


@pytest.fixture
def path_benchmark_d4() -> Benchmark:
    return _path_benchmark(depth=4)


@pytest.fixture
def path_benchmark_d5() -> Benchmark:
    return _path_benchmark(depth=5)


def _path_benchmark(depth=3) -> Benchmark:
    from tests.theorems import paths

    parser = PythonParser()
    theory = parser.parse(paths)
    print("Parsed theory")
    ground_terms: List[Sentence] = []
    seed = BenchmarkSeed(
        theory=theory,
    )
    entities = set()
    for source, target in tree_edges("a", depth, 3):
        ground_terms.append(paths.Link(source=source, target=target))
        entities.update({source, target})
    seed.ground_terms = ground_terms
    entities_l = list(entities)

    def rand_entity() -> str:
        return entities_l[randint(0, len(entities_l) - 1)]

    candidate_goals: List[Sentence] = []
    for n in range(0, 20):
        candidate_goals.append(paths.Path(source=rand_entity(), target=rand_entity()))
    seed.candidate_goals = candidate_goals
    benchmark = benchmark_from_seed(seed)
    benchmark.entities = entities_l
    return benchmark
