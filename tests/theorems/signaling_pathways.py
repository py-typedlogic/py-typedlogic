"""
Signaling pathway example using ASP with Clingo as a solver.

This example models cellular signaling pathways involving protein modifications 
such as phosphorylation, with a focus on the MAPK/ERK pathway.
"""

from dataclasses import dataclass
from typing import Optional, List, Set, Dict
from enum import Enum, auto
from typedlogic import FactMixin, Term
from typedlogic.decorators import axiom, goal


# --- Data types ---

class ModificationType(Enum):
    """Types of protein modifications"""
    PHOSPHORYLATION = auto()
    UBIQUITINATION = auto()
    METHYLATION = auto()
    ACETYLATION = auto()
    GTP_BOUND = auto()  # For GTPases like Ras


@dataclass
class Protein(FactMixin):
    """A protein in a signaling pathway"""
    name: str


@dataclass
class ModifiedProtein(FactMixin):
    """A protein with a specific post-translational modification"""
    protein: Protein
    modification: ModificationType
    site: Optional[str] = None  # e.g., "Y204" for tyrosine at position 204
    active: bool = True  # Whether this modification activates the protein


@dataclass
class Complex(FactMixin):
    """A protein complex formed by multiple proteins"""
    # components: Tuple[Protein, ...]
    name: Optional[str] = None


@dataclass
class Kinase(FactMixin):
    """A protein with kinase activity"""
    protein: Protein


@dataclass
class Phosphatase(FactMixin):
    """A protein with phosphatase activity"""
    protein: Protein


@dataclass
class GTPase(FactMixin):
    """A protein with GTPase activity"""
    protein: Protein


@dataclass
class GEF(FactMixin):
    """Guanine nucleotide exchange factor - activates GTPases"""
    protein: Protein
    target: Protein  # The GTPase this GEF activates


@dataclass
class GAP(FactMixin):
    """GTPase-activating protein - inactivates GTPases"""
    protein: Protein
    target: Protein  # The GTPase this GAP inactivates


@dataclass
class Ligand(FactMixin):
    """A signaling molecule that can bind to a receptor"""
    name: str


@dataclass
class Receptor(FactMixin):
    """A cell surface receptor"""
    protein: Protein


@dataclass
class LigandReceptorBinding(FactMixin):
    """A binding event between a ligand and its receptor"""
    ligand: Ligand
    receptor: Receptor
    active: bool = True


@dataclass
class Activation(FactMixin):
    """Represents activation of one protein by another"""
    upstream: Protein  # The activating protein
    downstream: Protein  # The activated protein


@dataclass
class PhosphorylationEvent(FactMixin):
    """A specific phosphorylation event"""
    kinase: Protein
    substrate: Protein
    site: str


@dataclass
class Translocation(FactMixin):
    """Movement of a protein from one cellular compartment to another"""
    protein: Protein
    from_compartment: str
    to_compartment: str


@dataclass
class Compartment(FactMixin):
    """A cellular compartment"""
    name: str


@dataclass
class ProteinLocation(FactMixin):
    """The location of a protein in a specific compartment"""
    protein: Protein
    compartment: Compartment


# --- Signal transduction axioms ---

@axiom
def receptor_activation_by_ligand(ligand_name: str, receptor_name: str):
    """When a ligand binds to its receptor, the receptor becomes activated"""
    if (
        Ligand(name=ligand_name) and 
        Receptor(protein=Protein(name=receptor_name)) and
        LigandReceptorBinding(
            ligand=Ligand(name=ligand_name),
            receptor=Receptor(protein=Protein(name=receptor_name)),
            active=True
        )
    ):
        assert ModifiedProtein(
            protein=Protein(name=receptor_name),
            modification=ModificationType.PHOSPHORYLATION,
            active=True
        )


