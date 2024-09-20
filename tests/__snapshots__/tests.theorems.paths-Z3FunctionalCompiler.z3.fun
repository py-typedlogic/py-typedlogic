[ForAll([x, y, z],
        Implies(And(Path(x, y), Path(y, z)), Path(x, z))),
 ForAll([source, target],
        Implies(Link(source, target), Path(source, target)))]