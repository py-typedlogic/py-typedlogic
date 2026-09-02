"""
Typed schema for the structural part of a Maud kinetic model.

Each class is a :class:`~typedlogic.FactMixin` whose fields map onto keys in
Maud's input TOML files (see https://github.com/biosustain/Maud). Because these
are ordinary typedlogic facts, they can be asserted directly, derived by
``@axiom`` rules, or materialised by a solver before being handed to the
exporter.

The classes cover the pieces of a Maud input that are genuinely *structural*
(and therefore a good fit for symbolic reasoning):

Kinetic model
    :class:`KineticModel`, :class:`Compartment`, :class:`Metabolite`,
    :class:`MetaboliteInCompartment`, :class:`Enzyme`, :class:`Reaction`,
    :class:`ReactionStoichiometry`, :class:`EnzymeReaction`,
    :class:`Allostery`, :class:`CompetitiveInhibition`

Priors
    :class:`KcatPrior`, :class:`KmPrior`, :class:`FormationEnergyPrior`

Experiments / measurements
    :class:`Experiment`, :class:`Measurement`

Numeric priors and measurements are included so a complete, runnable Maud input
can be produced, but they are deliberately thin -- the numerical modelling is
Maud's job, not typedlogic's.
"""

from dataclasses import dataclass
from typing import Optional

from typedlogic import FactMixin

# Mechanism identifiers accepted by Maud reactions.
REVERSIBLE_MICHAELIS_MENTEN = "reversible_michaelis_menten"
IRREVERSIBLE_MICHAELIS_MENTEN = "irreversible_michaelis_menten"
DRAIN = "drain"

# Allosteric modification types.
ACTIVATION = "activation"
INHIBITION = "inhibition"

# Measurement target types.
TARGET_MIC = "mic"  # metabolite-in-compartment concentration
TARGET_FLUX = "flux"  # reaction flux
TARGET_ENZYME = "enzyme"  # enzyme concentration


# --- Kinetic model structure ---


@dataclass(frozen=True)
class KineticModel(FactMixin):
    """Top-level name of the kinetic model. At most one is expected."""

    name: str


@dataclass(frozen=True)
class Compartment(FactMixin):
    """A physical compartment, e.g. cytosol."""

    id: str
    name: str
    volume: float = 1.0


@dataclass(frozen=True)
class Metabolite(FactMixin):
    """A chemical species, independent of compartment."""

    id: str
    name: str


@dataclass(frozen=True)
class MetaboliteInCompartment(FactMixin):
    """
    A metabolite located in a compartment (a Maud ``mic``).

    ``balanced`` marks whether the species is at steady state (its production
    and consumption must balance) as opposed to a boundary/pool species.
    """

    metabolite_id: str
    compartment_id: str
    balanced: bool = True


@dataclass(frozen=True)
class Enzyme(FactMixin):
    """An enzyme catalysing one or more reactions."""

    id: str
    name: str
    subunits: int = 1


@dataclass(frozen=True)
class Reaction(FactMixin):
    """
    A reaction.

    Stoichiometry is supplied separately via :class:`ReactionStoichiometry`
    facts so it can be reasoned over.
    """

    id: str
    name: str
    mechanism: str = REVERSIBLE_MICHAELIS_MENTEN


@dataclass(frozen=True)
class ReactionStoichiometry(FactMixin):
    """
    One stoichiometric coefficient of a reaction for a metabolite-in-compartment.

    Negative coefficients denote substrates, positive coefficients products.
    The exporter assembles these into Maud's ``stoichiometry`` inline table keyed
    by ``<metabolite_id>_<compartment_id>``.
    """

    reaction_id: str
    metabolite_id: str
    compartment_id: str
    coefficient: float


@dataclass(frozen=True)
class EnzymeReaction(FactMixin):
    """Associates an enzyme with a reaction it catalyses."""

    enzyme_id: str
    reaction_id: str


@dataclass(frozen=True)
class Allostery(FactMixin):
    """An allosteric effector acting on an enzyme."""

    enzyme_id: str
    metabolite_id: str
    compartment_id: str
    modification_type: str = ACTIVATION


@dataclass(frozen=True)
class CompetitiveInhibition(FactMixin):
    """A metabolite competitively inhibiting an enzyme's reaction."""

    enzyme_id: str
    reaction_id: str
    metabolite_id: str
    compartment_id: str


# --- Priors ---


@dataclass(frozen=True)
class KcatPrior(FactMixin):
    """Log-normal prior on an enzyme's turnover number for a reaction."""

    enzyme: str
    reaction: str
    location: float
    scale: float


@dataclass(frozen=True)
class KmPrior(FactMixin):
    """Log-normal prior on a Michaelis constant."""

    metabolite: str
    compartment: str
    enzyme: str
    reaction: str
    exploc: float
    scale: float


@dataclass(frozen=True)
class FormationEnergyPrior(FactMixin):
    """
    Normal prior on a metabolite's formation energy (dgf).

    The exporter aggregates all of these into a single multivariate ``dgf``
    prior with a diagonal covariance built from the individual ``scale`` values.
    """

    metabolite: str
    location: float
    scale: float


# --- Experiments and measurements ---


@dataclass(frozen=True)
class Experiment(FactMixin):
    """An experimental condition under which measurements were taken."""

    id: str
    is_train: bool = True
    is_test: bool = False
    temperature: float = 298.15


@dataclass(frozen=True)
class Measurement(FactMixin):
    """
    A single measurement within an experiment.

    For ``mic`` targets, ``target_id`` is a metabolite id and ``compartment`` is
    set. For ``flux`` targets, ``target_id`` is a reaction id and ``compartment``
    is ``None``.
    """

    experiment_id: str
    target_type: str
    target_id: str
    value: float
    error_scale: float
    compartment: Optional[str] = None
