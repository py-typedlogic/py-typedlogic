
from dataclasses import dataclass
from enum import IntEnum

from typedlogic import FactMixin, axiom
from typedlogic.extensions.probabilistic import probability

Thing = str
PersonID = Thing
TermID = Thing
PhenotypeID = TermID
DiseaseID = TermID
GeneID = Thing

class Pathogenicity(IntEnum):
    BENIGN = 1
    LIKELY_BENIGN = 2
    UNCERTAIN_SIGNIFICANCE = 3
    LIKELY_PATHOGENIC = 4
    PATHOGENIC = 5
@dataclass
class SubClassOf(FactMixin):
    child: TermID
    parent: TermID

@dataclass
class Person(FactMixin):
    person: PersonID

@dataclass
class PersonHasDisease(FactMixin):
    person: PersonID
    disease: DiseaseID


@dataclass
class PersonHasPhenotype(FactMixin):
    """
    Holds if person p has phenotype phenotype.

    Latent knowledge - not typically observable.
    """
    person: PersonID
    phenotype: PhenotypeID

#@dataclass
#class PersonHasVariantIn(FactMixin):
#    person: PersonID
#    gene: GeneID
#    pathogenicity: Pathogenicity

#@dataclass
#class DiseaseHasVariantIn(FactMixin):
#    disease: DiseaseID
#    gene: GeneID

@dataclass
class PersonHasObservation(FactMixin):
    """
    Holds if person p is recorded to have phenotype.    
    """
    person: PersonID
    phenotype: PhenotypeID


@axiom
def phenotype_ontology(p: PersonID, child: PhenotypeID, parent: PhenotypeID):
    assert (SubClassOf(child, parent) and PersonHasPhenotype(p, child)) >> PersonHasPhenotype(p, parent)

@axiom
def disease_ontology(p: PersonID, child: DiseaseID, parent: DiseaseID):
    assert (SubClassOf(child, parent) and PersonHasDisease(p, child)) >> PersonHasDisease(p, parent)

@axiom
def observation_hierarchy(p: PersonID, child: PhenotypeID, parent: PhenotypeID):
    assert (SubClassOf(child, parent) and PersonHasObservation(p, child)) >> PersonHasObservation(p, parent)

@axiom
def observation_implies_phenotype(p: PersonID, ph: PhenotypeID):
    assert probability(PersonHasPhenotype(p, ph) >> PersonHasObservation(p, ph)) == 0.95
    #assert probability(~PersonHasPhenotype(p, ph) >> PersonHasObservation(p, ph)) == 0.02


#@axiom
#def person_has_variant(p: PersonID, g: GeneID, pathogenicity: Pathogenicity):
#    assert probability(PersonHasVariantIn(p, g, pathogenicity)) == 0.00001    