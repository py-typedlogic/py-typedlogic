from typedlogic.utils.import_closure import compute_import_closure


def test_closure():
    closure = compute_import_closure("tests.theorems.import_test.ext")
    assert "tests.theorems.import_test.ext" in closure
    assert "tests.theorems.import_test.core" in closure


def test_closure_from_module():
    import tests.theorems.import_test.ext as ext

    closure = compute_import_closure(ext.__name__)
    assert "tests.theorems.import_test.ext" in closure
    assert "tests.theorems.import_test.core" in closure
