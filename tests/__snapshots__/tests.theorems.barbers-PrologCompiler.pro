%% Predicate Definitions
% Person(name: str)
% Barber(name: str)
% Shaves(shaver: str, customer: str)

%% shaves

shaves(Shaver, Customer) :- barber(Shaver), person(Customer), \+ (shaves(Customer, Customer)).

%% Sentences

person(Name) :- barber(Name).