@axiom
def rtk_activates_grb2_sos(receptor_name: str):
    """
    Activated receptor tyrosine kinases (RTKs) recruit GRB2-SOS complex
    """
    if ModifiedProtein(
        protein=Protein(name=receptor_name),
        modification=ModificationType.PHOSPHORYLATION,
        active=True
    ):
        assert Complex(
            # components=(
            #     Protein(name=receptor_name),
            #     Protein(name="GRB2"),
            #     Protein(name="SOS")
            # ),
            #name=f"{receptor_name}-GRB2-SOS"
            name="GRB2-SOS",
        ) and Activation(
            upstream=Protein(name=receptor_name),
            downstream=Protein(name="SOS")
        )


@axiom
def sos_activates_ras(sos_active: bool):
    """
    SOS is a GEF that activates Ras by promoting GDP/GTP exchange
    """
    if (
        Protein(name="SOS") and
        Protein(name="RAS") and
        GEF(protein=Protein(name="SOS"), target=Protein(name="RAS")) and
        Activation(upstream=Protein(name="SOS"), downstream=Protein(name="RAS"))
    ):
        assert ModifiedProtein(
            protein=Protein(name="RAS"),
            modification=ModificationType.GTP_BOUND,
            active=True
        )


@axiom
def ras_activates_raf(ras_active: bool):
    """
    Active (GTP-bound) Ras activates Raf kinase
    """
    if ModifiedProtein(
        protein=Protein(name="RAS"),
        modification=ModificationType.GTP_BOUND,
        active=True
    ):
        assert ModifiedProtein(
            protein=Protein(name="RAF"),
            modification=ModificationType.PHOSPHORYLATION,
            site="S338",
            active=True
        )
        assert Activation(
            upstream=Protein(name="RAS"),
            downstream=Protein(name="RAF")
        )


@axiom
def raf_phosphorylates_mek(raf_name: str, mek_name: str):
    """
    Active Raf phosphorylates MEK at specific serine residues
    """
    if (
        ModifiedProtein(
            protein=Protein(name=raf_name),
            modification=ModificationType.PHOSPHORYLATION,
            active=True
        ) and
        Kinase(protein=Protein(name=raf_name)) and
        Protein(name=mek_name)
    ):
        assert PhosphorylationEvent(
            kinase=Protein(name=raf_name),
            substrate=Protein(name=mek_name),
            site="S218"
        )
        assert PhosphorylationEvent(
            kinase=Protein(name=raf_name),
            substrate=Protein(name=mek_name),
            site="S222"
        )
        assert ModifiedProtein(
            protein=Protein(name=mek_name),
            modification=ModificationType.PHOSPHORYLATION,
            site="S218",
            active=True
        )
        assert ModifiedProtein(
            protein=Protein(name=mek_name),
            modification=ModificationType.PHOSPHORYLATION,
            site="S222",
            active=True
        )
        assert Activation(
            upstream=Protein(name=raf_name),
            downstream=Protein(name=mek_name)
        )


@axiom
def mek_phosphorylates_erk(mek_name: str, erk_name: str):
    """
    Active MEK phosphorylates ERK at threonine and tyrosine residues
    """
    if (
        (ModifiedProtein(
            protein=Protein(name=mek_name),
            modification=ModificationType.PHOSPHORYLATION,
            site="S218",
            active=True
        ) and
        ModifiedProtein(
            protein=Protein(name=mek_name),
            modification=ModificationType.PHOSPHORYLATION,
            site="S222",
            active=True
        )) and
        Kinase(protein=Protein(name=mek_name)) and
        Protein(name=erk_name)
    ):
        assert PhosphorylationEvent(
            kinase=Protein(name=mek_name),
            substrate=Protein(name=erk_name),
            site="T185"
        )
        assert PhosphorylationEvent(
            kinase=Protein(name=mek_name),
            substrate=Protein(name=erk_name),
            site="Y187"
        )
        assert ModifiedProtein(
            protein=Protein(name=erk_name),
            modification=ModificationType.PHOSPHORYLATION,
            site="T185",
            active=True
        )
        assert ModifiedProtein(
            protein=Protein(name=erk_name),
            modification=ModificationType.PHOSPHORYLATION,
            site="Y187",
            active=True
        )
        assert Activation(
            upstream=Protein(name=mek_name),
            downstream=Protein(name=erk_name)
        )


