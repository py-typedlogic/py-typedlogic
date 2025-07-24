[ForAll([name, age],
        Implies(Person(name, age), NamedThing(name))),
 ForAll([subject, predicate, object, reciprocated],
        Implies(Likes(subject,
                      predicate,
                      object,
                      reciprocated),
                Relationship(subject, predicate, object)))]