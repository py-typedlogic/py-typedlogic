%% Predicate Definitions
% Code(system: CodeSystem, value: str)
% Patient(id: str, birth_date: date, sex: str)
% Encounter(id: str, patient_id: str, date: date)
% Diagnosis(encounter_id: str, code: Code)
% LabResult(patient_id: str, date: date, code: Code, value: float, unit: str)
% Medication(patient_id: str, date: date, code: Code, dosage: Optional)
% Phenotype(patient_id: str)
% DiabetesT2(patient_id: str, confidence: float)
% Hypertension(patient_id: str, confidence: float)
% CKD(patient_id: str, stage: Optional, confidence: float)
% IsA(child: Code, parent: Code)

%% diabetes_from_diagnosis

diabetest2(Patient_id, _) :- patient(Patient_id, date(1970, 1, 1), 'unknown'), encounter(Encounter_id, Patient_id, date(2024, 1, 1)), diagnosis(Encounter_id, code('ICD10', 'E11')).

%% diabetes_from_child_codes

diabetest2(Patient_id, _) :- patient(Patient_id, date(1970, 1, 1), 'unknown'), encounter(Encounter_id, Patient_id, date(2024, 1, 1)), diagnosis(Encounter_id, code('ICD10', Child_code)), isa(code('ICD10', Child_code), code('ICD10', 'E11')).

%% diabetes_from_lab_values

diabetest2(Patient_id, 0.9) :- patient(Patient_id, date(1970, 1, 1), 'unknown'), labresult(Patient_id, date(2024, 1, 1), code('LOINC', '4548-4'), V, '%'), V >= 6.5.

%% diabetes_from_medication

diabetest2(Patient_id, 0.7) :- patient(Patient_id, date(1970, 1, 1), 'unknown'), medication(Patient_id, date(2024, 1, 1), code('SNOMED', '10370'), _).

%% hypertension_from_diagnosis

hypertension(Patient_id, _) :- patient(Patient_id, date(1970, 1, 1), 'unknown'), encounter(Encounter_id, Patient_id, date(2024, 1, 1)), diagnosis(Encounter_id, code('ICD10', 'I10')).

%% hypertension_from_bp_readings

hypertension(Patient_id, 0.8) :- patient(Patient_id, date(1970, 1, 1), 'unknown'), labresult(Patient_id, date(2024, 1, 1), code('LOINC', '8480-6'), Systolic, 'mmHg'), labresult(Patient_id, date(2024, 1, 1), code('LOINC', '8462-4'), Diastolic, 'mmHg'), Systolic >= 140, Diastolic >= 90.

%% ckd_from_diagnosis

ckd(Patient_id, _, _) :- patient(Patient_id, date(1970, 1, 1), 'unknown'), encounter(Encounter_id, Patient_id, date(2024, 1, 1)), diagnosis(Encounter_id, code('ICD10', 'N18')).

%% ckd_from_egfr

ckd(Patient_id, 1, 0.5) :- Value >= 90, patient(Patient_id, date(1970, 1, 1), 'unknown'), labresult(Patient_id, date(2024, 1, 1), code('LOINC', '62238-1'), Value, 'mL/min/1.73m²').
Value >= 90 :- Value >= 60, patient(Patient_id, date(1970, 1, 1), 'unknown'), labresult(Patient_id, date(2024, 1, 1), code('LOINC', '62238-1'), Value, 'mL/min/1.73m²'), \+ (ckd(Patient_id, 2, 0.7)).
Value >= 90 :- Value >= 30, patient(Patient_id, date(1970, 1, 1), 'unknown'), labresult(Patient_id, date(2024, 1, 1), code('LOINC', '62238-1'), Value, 'mL/min/1.73m²'), \+ (ckd(Patient_id, 3, 0.9)), \+ (Value >= 60).
Value >= 90 :- Value >= 15, patient(Patient_id, date(1970, 1, 1), 'unknown'), labresult(Patient_id, date(2024, 1, 1), code('LOINC', '62238-1'), Value, 'mL/min/1.73m²'), \+ (ckd(Patient_id, 4, 0.95)), \+ (Value >= 30), \+ (Value >= 60).
Value >= 90 :- patient(Patient_id, date(1970, 1, 1), 'unknown'), labresult(Patient_id, date(2024, 1, 1), code('LOINC', '62238-1'), Value, 'mL/min/1.73m²'), \+ (Value >= 15), \+ (ckd(Patient_id, 5, 0.99)), \+ (Value >= 30), \+ (Value >= 60).

%% comorbidity_diabetes_hypertension

diabetest2(Patient_id, 1.0) :- diabetest2(Patient_id, _), hypertension(Patient_id, _).
hypertension(Patient_id, 1.0) :- diabetest2(Patient_id, _), hypertension(Patient_id, _).

%% Sentences

phenotype(Patient_id) :- diabetest2(Patient_id, Confidence).

%% Sentences

phenotype(Patient_id) :- hypertension(Patient_id, Confidence).

%% Sentences

phenotype(Patient_id) :- ckd(Patient_id, Stage, Confidence).