@axiom
def erk_nuclear_translocation(erk_name: str):
    """
    Activated ERK translocates from cytoplasm to nucleus
    """
    if (
        ModifiedProtein(
            protein=Protein(name=erk_name),
            modification=ModificationType.PHOSPHORYLATION,
            site="T185",
            active=True
        ) and
        ModifiedProtein(
            protein=Protein(name=erk_name),
            modification=ModificationType.PHOSPHORYLATION,
            site="Y187",
            active=True
        ) and
        ProteinLocation(
            protein=Protein(name=erk_name),
            compartment=Compartment(name="cytoplasm")
        )
    ):
        assert Translocation(
            protein=Protein(name=erk_name),
            from_compartment="cytoplasm",
            to_compartment="nucleus"
        )
        assert ProteinLocation(
            protein=Protein(name=erk_name),
            compartment=Compartment(name="nucleus")
        )


@axiom
def gap_inactivates_ras(gap_name: str):
    """
    GAPs accelerate the GTPase activity of Ras, converting it to inactive GDP-bound form
    """
    if (
        ModifiedProtein(
            protein=Protein(name="RAS"),
            modification=ModificationType.GTP_BOUND,
            active=True
        ) and
        GAP(protein=Protein(name=gap_name), target=Protein(name="RAS"))
    ):
        # This is essentially turning off the active state
        assert ~ModifiedProtein(
            protein=Protein(name="RAS"),
            modification=ModificationType.GTP_BOUND,
            active=True
        )


@axiom
def phosphatase_inactivates_protein(phosphatase_name: str, protein_name: str, site: str):
    """
    Phosphatases remove phosphate groups from proteins, often inactivating them
    """
    if (
        ModifiedProtein(
            protein=Protein(name=protein_name),
            modification=ModificationType.PHOSPHORYLATION,
            site=site,
            active=True
        ) and
        Phosphatase(protein=Protein(name=phosphatase_name))
    ):
        assert ~ModifiedProtein(
            protein=Protein(name=protein_name),
            modification=ModificationType.PHOSPHORYLATION,
            site=site,
            active=True
        )


# --- Cross-pathway interactions ---

@axiom
def pi3k_pathway_crosstalk(receptor_name: str):
    """
    Activated RTKs can also initiate the PI3K-AKT pathway
    """
    if ModifiedProtein(
        protein=Protein(name=receptor_name),
        modification=ModificationType.PHOSPHORYLATION,
        active=True
    ):
        assert Activation(
            upstream=Protein(name=receptor_name),
            downstream=Protein(name="PI3K")
        )
        assert ModifiedProtein(
            protein=Protein(name="PI3K"),
            modification=ModificationType.PHOSPHORYLATION,
            active=True
        )


@axiom
def pi3k_activates_akt(pi3k_active: bool):
    """
    Active PI3K leads to PIP3 production, which activates AKT
    """
    if ModifiedProtein(
        protein=Protein(name="PI3K"),
        modification=ModificationType.PHOSPHORYLATION,
        active=True
    ):
        assert Activation(
            upstream=Protein(name="PI3K"),
            downstream=Protein(name="AKT")
        )
        assert ModifiedProtein(
            protein=Protein(name="AKT"),
            modification=ModificationType.PHOSPHORYLATION,
            site="T308",
            active=True
        )


# --- Feedback loops ---

