[Person("Fred"),
 Person("Jie"),
 Animal("corky", "cat"),
 Animal("fido", "dog"),
 ForAll([x, species],
        Implies(Animal(x, species), Likes(x, "Fred"))),
 ForAll([x, species],
        Implies(Animal(x, "cat"), Likes(x, "Jie"))),
 ForAll([x, species],
        Implies(Animal(x, "dog"), Not(Likes("Fred", x))))]