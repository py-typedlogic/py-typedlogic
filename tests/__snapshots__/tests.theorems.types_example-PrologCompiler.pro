%% Predicate Definitions
% PersonWithAge(name: str, age: int)
% Adult(name: str)
% StageAge(stage: str, age: int)

%% facts

stageage('Adult', 18).
personwithage('Alice', 25).

%% classifications

%% UNTRANSLATABLE: ∀[name:Thing age:int]. age >= 18 → Adult(name)