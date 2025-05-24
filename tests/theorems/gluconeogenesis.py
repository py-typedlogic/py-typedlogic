"""
Gluconeogenesis pathway model with gene substitutability and tissue specificity.

This model represents the gluconeogenesis pathway with:
1. Metabolites (chemicals in the pathway)
2. Reactions (enzymatic steps that convert metabolites)
3. Genes (that encode enzymes for reactions)
4. Tissues (where genes may be expressed)

The model can be used to answer questions like:
- What happens if gene X is knocked out?
- Can the pathway function in a specific tissue?
- Which reactions are affected by gene knockouts?
"""

from pydantic import BaseModel
from typedlogic import FactMixin, gen2, Term
from typedlogic.decorators import axiom, goal
from enum import Enum, auto
from typing import List, Optional, Set


# --- Data types ---

class MetaboliteId(str, Enum):
    """Key metabolites in gluconeogenesis"""
    PYRUVATE = "pyruvate"
    OXALOACETATE = "oxaloacetate"
    PEP = "phosphoenolpyruvate"  # PEP
    GA3P = "glyceraldehyde_3_phosphate"
    DHAP = "dihydroxyacetone_phosphate"
    F16BP = "fructose_1_6_bisphosphate"
    F6P = "fructose_6_phosphate"
    G6P = "glucose_6_phosphate"
    GLUCOSE = "glucose"


class GeneId(str, Enum):
    """Genes encoding enzymes in gluconeogenesis"""
    # Pyruvate to PEP
    PCK1 = "pck1"  # PEPCK cytosolic
    PCK2 = "pck2"  # PEPCK mitochondrial
    PC = "pc"      # Pyruvate carboxylase
    
    # PEP to F16BP
    ENO1 = "eno1"  # Enolase
    PGM1 = "pgm1"  # Phosphoglycerate mutase
    GAPDH = "gapdh"  # Glyceraldehyde 3-phosphate dehydrogenase
    TPI1 = "tpi1"  # Triosephosphate isomerase
    ALDOB = "aldob"  # Aldolase B
    
    # F16BP to Glucose
    FBP1 = "fbp1"  # Fructose-1,6-bisphosphatase 1
    FBP2 = "fbp2"  # Fructose-1,6-bisphosphatase 2
    PGI = "pgi"    # Phosphoglucose isomerase
    G6PC = "g6pc"  # Glucose-6-phosphatase (liver)
    G6PC3 = "g6pc3"  # Glucose-6-phosphatase 3 (other tissues)


class ReactionId(str, Enum):
    """Key reactions in gluconeogenesis"""
    PYR_TO_OAA = "pyruvate_to_oxaloacetate"
    OAA_TO_PEP = "oxaloacetate_to_pep"
    PEP_TO_GA3P = "pep_to_ga3p"
    GA3P_TO_DHAP = "ga3p_to_dhap"
    GA3P_DHAP_TO_F16BP = "ga3p_dhap_to_f16bp"
    F16BP_TO_F6P = "f16bp_to_f6p"
    F6P_TO_G6P = "f6p_to_g6p"
    G6P_TO_GLUCOSE = "g6p_to_glucose"


class TissueId(str, Enum):
    """Tissues where gluconeogenesis may occur"""
    LIVER = "liver"
    KIDNEY = "kidney"
    INTESTINE = "intestine"
    MUSCLE = "muscle"


# --- Model classes ---

class Metabolite(BaseModel, FactMixin):
    """A metabolite in the pathway"""
    id: MetaboliteId


class Gene(BaseModel, FactMixin):
    """A gene encoding an enzyme"""
    id: GeneId


class ActiveGene(BaseModel, FactMixin):
    """A gene that is expressed and active"""
    id: GeneId


class InactiveGene(BaseModel, FactMixin):
    """A gene that is knocked out or not expressed"""
    id: GeneId


class GeneExpression(BaseModel, FactMixin):
    """Expression of a gene in a specific tissue"""
    gene_id: GeneId
    tissue_id: TissueId
    level: float  # Expression level


class Reaction(BaseModel, FactMixin):
    """A reaction converting substrate(s) to product(s)"""
    id: ReactionId
    substrates: List[MetaboliteId]
    products: List[MetaboliteId]
    reversible: bool = False  # This property is needed for pathway analysis


class CatalyzedBy(BaseModel, FactMixin):
    """A reaction catalyzed by a gene product (enzyme)"""
    reaction_id: ReactionId
    gene_id: GeneId
    primary: bool = True  # This property helps distinguish primary vs backup enzymes


