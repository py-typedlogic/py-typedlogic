%% Predicate Definitions
% Person(name: str, age: int, living_status: LivingStatus)
% PersonHasAgeCategory(person: str, age_category: AgeCategory)
% IsAlive(person: str)

%% person_has_age_category

personhasagecategory(P, 'MIDDLE_AGED') :- person(P, Age, Living_status), Age > 44, Age < 65.
personhasagecategory(P, 'OLD') :- person(P, Age, Living_status), Age > 64.
personhasagecategory(P, 'YOUNG') :- person(P, Age, Living_status), Age < 45.

%% is_alive

isalive(P) :- person(P, Age, 'ALIVE').