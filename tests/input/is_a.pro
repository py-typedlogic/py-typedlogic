
instance_of(I,D) :- is_a(C,D), instance_of(I,C).

is_a(cat,mammal).
is_a(dog,mammal).
is_a(hedgehog,mammal).

0.4 :: instance_of(i1,cat).
0.2 :: instance_of(i1,dog).
0.0 :: instance_of(i1,hedgehog).

unsat :- instance_of(I,cat),instance_of(I,dog).

evidence(not unsat).


query(instance_of(_,_)).