class PathwayActive(BaseModel, FactMixin):
    """Indicates the overall pathway is functional"""
    # No parameters - existence of this fact means pathway is active


class ReactionActive(BaseModel, FactMixin):
    """Indicates a specific reaction is active"""
    reaction_id: ReactionId


class MetabolitePresent(BaseModel, FactMixin):
    """Indicates a metabolite is present (produced in the pathway)"""
    metabolite_id: MetaboliteId


class SimulationContext(BaseModel, FactMixin):
    """Context for the current simulation"""
    tissue_id: Optional[TissueId] = None  # If set, only genes expressed in this tissue are considered


# --- Axioms ---

@axiom
def reaction_requires_gene(r: ReactionId):
    """A reaction is active if at least one of its catalyzing genes is active"""
    catalyzing_genes = [c.gene_id for c in CatalyzedBy.get_all() if c.reaction_id == r]
    if any([ActiveGene(id=g) for g in catalyzing_genes]):
        assert ReactionActive(reaction_id=r)


@axiom
def reaction_requires_substrate(r: ReactionId):
    """A reaction requires all its substrates to be present to be active"""
    reactions = [rx for rx in Reaction.get_all() if rx.id == r]
    if not reactions:
        return  # No such reaction
    
    reaction = reactions[0]
    if all([MetabolitePresent(metabolite_id=s) for s in reaction.substrates]) and ReactionActive(reaction_id=r):
        # If reaction is active and all substrates are present, products are produced
        for product in reaction.products:
            assert MetabolitePresent(metabolite_id=product)


@axiom
def tissue_specific_gene_expression(g: GeneId, t: TissueId):
    """A gene is active in a tissue only if it's expressed there"""
    context = [c for c in SimulationContext.get_all()]
    if context and context[0].tissue_id is not None:
        tissue = context[0].tissue_id
        expressions = [e for e in GeneExpression.get_all() 
                      if e.gene_id == g and e.tissue_id == tissue]
        
        if expressions and expressions[0].level >= 0.1:  # Expression threshold
            assert ActiveGene(id=g)
        else:
            assert InactiveGene(id=g)


@axiom
def pathway_active_condition():
    """The pathway is active if glucose can be produced"""
    if MetabolitePresent(metabolite_id=MetaboliteId.GLUCOSE):
        assert PathwayActive()


# --- Initial facts setup ---

