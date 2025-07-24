%% Predicate Definitions
% NamedThing(name: str)
% Relationship(subject: str, predicate: str, object: str)
% Person(name: str, age: int)
% Likes(subject: str, predicate: str, object: str, reciprocated: boolean)

%% Sentences

namedthing(Name) :- person(Name, Age).

%% Sentences

relationship(Subject, Predicate, Object) :- likes(Subject, Predicate, Object, Reciprocated).