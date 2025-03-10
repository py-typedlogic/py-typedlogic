from abc import ABC
from dataclasses import dataclass, field
from typing import ClassVar, Optional, Set, Tuple, Type


class Profile(ABC):
    """A profile of FOL"""

    disjoint_profiles: ClassVar[Set[Type["Profile"]]] = set()

    def impl(self, profile: Type["Profile"]) -> bool:
        """
        True if self is an implementation of profile.

        Operates under NAF: if it cannot be proven that self is an implementation of profile, it returns None.

        >>> p = WellFoundedSemantics()
        >>> p.impl(WellFoundedSemantics)
        True
        >>> p.impl(ClosedWorld)
        True
        >>> p.impl(OpenWorld)
        False

        """
        return isinstance(self, profile)

    def not_impl(self, profile: Type["Profile"]) -> Optional[bool]:
        """
        True if self is provably not an implementation of profile

        >>> p = WellFoundedSemantics()
        >>> p.not_impl(WellFoundedSemantics)
        False
        >>> p.impl(ClosedWorld)
        True
        >>> p.not_impl(ClosedWorld)
        False
        >>> p.not_impl(OpenWorld)
        True
        >>> assert p.not_impl(SortedLogic) is None

        """
        if self.impl(profile):
            return False
        disjoints = profile.disjoint_profiles
        if disjoints and any(isinstance(self, p) for p in disjoints):
            return True
        this_disjoints = type(self).disjoint_profiles
        if this_disjoints and any(issubclass(profile, p) for p in this_disjoints):
            return True
        return None


@dataclass
class MixedProfile(Profile):
    """
    A profile that mixes multiple profiles.md

    >>> p = MixedProfile(Unrestricted(), SortedLogic())
    >>> p.impl(Unrestricted)
    True
    >>> p.impl(SortedLogic)
    True

    """

    profiles: Tuple = field(default_factory=tuple)

    def __init__(self, *profiles: Profile):
        self.profiles = profiles

    def impl(self, profile: Type["Profile"]) -> bool:
        return isinstance(self, profile) or any(p.impl(profile) for p in self.profiles)

    def not_impl(self, profile: Type["Profile"]) -> Optional[bool]:
        provably_not_impl = any(p.not_impl(profile) for p in self.profiles)
        provable_impl = any(p.impl(profile) for p in self.profiles)
        if provable_impl and provably_not_impl:
            raise ValueError(
                f"Inconsistent profiles.md: {self} is both an implementation and not an implementation of {profile}"
            )
        return provably_not_impl


@dataclass
class ExcludedProfile(Profile):
    """
    A profile that excludes other profiles.md

    >>> p = ExcludedProfile(WellFoundedSemantics())
    >>> p.impl(WellFoundedSemantics)
    False
    >>> p.not_impl(WellFoundedSemantics)
    True

    >>> p = MixedProfile(Unrestricted(), SortedLogic(), ExcludedProfile(PropositionalLogic()))
    >>> p.impl(Unrestricted)
    True
    >>> p.impl(PropositionalLogic)
    False
    >>> p.not_impl(PropositionalLogic)
    True

    """

    profile: Profile

    def impl(self, profile: Type["Profile"]) -> bool:
        """True if self is an implementation of profile"""
        if self.profile.impl(profile):
            return False
        return super().impl(profile)

    def not_impl(self, profile: Type["Profile"]) -> Optional[bool]:
        """True if self is not an implementation of profile"""
        if isinstance(self.profile, profile):
            return True
        return super().not_impl(profile)


class ComputationalProfile(Profile, ABC):
    """A profile that describes the computational properties of a logic"""


class Decidable(ComputationalProfile):
    """The logic is decidable"""


class Undecidable(ComputationalProfile):
    """The logic is undecidable"""


class LogicalFeature(Profile, ABC):
    """A profile grouping corresponding to a feature of logic"""


class NegationLogic(LogicalFeature):
    """The logic has negation"""


class DisjunctionLogic(LogicalFeature):
    """The logic has disjunction"""


class ConjunctionLogic(LogicalFeature):
    """The logic has conjunction"""


