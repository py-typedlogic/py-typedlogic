[StageAge("Adult", 18),
 ForAll([name, age], Implies(age >= 18, Adult(name))),
 Implies(PersonWithAge("Alice", 25), Adult("Alice")),
 Implies(Adult("Bob"),
         Exists(age, PersonWithAge("Alice", age)))]