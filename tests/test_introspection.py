from typedlogic import Implies
from typedlogic.datamodel import And, Forall, Term, Variable
from typedlogic.parsers.pyparser.introspection import (
    get_module_predicate_definitions,
    get_module_sentence_groups,
    translate_module_to_theory,
)


def test_introspect_theory():
    import tests.theorems.mortals as mortals

    theory = translate_module_to_theory(mortals)
    assert theory
    assert theory.name


def test_introspect():
    import tests.theorems.mortals as mortals

    ascs = get_module_sentence_groups(mortals)
    assert len(ascs) == 4
    for asc in ascs:
        print(asc)
        print(asc.sentences)
        assert asc.sentences
    forall_qsent = ascs[1].sentences[0]
    assert isinstance(forall_qsent, Forall)
    impl_sent = forall_qsent.sentence
    assert isinstance(impl_sent, Implies)
    assert impl_sent.antecedent
    assert impl_sent.consequent
    acyc_sg = ascs[2]
    assert acyc_sg.sentences
    assert len(acyc_sg.sentences) == 1
    acyc_sent = acyc_sg.sentences[0]
    assert acyc_sent
    assert isinstance(acyc_sent, Forall)
    assert acyc_sent.sentence
    assert acyc_sent.variables
    assert len(acyc_sent.variables) == 2
    x = acyc_sent.variables[0]
    y = acyc_sent.variables[1]
    assert isinstance(x, Variable)
    assert isinstance(y, Variable)
    assert x.name == "x"
    assert y.name == "y"
    vars = acyc_sent.variables
    assert len(vars) == 2
    assert isinstance(vars[0], Variable)
    assert vars[0].name == "x"
    assert isinstance(vars[1], Variable)
    assert vars[1].name == "y"


def test_introspect_classes():
    import tests.theorems.mortals as mortals

    preddef_map = get_module_predicate_definitions(mortals)
    for name, pd in preddef_map.items():
        print(f"{name}: {pd}")
        # print(vars(cls))
    assert len(preddef_map) == 3
    assert "Mortal" in preddef_map
    assert "Person" in preddef_map
    assert "AncestorOf" in preddef_map
    assert len(preddef_map["Mortal"].arguments) == 1
    assert len(preddef_map["Person"].arguments) == 1
    assert len(preddef_map["AncestorOf"].arguments) == 2


def test_introspect_classes2():
    import tests.theorems.animals as animals

    preddef_map = get_module_predicate_definitions(animals)
    for name, pd in preddef_map.items():
        print(f"{name}: {pd}")
        # print(vars(cls))
    assert len(preddef_map) == 3
    assert len(preddef_map["Person"].arguments) == 1
    assert len(preddef_map["Likes"].arguments) == 2


def test_introspect_classes3():
    import tests.theorems.numbers as numbers

    preddef_map = get_module_predicate_definitions(numbers)
    for name, pd in preddef_map.items():
        print(f"{name}: {pd}")
        for arg_name, arg_type in pd.arguments.items():
            t = pd.argument_base_type(arg_name)
        # print(vars(cls))
    assert len(preddef_map) == 2


def test_introspect_imports():
    import tests.theorems.import_test.ext as ext

    preddef_map = get_module_predicate_definitions(ext)
    for name, pd in preddef_map.items():
        print(f"{name}: parents={pd.parents}")
        for arg_name, arg_type in pd.arguments.items():
            t = pd.argument_base_type(arg_name)
        # print(vars(cls))
    assert len(preddef_map) == 4
    assert "Person" in preddef_map
    person_pd = preddef_map["Person"]
    assert person_pd.parents == ["NamedThing"]


def test_introspect_type_example():
    import tests.theorems.types_example as te

    theory = translate_module_to_theory(te)
    assert theory.constants
    print(theory.constants)
    assert len(theory.constants) == 1
    assert theory.constants["AGE_THRESHOLD"] == 18
    assert theory.type_definitions
    print(theory.type_definitions)
    assert len(theory.type_definitions) == 1
    assert theory.type_definitions["Thing"] == "str"


def test_introspect_defined_type_example():
    import tests.theorems.defined_types_example as te

    theory = translate_module_to_theory(te)
    assert theory.constants
    for c in theory.constants.values():
        print(f"C: {c}")
    print(theory.constants)
    assert len(theory.constants) == 1
    assert theory.constants["AGE_THRESHOLD"] == 18
    assert theory.type_definitions
    for td, td_v in theory.type_definitions.items():
        print(f"TD: {td}  = {td_v}")
    # print(theory.type_definitions)
    assert len(theory.type_definitions) == 5
    assert theory.type_definitions["Thing"] == ["str", "int"]
    assert theory.type_definitions["PosInt"] == "int"
    assert theory.unroll_type("Thing") == ["str", "int"]
    assert theory.unroll_type("ZipCode") == ["str"]


def test_function_term_example():
    # pytest.skip("Not implemented")
    import tests.theorems.paths_with_distance as pwd

    theory = translate_module_to_theory(pwd)
    for s in theory.sentences:
        print(s)
    assert len(theory.sentences) == 2
    x = Variable("x")
    y = Variable("y")
    z = Variable("z")
    d1 = Variable("d1", "int")
    d2 = Variable("d2", "int")
    s = Forall(
        [x, y, z, d1, d2],
        Implies(
            And(
                Term("Path", x, y, d1),
                Term("Path", y, z, d2),
            ),
            Term("Path", x, z, Term("add", d1, d2)),
        ),
    )
    assert theory.sentences[1] == s


def test_unary_predicates():
    import tests.theorems.unary_predicates as unary_predicates

    theory = translate_module_to_theory(unary_predicates)
    coin_cls = unary_predicates.Coin
    assert coin_cls
    assert list(coin_cls.__annotations__.keys()) == ["id"]
    win_cls = unary_predicates.Win
    assert win_cls
    assert list(win_cls.__annotations__.keys()) == []
    pd_map = {pd.predicate: pd for pd in theory.predicate_definitions}
    win_pd = pd_map["Win"]
    assert win_pd
    assert win_pd.predicate == "Win"
    # assert win_pd.arguments == {}
    found = False
    for s in theory.sentences:
        if isinstance(s, Forall):
            s = s.sentence
        if isinstance(s, Implies):
            cons = s.consequent
            if isinstance(cons, Term):
                if cons.predicate == "Win":
                    assert cons.values == ()
                    found = True
    assert found
