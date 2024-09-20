[PersonAge("Alice", 25),
 PersonAge("Bob", 30),
 PersonAge("Ciara", 30),
 ForAll([name1, name2],
        Implies(Exists(age,
                       And(PersonAge(name1, age),
                           PersonAge(name2, age))),
                SameAge(name1, name2)))]