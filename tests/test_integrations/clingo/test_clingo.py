import clingo


def test_clingo():
    # Create a Control object
    ctl = clingo.Control(["0"])

    # Add the ASP program
    ctl.add("base", [], "a; b.")

    # Ground the program
    ctl.ground([("base", [])])

    n = 0
    # Solve the program
    with ctl.solve(yield_=True) as handle:
        for model in handle:
            n += 1
            print(f"Model: {n}")
            print(model)

            # Print each atom in the model
            for atom in model.symbols(shown=True):
                print(atom)
    assert n == 2
    print("Finished")


def test_clingo_unsat():
    # Create a Control object
    ctl = clingo.Control(["0"])

    # Add the ASP program
    ctl.add("base", [], "a; b. not a. not b.")

    # Ground the program
    ctl.ground([("base", [])])

    n = 0
    # Solve the program
    with ctl.solve(yield_=True) as handle:
        for model in handle:
            n += 1
            print(f"Model: {n}")
            print(model)

            # Print each atom in the model
            for atom in model.symbols(shown=True):
                print(atom)

    print(f"Finished {n}")
    assert n == 0
