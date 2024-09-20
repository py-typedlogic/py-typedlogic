[ForAll([name, age],
        Implies(NamedThing(name), Person(name, age))),
 ForAll([subject, predicate, object, reciprocated],
        Implies(Relationship(subject, predicate, object),
                Likes(subject,
                      predicate,
                      object,
                      reciprocated)))]