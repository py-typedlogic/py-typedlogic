%% Predicate Definitions
% PersonWithAge(name: str, age: int)
% Adult(name: str)
% StageAge(stage: str, age: int)

%% facts

%% UNTRANSLATABLE: StageAge('Adult', AGE_THRESHOLD)

%% classifications

%% UNTRANSLATABLE: ∀[name:Thing age:int]. age >= AGE_THRESHOLD → Adult(name)

%% goals

adult('Alice') :- personwithage('Alice', 25).
%% UNTRANSLATABLE: Adult('Bob') → ∃[age:int]. PersonWithAge('Alice', age)