@axiom
def erk_negative_feedback(erk_name: str):
    """
    Active ERK can phosphorylate SOS, creating a negative feedback loop
    """
    if (
        ModifiedProtein(
            protein=Protein(name=erk_name),
            modification=ModificationType.PHOSPHORYLATION,
            site="T185",
            active=True
        ) and
        ModifiedProtein(
            protein=Protein(name=erk_name),
            modification=ModificationType.PHOSPHORYLATION,
            site="Y187",
            active=True
        )
    ):
        assert PhosphorylationEvent(
            kinase=Protein(name=erk_name),
            substrate=Protein(name="SOS"),
            site="S1132"
        )
        assert ModifiedProtein(
            protein=Protein(name="SOS"),
            modification=ModificationType.PHOSPHORYLATION,
            site="S1132",
            active=False  # This phosphorylation inhibits SOS
        )


# --- Transcription factor activation ---

@axiom
def erk_activates_transcription_factors(erk_name: str, tf_name: str):
    """
    Activated ERK in the nucleus phosphorylates various transcription factors
    """
    if (
        ModifiedProtein(
            protein=Protein(name=erk_name),
            modification=ModificationType.PHOSPHORYLATION,
            site="T185",
            active=True
        ) and
        ModifiedProtein(
            protein=Protein(name=erk_name),
            modification=ModificationType.PHOSPHORYLATION,
            site="Y187",
            active=True
        ) and
        ProteinLocation(
            protein=Protein(name=erk_name),
            compartment=Compartment(name="nucleus")
        ) and
        Protein(name=tf_name)
    ):
        assert PhosphorylationEvent(
            kinase=Protein(name=erk_name),
            substrate=Protein(name=tf_name),
            site="S"  # Generic site
        )
        assert ModifiedProtein(
            protein=Protein(name=tf_name),
            modification=ModificationType.PHOSPHORYLATION,
            site="S",
            active=True
        )
        assert Activation(
            upstream=Protein(name=erk_name),
            downstream=Protein(name=tf_name)
        )


# --- Test function ---

