[ForAll(x, Implies(Person(x), Mortal(x))),
 ForAll([x, y, z],
        Implies(And(AncestorOf(x, z), AncestorOf(z, y)),
                AncestorOf(x, y))),
 ForAll([x, y],
        Not(And(AncestorOf(x, y), AncestorOf(y, x))))]