[StageAge("Adult", 18),
 PersonWithAge("Alice", 25),
 ForAll([name, age], Implies(age >= 18, Adult(name)))]