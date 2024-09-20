%% Predicate Definitions
% Person(name: str)
% Mortal(name: str)
% AncestorOf(ancestor: str, descendant: str)

%% all_persons_are_mortal_axiom

mortal(X) :- person(X).

%% ancestor_transitivity_axiom

ancestorof(X, Y) :- ancestorof(X, Z), ancestorof(Z, Y).

%% acyclicity_axiom



%% check_transitivity

ancestorof('p1', 'p3') :- ancestorof('p1', 'p2'), ancestorof('p2', 'p3').