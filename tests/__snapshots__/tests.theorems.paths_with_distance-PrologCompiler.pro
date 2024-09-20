%% Predicate Definitions
% Link(source: str, target: str)
% Path(source: str, target: str, hops: int)

%% path_from_link

path(X, Y, 1) :- link(X, Y).

%% transitivity

path(X, Z, D1 + D2) :- path(X, Y, D1), path(Y, Z, D2).