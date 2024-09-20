%% Predicate Definitions
% Likes(subject: str, object: str)
% Person(name: str)
% Animal(name: str, species: str)

%% persons

person('Fred').
person('Jie').

%% animals

animal('corky', 'cat').
animal('fido', 'dog').

%% animal_preferences

likes(X, 'Fred') :- animal(X, Species).
likes(X, 'Jie') :- animal(X, 'cat').
