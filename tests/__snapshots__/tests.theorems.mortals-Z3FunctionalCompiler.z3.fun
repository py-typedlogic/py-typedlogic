[ForAll(x, Implies(Person(x), Mortal(x))),
 ForAll([x, y, z],
        Implies(And(AncestorOf(x, z), AncestorOf(z, y)),
                AncestorOf(x, y))),
 ForAll([x, y],
        Not(And(AncestorOf(x, y), AncestorOf(y, x)))),
 Implies(And(AncestorOf("p1", "p2"), AncestorOf("p2", "p3")),
         AncestorOf("p1", "p3"))]