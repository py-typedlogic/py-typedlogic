%% Predicate Definitions
% PersonAge(name: str, age: int)
% SameAge(name1: str, name2: str)

%% facts

personage('Alice', 25).
personage('Bob', 30).
personage('Ciara', 30).

%% axioms

sameage(Name1, Name2) :- personage(Name1, Age), personage(Name2, Age).