class AllowsComparisonTerms(LogicalFeature):
    """The logic allows comparison terms"""


class ModelMultiplicitySemantics(Profile, ABC):
    """A profile grouping corresponding to a model semantics"""


class SingleModelSemantics(ModelMultiplicitySemantics):
    """The logic has a single model"""


class MultipleModelSemantics(ModelMultiplicitySemantics):
    """The logic has multiple models"""


class Assumption(Profile, ABC):
    """Category of assumptions"""


class OpenWorld(Assumption):
    """The assumption that what is not known to be true is false"""


class ClosedWorld(Assumption):
    """The assumption that what is not known to be true is unknown"""

    disjoint_profiles = {OpenWorld}


class WellFoundedSemantics(ClosedWorld):
    """The assumption that the world is well-founded"""


class ClassicPrologNegationAsFailure(ClosedWorld):
    """The assumption that negation is failure"""


class TypeSystem(Profile, ABC):
    """Category of type systems"""


class UnsortedLogic(TypeSystem):
    """The logic has no type system"""


class SortedLogic(TypeSystem):
    """The logic has a type system"""


class LogicalFamily(Profile, ABC):
    """A profile grouping corresponding to a family of logics"""


class Classical(LogicalFamily):
    """The classical logic family"""


class NonClassical(LogicalFamily):
    """The non-classical logic family"""


class Modal(LogicalFamily):
    """The modal logic family"""


class Temporal(LogicalFamily):
    """The temporal logic family"""


class Paraconsistent(LogicalFamily):
    """The paraconsistent logic family"""


class Intuitionistic(LogicalFamily):
    """The intuitionistic logic family"""


class Probabilistic(LogicalFamily):
    """The probabilistic logic family"""


class LogicalSubset(Profile, ABC):
    """A profile grouping corresponding to a subset of logic"""


class Unrestricted(LogicalSubset, Undecidable):
    """The an unrestricted logic"""


class ClassicDatalog(LogicalSubset, ClosedWorld, SingleModelSemantics):
    """A subset of logic that corresponds to Datalog"""


class DisjunctiveDatalog(LogicalSubset, ClosedWorld, MultipleModelSemantics):
    """A subset of logic that corresponds to Datalog"""


class DescriptionLogic(LogicalSubset, Decidable):
    """A subset of logic that corresponds to Description Logic"""


class OWLProfile(LogicalSubset, ABC):
    """
    The OWL 2 DL subset of Description Logic.

    Note al OWL Profile is not necessarily a DL profile
    """


class OWL2DL(DescriptionLogic, OWLProfile):
    """The OWL 2 DL subset of Description Logic"""


class ModalLogic(LogicalSubset):
    """A subset of logic that corresponds to Modal Logic"""


class OrderOfLogic(Profile, ABC):
    """Category of orderings"""


class PropositionalLogic(OrderOfLogic):
    """The assumption that all predicates are propositional"""


class FirstOrder(OrderOfLogic):
    """The assumption that all predicates are first-order"""


class HigherOrder(OrderOfLogic):
    """The assumption that predicates may be higher-order"""


class NamedLogic(Profile, ABC):
    """A named logic"""


class AnswerSetProgramming(NamedLogic, WellFoundedSemantics, DisjunctiveDatalog):
    """The Answer Set Programming logic"""


class ReasoningParadigm(Profile, ABC):
    """A profile grouping corresponding to a reasoning paradigm"""


class Inductive(ReasoningParadigm):
    """The inductive reasoning paradigm"""


class Deductive(ReasoningParadigm):
    """The deductive reasoning paradigm"""


class Abductive(ReasoningParadigm):
    """The abductive reasoning paradigm"""


class Monotonic(ReasoningParadigm):
    """The monotonic reasoning paradigm"""


class NonMonotonic(ReasoningParadigm):
    """The non-monotonic reasoning paradigm"""


class ConstraintSolver(ReasoningParadigm):
    """The constraint solver reasoning paradigm"""


class UnspecifiedProfile(Profile):
    """An unspecified profile"""