def setup_pathway_model():
    """Initialize the pathway model with basic facts"""
    # Define metabolites
    metabolites = [Metabolite(id=m) for m in MetaboliteId]
    
    # Define reactions
    reactions = [
        Reaction(
            id=ReactionId.PYR_TO_OAA,
            substrates=[MetaboliteId.PYRUVATE],
            products=[MetaboliteId.OXALOACETATE]
        ),
        Reaction(
            id=ReactionId.OAA_TO_PEP,
            substrates=[MetaboliteId.OXALOACETATE],
            products=[MetaboliteId.PEP]
        ),
        Reaction(
            id=ReactionId.PEP_TO_GA3P,
            substrates=[MetaboliteId.PEP],
            products=[MetaboliteId.GA3P]
        ),
        Reaction(
            id=ReactionId.GA3P_TO_DHAP,
            substrates=[MetaboliteId.GA3P],
            products=[MetaboliteId.DHAP],
            reversible=True
        ),
        Reaction(
            id=ReactionId.GA3P_DHAP_TO_F16BP,
            substrates=[MetaboliteId.GA3P, MetaboliteId.DHAP],
            products=[MetaboliteId.F16BP]
        ),
        Reaction(
            id=ReactionId.F16BP_TO_F6P,
            substrates=[MetaboliteId.F16BP],
            products=[MetaboliteId.F6P]
        ),
        Reaction(
            id=ReactionId.F6P_TO_G6P,
            substrates=[MetaboliteId.F6P],
            products=[MetaboliteId.G6P],
            reversible=True
        ),
        Reaction(
            id=ReactionId.G6P_TO_GLUCOSE,
            substrates=[MetaboliteId.G6P],
            products=[MetaboliteId.GLUCOSE]
        )
    ]
    
    # Define genes and their catalysis relationships
    genes = [Gene(id=g) for g in GeneId]
    
    # Define which genes catalyze which reactions
    catalysis = [
        # Pyruvate to OAA
        CatalyzedBy(reaction_id=ReactionId.PYR_TO_OAA, gene_id=GeneId.PC, primary=True),
        
        # OAA to PEP - two alternative enzymes
        CatalyzedBy(reaction_id=ReactionId.OAA_TO_PEP, gene_id=GeneId.PCK1, primary=True),
        CatalyzedBy(reaction_id=ReactionId.OAA_TO_PEP, gene_id=GeneId.PCK2, primary=False),
        
        # PEP to GA3P (several steps combined)
        CatalyzedBy(reaction_id=ReactionId.PEP_TO_GA3P, gene_id=GeneId.ENO1),
        CatalyzedBy(reaction_id=ReactionId.PEP_TO_GA3P, gene_id=GeneId.PGM1),
        CatalyzedBy(reaction_id=ReactionId.PEP_TO_GA3P, gene_id=GeneId.GAPDH),
        
        # GA3P to DHAP
        CatalyzedBy(reaction_id=ReactionId.GA3P_TO_DHAP, gene_id=GeneId.TPI1),
        
        # GA3P + DHAP to F16BP
        CatalyzedBy(reaction_id=ReactionId.GA3P_DHAP_TO_F16BP, gene_id=GeneId.ALDOB),
        
        # F16BP to F6P - two alternative enzymes
        CatalyzedBy(reaction_id=ReactionId.F16BP_TO_F6P, gene_id=GeneId.FBP1, primary=True),
        CatalyzedBy(reaction_id=ReactionId.F16BP_TO_F6P, gene_id=GeneId.FBP2, primary=False),
        
        # F6P to G6P
        CatalyzedBy(reaction_id=ReactionId.F6P_TO_G6P, gene_id=GeneId.PGI),
        
        # G6P to Glucose - tissue-specific enzymes
        CatalyzedBy(reaction_id=ReactionId.G6P_TO_GLUCOSE, gene_id=GeneId.G6PC, primary=True),  # Liver
        CatalyzedBy(reaction_id=ReactionId.G6P_TO_GLUCOSE, gene_id=GeneId.G6PC3, primary=False)  # Other tissues
    ]
    
    # Define tissue-specific gene expression patterns
    gene_expression = [
        # Liver - expresses all genes
        *[GeneExpression(gene_id=g, tissue_id=TissueId.LIVER, level=1.0) for g in GeneId],
        
        # Kidney - expresses most but not FBP2
        *[GeneExpression(gene_id=g, tissue_id=TissueId.KIDNEY, level=1.0) for g in GeneId 
          if g != GeneId.FBP2],
        GeneExpression(gene_id=GeneId.FBP2, tissue_id=TissueId.KIDNEY, level=0.0),
        
        # Intestine - limited expression, no G6PC
        *[GeneExpression(gene_id=g, tissue_id=TissueId.INTESTINE, level=1.0) for g in GeneId 
          if g not in [GeneId.G6PC, GeneId.FBP2]],
        GeneExpression(gene_id=GeneId.G6PC, tissue_id=TissueId.INTESTINE, level=0.0),
        GeneExpression(gene_id=GeneId.FBP2, tissue_id=TissueId.INTESTINE, level=0.0),
        
        # Muscle - very limited expression, only partial pathway
        GeneExpression(gene_id=GeneId.PCK2, tissue_id=TissueId.MUSCLE, level=0.5),
        GeneExpression(gene_id=GeneId.FBP2, tissue_id=TissueId.MUSCLE, level=0.8),
    ]
    
    return metabolites + reactions + genes + catalysis + gene_expression


def simulate_pathway(tissue: Optional[TissueId] = None, knockouts: List[GeneId] = None):
    """
    Simulate the pathway with optional tissue context and gene knockouts.
    
    Args:
        tissue: Optional tissue context to simulate
        knockouts: List of genes to knock out
    
    Returns:
        List of facts to initialize the model
    """
    facts = setup_pathway_model()
    
    # Add simulation context
    if tissue:
        facts.append(SimulationContext(tissue_id=tissue))
    
    # Apply gene knockouts - mark genes as inactive 
    if knockouts:
        for gene_id in knockouts:
            facts.append(InactiveGene(id=gene_id))
    
    # Add initial metabolite (pathway substrate is always present)
    facts.append(MetabolitePresent(metabolite_id=MetaboliteId.PYRUVATE))
    
    return facts


@goal
def test_pathway_in_liver():
    """Test that pathway works in liver tissue"""
    if PathwayActive() and SimulationContext(tissue_id=TissueId.LIVER):
        return True
    return False


@goal
def test_fbp1_knockout_blocks_pathway():
    """Test that knocking out FBP1 blocks the pathway when FBP2 is not expressed"""
    if SimulationContext(tissue_id=TissueId.KIDNEY) and InactiveGene(id=GeneId.FBP1) and not PathwayActive():
        return True
    return False