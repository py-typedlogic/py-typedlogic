%% Predicate Definitions
% Link(source: str, target: str)
% Path(source: str, target: str)

%% transitivity

path(X, Z) :- path(X, Y), path(Y, Z).

%% Sentences

path(Source, Target) :- link(Source, Target).