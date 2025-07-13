from dataclasses import dataclass, field
from typing import Dict, Iterator, Tuple, List, Type, Union

from typedlogic import Term, Sentence, Fact
from typedlogic.solver import Model


@dataclass(frozen=True)
class That(Fact):
    sentence: Sentence


@dataclass(frozen=True)
class Probability(Fact):
    probability: float
    that: That


@dataclass(frozen=True)
class Evidence(Fact):
    that: Sentence
    truth_value: bool


def probability(sentence: Sentence) -> float:
    raise NotImplementedError


@dataclass
class ProbabilisticModel(Model):
    """
    An extension of a stable model that includes probabilities.
    """

    term_probabilities: Dict[Term, float] = field(default_factory=dict)

    def retrieve_probabilities(self, predicate: Union[str, Type[Term]], *args) -> List[Tuple[Term, float]]:
        return list(self.iter_retrieve_probabilities(predicate, *args))

    def iter_retrieve_probabilities(self, predicate: Union[str, Type[Term]], *args) -> Iterator[Tuple[Term, float]]:
        if not isinstance(predicate, str):
            predicate = predicate.__name__
        for t, pr in self.term_probabilities.items():
            if t.predicate != predicate:
                continue
            if args:
                is_match = True
                for i in range(len(args)):
                    if args[i] is None:
                        continue
                    if args[i] != t.values[i]:
                        is_match = False
                        break
                if not is_match:
                    continue
            yield t, pr
