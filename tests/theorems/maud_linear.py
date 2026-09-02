"""
A small linear-pathway kinetic model, expressed as typedlogic facts destined
for Maud (see :mod:`typedlogic.integrations.frameworks.maud`).

The pathway is the canonical Maud "linear" toy model::

    M1_e  --r1-->  M1_c  --r2-->  M2_c  --r3-->  M2_e

with two compartments (``e`` external, ``c`` cytosol), two metabolites, three
reactions and three enzymes. The boundary species ``M1_e`` and ``M2_e`` are
unbalanced; the internal species are balanced (steady state).

This module demonstrates the *value-add* of putting a symbolic layer in front of
Maud: the model does not assert ``EnzymeReaction`` facts directly. Instead it
asserts a higher-level :class:`Catalyzes` relation, and an ``@axiom`` derives the
``EnzymeReaction`` associations Maud needs. Running the theory through any datalog
solver materialises them before export, so the network topology is maintained in
one place and the Maud-specific wiring is generated.
"""

from dataclasses import dataclass
from typing import List

from typedlogic import FactMixin
from typedlogic.decorators import axiom
from typedlogic.integrations.frameworks.maud.maud_model import (
    ACTIVATION,
    TARGET_MIC,
    Allostery,
    Compartment,
    Enzyme,
    EnzymeReaction,
    Experiment,
    FormationEnergyPrior,
    KcatPrior,
    KineticModel,
    Measurement,
    Metabolite,
    MetaboliteInCompartment,
    Reaction,
    ReactionStoichiometry,
)


@dataclass(frozen=True)
class Catalyzes(FactMixin):
    """
    Higher-level statement that an enzyme catalyses a reaction.

    This is example vocabulary, not part of Maud's schema: the axiom below turns
    it into the ``EnzymeReaction`` facts Maud consumes.
    """

    enzyme_id: str
    reaction_id: str


@axiom
def enzyme_reaction_from_catalysis(e: str, r: str):
    """Every catalysis relation yields the Maud enzyme-reaction association."""
    if Catalyzes(enzyme_id=e, reaction_id=r):
        assert EnzymeReaction(enzyme_id=e, reaction_id=r)


def structural_facts() -> List[FactMixin]:
    """Return the compartments, species, reactions and enzymes of the pathway."""
    facts: List[FactMixin] = [
        KineticModel(name="linear"),
        Compartment(id="e", name="external", volume=1.0),
        Compartment(id="c", name="cytosol", volume=1.0),
        Metabolite(id="M1", name="Metabolite 1"),
        Metabolite(id="M2", name="Metabolite 2"),
        # Boundary species (unbalanced) and internal species (balanced).
        MetaboliteInCompartment(metabolite_id="M1", compartment_id="e", balanced=False),
        MetaboliteInCompartment(metabolite_id="M1", compartment_id="c", balanced=True),
        MetaboliteInCompartment(metabolite_id="M2", compartment_id="c", balanced=True),
        MetaboliteInCompartment(metabolite_id="M2", compartment_id="e", balanced=False),
        Enzyme(id="r1", name="r1ase"),
        Enzyme(id="r2", name="r2ase"),
        Enzyme(id="r3", name="r3ase"),
        Reaction(id="r1", name="Transport in of M1"),
        Reaction(id="r2", name="M1 to M2"),
        Reaction(id="r3", name="Transport out of M2"),
        # Stoichiometry: negative = substrate, positive = product.
        ReactionStoichiometry(reaction_id="r1", metabolite_id="M1", compartment_id="e", coefficient=-1.0),
        ReactionStoichiometry(reaction_id="r1", metabolite_id="M1", compartment_id="c", coefficient=1.0),
        ReactionStoichiometry(reaction_id="r2", metabolite_id="M1", compartment_id="c", coefficient=-1.0),
        ReactionStoichiometry(reaction_id="r2", metabolite_id="M2", compartment_id="c", coefficient=1.0),
        ReactionStoichiometry(reaction_id="r3", metabolite_id="M2", compartment_id="c", coefficient=-1.0),
        ReactionStoichiometry(reaction_id="r3", metabolite_id="M2", compartment_id="e", coefficient=1.0),
        # Enzyme/reaction wiring stated at a higher level; EnzymeReaction is derived.
        Catalyzes(enzyme_id="r1", reaction_id="r1"),
        Catalyzes(enzyme_id="r2", reaction_id="r2"),
        Catalyzes(enzyme_id="r3", reaction_id="r3"),
        # An allosteric activation of the middle enzyme by M2.
        Allostery(enzyme_id="r2", metabolite_id="M2", compartment_id="c", modification_type=ACTIVATION),
    ]
    return facts


def prior_facts() -> List[FactMixin]:
    """Return priors on turnover numbers and formation energies."""
    return [
        KcatPrior(enzyme="r1", reaction="r1", location=1.0, scale=0.2),
        KcatPrior(enzyme="r2", reaction="r2", location=1.0, scale=0.2),
        KcatPrior(enzyme="r3", reaction="r3", location=1.0, scale=0.2),
        FormationEnergyPrior(metabolite="M1", location=-1.0, scale=0.5),
        FormationEnergyPrior(metabolite="M2", location=2.0, scale=0.5),
    ]


def experiment_facts() -> List[FactMixin]:
    """Return one training experiment with two concentration measurements."""
    return [
        Experiment(id="condition_1", is_train=True, is_test=False, temperature=298.15),
        Measurement(
            experiment_id="condition_1",
            target_type=TARGET_MIC,
            target_id="M1",
            compartment="c",
            value=0.8,
            error_scale=0.1,
        ),
        Measurement(
            experiment_id="condition_1",
            target_type=TARGET_MIC,
            target_id="M2",
            compartment="c",
            value=1.2,
            error_scale=0.1,
        ),
    ]


def all_facts() -> List[FactMixin]:
    """All facts of the model (structure + priors + experiments)."""
    return structural_facts() + prior_facts() + experiment_facts()
