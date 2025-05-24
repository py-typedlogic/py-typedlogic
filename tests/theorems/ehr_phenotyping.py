"""
Electronic Health Record (EHR) phenotyping algorithm for diseases.

This example demonstrates how to use ASP with Clingo as a solver for 
identifying diseases based on ICD codes, lab values, and other clinical data.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Set, Union
from enum import Enum, auto
from datetime import datetime, date
from typedlogic import FactMixin, Term
from typedlogic.decorators import axiom, goal


# --- Data types ---

class CodeSystem(Enum):
    """Coding systems for medical codes"""
    ICD10 = auto()
    LOINC = auto()
    SNOMED = auto()


@dataclass
class Code(FactMixin):
    """A medical code from a coding system"""
    system: CodeSystem
    value: str


@dataclass
class Patient(FactMixin):
    """A patient in the EHR system"""
    id: str
    birth_date: date
    sex: str


@dataclass
class Encounter(FactMixin):
    """A clinical encounter"""
    id: str
    patient_id: str
    date: date
    

@dataclass
class Diagnosis(FactMixin):
    """A diagnosis recorded during an encounter"""
    encounter_id: str
    code: Code


@dataclass
class LabResult(FactMixin):
    """A laboratory test result"""
    patient_id: str
    date: date
    code: Code  # LOINC code
    value: float
    unit: str


@dataclass
class Medication(FactMixin):
    """A prescribed medication"""
    patient_id: str
    date: date
    code: Code  # RxNorm code
    dosage: Optional[str] = None


# --- Disease phenotypes ---

@dataclass
class Phenotype(FactMixin):
    """Base class for disease phenotypes"""
    patient_id: str


@dataclass
class DiabetesT2(Phenotype):
    """Type 2 Diabetes Mellitus phenotype"""
    confidence: float = 1.0


@dataclass
class Hypertension(Phenotype):
    """Hypertension phenotype"""
    confidence: float = 1.0


@dataclass
class CKD(Phenotype):
    """Chronic Kidney Disease phenotype"""
    stage: Optional[int] = None
    confidence: float = 1.0


# --- ICD Code hierarchy ---

@dataclass
class IsA(FactMixin):
    """Represents a hierarchical relationship between codes"""
    child: Code
    parent: Code


# --- Axioms ---

@axiom
def diabetes_from_diagnosis(patient_id: str, encounter_id: str):
    """Identify T2D from ICD-10 codes (direct match)"""
    if (
        Patient(id=patient_id) and 
        Encounter(id=encounter_id, patient_id=patient_id) and
        Diagnosis(encounter_id=encounter_id, code=Code(system=CodeSystem.ICD10, value="E11"))
    ):
        assert DiabetesT2(patient_id=patient_id)


@axiom
def diabetes_from_child_codes(patient_id: str, encounter_id: str, child_code: str):
    """Identify T2D from child codes in the ICD hierarchy"""
    if (
        Patient(id=patient_id) and 
        Encounter(id=encounter_id, patient_id=patient_id) and
        Diagnosis(encounter_id=encounter_id, code=Code(system=CodeSystem.ICD10, value=child_code)) and
        IsA(child=Code(system=CodeSystem.ICD10, value=child_code), 
            parent=Code(system=CodeSystem.ICD10, value="E11"))
    ):
        assert DiabetesT2(patient_id=patient_id)


@axiom
def diabetes_from_lab_values(patient_id: str):
    """Identify T2D from elevated HbA1c (≥ 6.5%)"""
    if (
        Patient(id=patient_id) and
        LabResult(
            patient_id=patient_id,
            code=Code(system=CodeSystem.LOINC, value="4548-4"),  # HbA1c
            value=v
        ) and v >= 6.5
    ):
        assert DiabetesT2(patient_id=patient_id, confidence=0.9)


@axiom
def diabetes_from_medication(patient_id: str):
    """Identify T2D from diabetes medications (e.g., metformin)"""
    if (
        Patient(id=patient_id) and
        Medication(
            patient_id=patient_id,
            code=Code(system=CodeSystem.SNOMED, value="10370")  # Metformin
        )
    ):
        assert DiabetesT2(patient_id=patient_id, confidence=0.7)


@axiom
def hypertension_from_diagnosis(patient_id: str, encounter_id: str):
    """Identify hypertension from ICD-10 codes"""
    if (
        Patient(id=patient_id) and 
        Encounter(id=encounter_id, patient_id=patient_id) and
        Diagnosis(encounter_id=encounter_id, code=Code(system=CodeSystem.ICD10, value="I10"))
    ):
        assert Hypertension(patient_id=patient_id)


@axiom
def hypertension_from_bp_readings(patient_id: str, systolic: float, diastolic: float):
    """Identify hypertension from elevated blood pressure readings"""
    if (
        Patient(id=patient_id) and
        LabResult(
            patient_id=patient_id,
            code=Code(system=CodeSystem.LOINC, value="8480-6"),  # Systolic BP
            value=systolic
        ) and
        LabResult(
            patient_id=patient_id,
            code=Code(system=CodeSystem.LOINC, value="8462-4"),  # Diastolic BP
            value=diastolic
        ) and
        systolic >= 140 and diastolic >= 90
    ):
        assert Hypertension(patient_id=patient_id, confidence=0.8)


@axiom
def ckd_from_diagnosis(patient_id: str, encounter_id: str):
    """Identify CKD from ICD-10 codes"""
    if (
        Patient(id=patient_id) and 
        Encounter(id=encounter_id, patient_id=patient_id) and
        Diagnosis(encounter_id=encounter_id, code=Code(system=CodeSystem.ICD10, value="N18"))
    ):
        assert CKD(patient_id=patient_id)


@axiom
def ckd_from_egfr(patient_id: str, value: float):
    """Identify CKD stage from eGFR values"""
    if (
        Patient(id=patient_id) and
        LabResult(
            patient_id=patient_id,
            code=Code(system=CodeSystem.LOINC, value="62238-1"),  # eGFR
            value=value
        )
    ):
        if value >= 90:
            assert CKD(patient_id=patient_id, stage=1, confidence=0.5)
        elif value >= 60:
            assert CKD(patient_id=patient_id, stage=2, confidence=0.7) 
        elif value >= 30:
            assert CKD(patient_id=patient_id, stage=3, confidence=0.9)
        elif value >= 15:
            assert CKD(patient_id=patient_id, stage=4, confidence=0.95)
        else:
            assert CKD(patient_id=patient_id, stage=5, confidence=0.99)


@axiom
def comorbidity_diabetes_hypertension(patient_id: str):
    """Identify patients with both T2D and hypertension"""
    if DiabetesT2(patient_id=patient_id) and Hypertension(patient_id=patient_id):
        # Increase confidence in both diagnoses when they co-occur
        assert DiabetesT2(patient_id=patient_id, confidence=1.0)
        assert Hypertension(patient_id=patient_id, confidence=1.0)


# Sample test function to demonstrate usage
def test_phenotyping_algorithm():
    """Test the phenotyping algorithm with sample data"""
    from typedlogic.registry import get_solver
    
    # Initialize solver
    solver = get_solver("clingo")
    solver.load(__name__)
    
    # Create test data
    today = date.today()
    birth_date = date(1960, 1, 1)
    
    # Patient with T2D diagnosis
    patient1 = Patient(id="P1", birth_date=birth_date, sex="F")
    encounter1 = Encounter(id="E1", patient_id="P1", date=today)
    diagnosis1 = Diagnosis(encounter_id="E1", code=Code(system=CodeSystem.ICD10, value="E11"))
    
    # Patient with elevated HbA1c
    patient2 = Patient(id="P2", birth_date=birth_date, sex="M")
    lab1 = LabResult(
        patient_id="P2",
        date=today,
        code=Code(system=CodeSystem.LOINC, value="4548-4"),
        value=7.2,
        unit="%"
    )
    
    # Patient with hypertension and CKD
    patient3 = Patient(id="P3", birth_date=birth_date, sex="M")
    encounter3 = Encounter(id="E3", patient_id="P3", date=today)
    diagnosis3 = Diagnosis(encounter_id="E3", code=Code(system=CodeSystem.ICD10, value="I10"))
    lab3 = LabResult(
        patient_id="P3",
        date=today,
        code=Code(system=CodeSystem.LOINC, value="62238-1"),
        value=45,
        unit="mL/min/1.73m²"
    )
    
    # Add facts to solver
    facts = [patient1, encounter1, diagnosis1, patient2, lab1, patient3, encounter3, diagnosis3, lab3]
    for fact in facts:
        solver.add(fact)
    
    # Define hierarchy relationships
    code_hierarchy = [
        IsA(child=Code(system=CodeSystem.ICD10, value="E11.9"), 
            parent=Code(system=CodeSystem.ICD10, value="E11"))
    ]
    for rel in code_hierarchy:
        solver.add(rel)
    
    # Solve and get model
    model = solver.model()
    
    # Retrieve phenotypes
    diabetes_cases = list(model.iter_retrieve(DiabetesT2))
    hypertension_cases = list(model.iter_retrieve(Hypertension))
    ckd_cases = list(model.iter_retrieve(CKD))
    
    # Check results
    assert len(diabetes_cases) >= 2  # P1 and P2 should have diabetes
    assert len(hypertension_cases) >= 1  # P3 should have hypertension
    assert len(ckd_cases) >= 1  # P3 should have CKD
    
    # Print results
    print(f"T2D cases: {diabetes_cases}")
    print(f"Hypertension cases: {hypertension_cases}")
    print(f"CKD cases: {ckd_cases}")
    
    return diabetes_cases, hypertension_cases, ckd_cases


if __name__ == "__main__":
    test_phenotyping_algorithm()