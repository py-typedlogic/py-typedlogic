[ForAll([shaver, customer],
        Implies(And(Barber(shaver),
                    Person(customer),
                    Not(Shaves(customer, customer))),
                Shaves(shaver, customer))),
 ForAll(name, Implies(Person(name), Barber(name)))]