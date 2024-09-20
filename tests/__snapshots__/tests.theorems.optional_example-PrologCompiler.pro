%% Predicate Definitions
% FriendOf(subject: str, object: str, start_year: Optional, end_year: Optional)
% FriendPath(subject: str, object: str)

%% tr

friendpath(S, O) :- friendof(S, O, _, _).
friendpath(S, O) :- friendof(S, O, _, _).

%% facts

friendof('Fred', 'Jie', 2000, 2005).
friendof('Jie', 'Li', _, _).