%% Predicate Definitions
% NamedThing(name: str)
% Relationship(subject: str, predicate: str, object: str)
% Person(name: str, age: int)
% Likes(subject: str, predicate: str, object: str, reciprocated: boolean)

%% Sentences

person(Name, Age) :- namedthing(Name, Age).

%% Sentences

likes(Subject, Predicate, Object, Reciprocated) :- relationship(Subject, Predicate, Object, Reciprocated).