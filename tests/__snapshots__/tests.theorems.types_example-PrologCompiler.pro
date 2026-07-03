%% Predicate Definitions
% PersonWithAge(name: str, age: int)
% Adult(name: str)
% StageAge(stage: str, age: int)

%% facts

%% UNTRANSLATABLE: StageAge('Adult', AGE_THRESHOLD)
personwithage('Alice', 25).

%% classifications

%% UNTRANSLATABLE: ∀[name:Thing age:int]. age >= AGE_THRESHOLD → Adult(name)