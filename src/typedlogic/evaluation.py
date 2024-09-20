import hashlib
import random
import timeit
from dataclasses import dataclass
from typing import Optional, List, Any, Type, Callable, Dict, Union, Iterator


from typedlogic import Theory, Sentence, Term, NegationAsFailure, Variable
from typedlogic.datamodel import Extension
from typedlogic.integrations.solvers.clingo import ClingoSolver
from typedlogic.solver import Solver
from typedlogic.transformations import transform_sentence


@dataclass
class Benchmark:
    theory: Optional[Theory] = None
    ground_terms: Optional[List[Sentence]] = None
    goals: Optional[List[Sentence]] = None
    entities: Optional[List[Any]] = None
    entity_mapping: Optional[Dict[Any, Any]] = None


@dataclass
class BenchmarkSeed:
    theory: Theory
    ground_terms: Optional[List[Sentence]] = None
    candidate_goals: Optional[List[Sentence]] = None


@dataclass
class BenchmarkResult:
    benchmark: Benchmark
    solver_class_name: str
    score: float
    elapsed: float



def benchmark_from_seed(seed: BenchmarkSeed, benchmark_solver_class: Type[Solver] = ClingoSolver, num_positive=10, num_negative=10) -> Benchmark:
    benchmark = Benchmark(
        theory=seed.theory,
        ground_terms=seed.ground_terms,
    )
    if not seed.candidate_goals:
        raise ValueError("No candidate goals provided")
    candidate_goals = [t.to_model_object() if isinstance(t, Extension) else t for t in seed.candidate_goals]
    predicates = {t.predicate for t in candidate_goals if isinstance(t, Term)}
    if not predicates:
        raise ValueError(f"No predicates from {candidate_goals}")
    solver = benchmark_solver_class()
    solver.add(seed.theory)
    if not seed.ground_terms:
        raise ValueError("No ground terms provided")
    for t in seed.ground_terms:
        solver.add(t)
    #print(solver.base_theory)
    model = solver.model()
    if not model.ground_terms:
        raise ValueError(f"Solver {benchmark_solver_class} model has no ground terms for {predicates}")
    provable = []
    for p in predicates:
        #print(f"Querying: {p}")
        for t in model.iter_retrieve(p):
            provable.append(t)
    if not provable:
        raise ValueError(f"Solver {benchmark_solver_class} unable to find solutions for {predicates}")
    # take a random subsample of provable goals
    if len(provable) < num_positive:
        raise ValueError(f"Num provable = {len(provable)} < {num_positive}")
    goals: List[Sentence] = random.sample(provable, num_positive)
    random.shuffle(candidate_goals)
    n = 0
    for cg in candidate_goals:
        if cg not in provable:
            goals.append(NegationAsFailure(cg))
            n += 1
            if n >= num_negative:
                break
    random.shuffle(goals)
    benchmark.goals = goals
    return benchmark


def run_benchmark(benchmark: Benchmark, solver_class: Union[Solver, Type[Solver]]) -> BenchmarkResult:
    if isinstance(solver_class, Solver):
        solver: Solver = solver_class
        solver_class = type(solver)
    else:
        solver = solver_class()
    if not isinstance(solver, Solver):
        raise ValueError(f"Unexpected: {solver}")
    if not benchmark.theory:
        raise ValueError
    solver.add(benchmark.theory)
    for f in benchmark.ground_terms or []:
        solver.add(f.to_model_object() if isinstance(f, Extension) else f)
    start_time = timeit.default_timer()
    tps = 0
    goal_pairs = []
    goal_truths = {}
    if not benchmark.goals:
        raise ValueError
    for g in benchmark.goals or []:
        negative = False
        if isinstance(g, NegationAsFailure):
            negative = True
            g = g.negated
        goal_pairs.append((g, negative))
        goal_truths[str(repr(g))] = negative
    results = solver.prove_multiple([gp[0] for gp in goal_pairs])
    for g, is_proven in results:
        #[(_, negative)] = [gp for gp in goal_pairs if gp[0] == g]
        negative = goal_truths[str(repr(g))]
        correct = is_proven != negative
        if correct:
            tps += 1
    end_time = timeit.default_timer()
    total_time = end_time - start_time
    return BenchmarkResult(
        benchmark=benchmark,
        solver_class_name=solver_class.__name__,
        score=tps / len(benchmark.goals),
        elapsed=total_time,
    )


def run_benchmark_matrix(benchmarks: List[Benchmark], solver_classes: List[Union[Solver, Type[Solver]]]) -> Iterator[BenchmarkResult]:
    """
    Run a matrix of benchmarks against a matrix of solvers.

    :param benchmarks:
    :param solver_class:
    :return:
    """
    for benchmark in benchmarks:
        for solver_class in solver_classes:
            yield run_benchmark(benchmark, solver_class)


def create_random_id_function(prefix: str, max_id=10000) -> Callable[[], str]:
    """
    Create a function that generates random ids.

    :param prefix:
    :param max_id:
    :return:
    """
    unallocated = set(range(max_id))
    def assign(*args):
        nonlocal unallocated
        next_id = random.choice(list(unallocated))
        unallocated.remove(next_id)
        return f"{prefix}{next_id}"
    return assign

def randomize_entity_names(benchmark: Benchmark, mapping_func: Optional[Callable] = None):
    if mapping_func is None:
        mapping_func = lambda x: hashlib.md5(str(x).encode('utf-8')).hexdigest()
    emap = {}
    if not benchmark.entities:
        raise ValueError
    for e in benchmark.entities:
        emap[e] = mapping_func(e)
    def rewire_term(s: Sentence) -> Sentence:
        if isinstance(s, Extension):
            s = s.to_model_object()
        if isinstance(s, Term):
            return Term(s.predicate, *[emap[a] if not isinstance(a, Variable) and a in emap else a for a in s.values])
        return s
    benchmark.ground_terms = [transform_sentence(t, rewire_term) for t in benchmark.ground_terms or []]
    benchmark.goals = [transform_sentence(t, rewire_term) for t in benchmark.goals or []]
    benchmark.entity_mapping = emap


