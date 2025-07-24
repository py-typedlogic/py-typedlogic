%% Predicate Definitions
% Path(source: str, target: str)
% Link(source: str, target: str)

%% transitivity

path(X, Z) :- path(X, Y), path(Y, Z).

%% Sentences

path(Source, Target) :- link(Source, Target).