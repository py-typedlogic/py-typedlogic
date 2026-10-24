import math
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Tuple, Type, Union

from typedlogic import Fact, Sentence, Term
from typedlogic.solver import Model


def validate_probability(value: object) -> None:
    """Reject nonnumeric, nonfinite, or out-of-range probability annotations."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not 0 <= value <= 1
        or not math.isfinite(value)
    ):
        raise ValueError(f"Probability must be a finite number in [0, 1], got {value!r}")


@dataclass(frozen=True)
class That(Fact):
    sentence: Sentence


@dataclass(frozen=True)
class Probability(Fact):
    probability: float
    that: That

    def __post_init__(self) -> None:
        """Validate probabilities before they enter a theory."""
        validate_probability(self.probability)


@dataclass(frozen=True)
class Evidence(Fact):
    that: Sentence
    truth_value: bool

    def __post_init__(self) -> None:
        """Require an actual Boolean, rather than Python truthiness."""
        if not isinstance(self.truth_value, bool):
            raise ValueError(f"Evidence truth_value must be bool, got {self.truth_value!r}")


@dataclass(frozen=True)
class AnnotatedDisjunction(Fact):
    """
    Mutually exclusive weighted atomic heads, optionally conditional on a body.

    ``alternatives`` contains ``(probability, atom)`` pairs. Probabilities sum to at
    most one; unused probability means none of the heads holds from this choice.
    This is not equivalent to separate independent ``Probability`` facts.
    """

    alternatives: Tuple[Tuple[float, Sentence], ...]
    body: Union[Sentence, None] = None


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
