%% Predicate Definitions
% FriendOf(subject: str, object: str, start_year: int, end_year: int)
% FriendPath(subject: str, object: str)

%% tr

friendpath(S, O) :- friendof(S, O, _, _).
friendpath(S, O) :- friendof(S, O, _, _).

%% facts

friendof('Fred', 'Jie', 2000, 2005).
friendof('Jie', 'Li', _, _).