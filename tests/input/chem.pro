
inst(I) :- prediction(I,_,_,_).
cls(C) :- prediction(_,C,_,_).
%cls(C) :- is_a(_,C).

0.00001 :: inst_of(I,C) :- inst(I), cls(C).

disjoint(C,D) :- disjoint(D,C).

instance_of(I,D,true) :- is_a(C,D), instance_of(I,C,true).
instance_of(I,C,false) :- is_a(C,D), instance_of(I,D,false).
instance_of(I,C,false) :- disjoint(C,D),instance_of(I,D,true).


%xinstance_of(I,C,false) :- inst(I),cls(C),\+ instance_of(I,C,true).
%xinstance_of(I,C,true) :- inst(I),cls(C),\+ instance_of(I,C,false).
%instance_of(I,C,true) :- \+ instance_of(I,C,false).

conflict :- inst(I),cls(C), ((instance_of(I,C,false) ; instance_of(I,C,true))).
conflict :- instance_of(I,C,false),instance_of(I,C,true).
conflict :- disjoint(C,D), instance_of(I,C,true),instance_of(I,D,true).

evidence(\+ conflict).


is_a(cat,animal).
is_a(dog,animal).
is_a(fierce,property).
is_a(cute,property).

disjoint(cat,dog).
disjoint(fierce,cute).

% m2 is more reliable than m1
0.2 :: instance_of(I,C,V) :- prediction(I,C,V,m1).
0.8 :: instance_of(I,C,V) :- prediction(I,C,V,m2).

% method1 predictions
0.3 :: prediction(i1,dog,true,m1).
0.8 :: prediction(i1,cat,true,m1).
0.6 :: prediction(i2,dog,true,m1).
0.98 :: prediction(i2,cat,true,m1).

% method2 predictions
0.4 :: prediction(i1,dog,true,m2).
0.1 :: prediction(i1,cat,true,m2).
0.99 :: prediction(i2,dog,true,m2).
0.95 :: prediction(i2,cat,true,m2).

query(instance_of(I,C,V)).


