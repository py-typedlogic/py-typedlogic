
instance_of(I,D) :- is_a(C,D), instance_of(I,C).

is_a(cat,animal).
is_a(dog,animal).
is_a(fierce,property).
is_a(cute,property).

disjoint(cat,dog).
disjoint(fierce,cute).

unsat(I,C,D) :- instance_of(I,C), instance_of(I,D), disjoint(C,D).

evidence(not unsat(I,C,D)).


% m2 is more reliable than m1
0.2 :: instance_of(I,C) :- prediction(I,C,m1).
0.8 :: instance_of(I,C) :- prediction(I,C,m2).

% method1 predictions
0.3 :: prediction(i1,dog,m1).
0.8 :: prediction(i1,cat,m1).
0.6 :: prediction(i2,dog,m1).
0.98 :: prediction(i2,cat,m1).

% method2 predictions
0.2 :: prediction(i1,dog,m2).
0.99 :: prediction(i1,cat,m2).
0.99 :: prediction(i2,dog,m2).
0.98 :: prediction(i2,cat,m2).

query(instance_of(I,C)).


