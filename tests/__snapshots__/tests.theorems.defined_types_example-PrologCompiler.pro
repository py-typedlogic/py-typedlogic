%% Predicate Definitions
% PersonWithAge(name: str, age: str)
% Adult(name: str)
% StageAge(stage: str, age: str)
% PersonWithAge2(name: str, age_in_years: int)
% PersonWithAddress(name: str, zip_code: str)

%% classifications

%% UNTRANSLATABLE: ∀[name:Thing age:Age]. age >= 18 → Adult(name)

%% goals

adult('Alice') :- personwithage('Alice', 25).
%% UNTRANSLATABLE: Adult('Bob') → ∃[age:int]. PersonWithAge('Alice', age)