def test_mapk_pathway():
    """Test the MAPK/ERK signaling pathway model"""
    from typedlogic.registry import get_solver
    import datetime
    
    # Initialize solver
    solver = get_solver("clingo")
    solver.load(__name__)
    
    # Define the compartments
    compartments = [
        Compartment(name="extracellular"),
        Compartment(name="membrane"),
        Compartment(name="cytoplasm"),
        Compartment(name="nucleus")
    ]
    
    # Define the proteins in the pathway
    proteins = [
        Protein(name="EGF"),  # Epidermal Growth Factor (a ligand)
        Protein(name="EGFR"),  # EGF Receptor
        Protein(name="GRB2"),  # Adapter protein
        Protein(name="SOS"),   # Guanine nucleotide exchange factor
        Protein(name="RAS"),   # Small GTPase
        Protein(name="RAF"),   # MAP kinase kinase kinase
        Protein(name="MEK"),   # MAP kinase kinase
        Protein(name="ERK"),   # MAP kinase
        Protein(name="RSK"),   # Ribosomal S6 Kinase (downstream of ERK)
        Protein(name="CREB"),  # Transcription factor
        Protein(name="ELK1"),  # Transcription factor
        Protein(name="PI3K"),  # PI3 kinase (parallel pathway)
        Protein(name="AKT"),   # Protein kinase B (parallel pathway)
        Protein(name="RASGAP"), # RAS GTPase-activating protein
        Protein(name="PP2A")   # Protein phosphatase 2A
    ]
    
    # Define protein types/activities
    kinases = [
        Kinase(protein=Protein(name="RAF")),
        Kinase(protein=Protein(name="MEK")),
        Kinase(protein=Protein(name="ERK")),
        Kinase(protein=Protein(name="RSK"))
    ]
    
    phosphatases = [
        Phosphatase(protein=Protein(name="PP2A"))
    ]
    
    gtpases = [
        GTPase(protein=Protein(name="RAS"))
    ]
    
    gefs = [
        GEF(protein=Protein(name="SOS"), target=Protein(name="RAS"))
    ]
    
    gaps = [
        GAP(protein=Protein(name="RASGAP"), target=Protein(name="RAS"))
    ]
    
    # Define ligands and receptors
    ligands = [
        Ligand(name="EGF")
    ]
    
    receptors = [
        Receptor(protein=Protein(name="EGFR"))
    ]
    
    # Define initial protein locations
    locations = [
        ProteinLocation(protein=Protein(name="EGF"), compartment=Compartment(name="extracellular")),
        ProteinLocation(protein=Protein(name="EGFR"), compartment=Compartment(name="membrane")),
        ProteinLocation(protein=Protein(name="GRB2"), compartment=Compartment(name="cytoplasm")),
        ProteinLocation(protein=Protein(name="SOS"), compartment=Compartment(name="cytoplasm")),
        ProteinLocation(protein=Protein(name="RAS"), compartment=Compartment(name="membrane")),
        ProteinLocation(protein=Protein(name="RAF"), compartment=Compartment(name="cytoplasm")),
        ProteinLocation(protein=Protein(name="MEK"), compartment=Compartment(name="cytoplasm")),
        ProteinLocation(protein=Protein(name="ERK"), compartment=Compartment(name="cytoplasm")),
        ProteinLocation(protein=Protein(name="CREB"), compartment=Compartment(name="nucleus")),
        ProteinLocation(protein=Protein(name="ELK1"), compartment=Compartment(name="nucleus")),
        ProteinLocation(protein=Protein(name="RASGAP"), compartment=Compartment(name="cytoplasm")),
        ProteinLocation(protein=Protein(name="PP2A"), compartment=Compartment(name="cytoplasm"))
    ]
    
    # Start the pathway by binding EGF to EGFR
    binding = LigandReceptorBinding(
        ligand=Ligand(name="EGF"),
        receptor=Receptor(protein=Protein(name="EGFR")),
        active=True
    )
    
    # Add all facts to the solver
    all_facts = (
        compartments + proteins + kinases + phosphatases + 
        gtpases + gefs + gaps + ligands + receptors + 
        locations + [binding]
    )
    
    for fact in all_facts:
        solver.add(fact)
    
    # Solve and get model
    model = solver.model()
    
    # Query for specific events in the pathway
    egfr_activation = list(model.iter_retrieve(
        ModifiedProtein,
        protein=Protein(name="EGFR"),
        modification=ModificationType.PHOSPHORYLATION
    ))
    
    ras_activation = list(model.iter_retrieve(
        ModifiedProtein,
        protein=Protein(name="RAS"),
        modification=ModificationType.GTP_BOUND
    ))
    
    erk_phosphorylation = list(model.iter_retrieve(
        ModifiedProtein,
        protein=Protein(name="ERK"),
        modification=ModificationType.PHOSPHORYLATION
    ))
    
    erk_translocation = list(model.iter_retrieve(
        Translocation,
        protein=Protein(name="ERK"),
        to_compartment="nucleus"
    ))
    
    tf_activation = list(model.iter_retrieve(
        ModifiedProtein,
        protein=Protein(name="CREB"),
        modification=ModificationType.PHOSPHORYLATION
    )) + list(model.iter_retrieve(
        ModifiedProtein,
        protein=Protein(name="ELK1"),
        modification=ModificationType.PHOSPHORYLATION
    ))
    
    # Validate pathway activation
    assert len(egfr_activation) >= 1, "EGFR should be activated"
    assert len(ras_activation) >= 1, "RAS should be activated"
    assert len(erk_phosphorylation) >= 2, "ERK should be phosphorylated on two sites"
    
    # Print pathway activation results
    print(f"EGFR activation: {egfr_activation}")
    print(f"RAS activation: {ras_activation}")
    print(f"ERK phosphorylation: {erk_phosphorylation}")
    print(f"ERK translocation: {erk_translocation}")
    print(f"Transcription factor activation: {tf_activation}")
    
    return model
