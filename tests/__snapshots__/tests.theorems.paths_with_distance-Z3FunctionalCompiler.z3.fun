[ForAll([x, y], Implies(Link(x, y), Path(x, y, 1))),
 ForAll([x, y, z, d1, d2],
        Implies(And(Path(x, y, d1), Path(y, z, d2)),
                Path(x, z, d1 + d2)))]