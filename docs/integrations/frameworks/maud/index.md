# Maud (metabolic models)

[Maud](https://github.com/biosustain/Maud) is a tool from the
[DTU Biosustain](https://www.biosustain.dtu.dk/) *Quantitative Modelling of Cell
Metabolism* group for fitting **Bayesian statistical models of metabolic
networks**. Under the hood it is a [Stan](https://mc-stan.org) program: it
performs continuous-parameter Bayesian inference (HMC/NUTS) over mechanistic
enzyme-kinetic rate equations at steady state, estimating real-valued quantities
such as kinetic constants (kcat, Km), thermodynamic parameters (formation
energies), and steady-state concentrations and fluxes.

## Where typedlogic fits

typedlogic is **not** a replacement for that numerical inference — a
probabilistic-logic engine like ProbLog reasons about *discrete, relational*
uncertainty, not continuous ODE/steady-state kinetics. What a typed logic layer
*can* contribute is the **structural / symbolic** part of a kinetic model:

| Layer | Tool | Handles |
|-------|------|---------|
| Symbolic structure, typing, validation | **typedlogic** | reaction network, stoichiometry, enzyme–reaction wiring, regulation, consistency checks |
| Continuous Bayesian inference | **Maud / Stan** | kcat, Km, formation energies, fluxes, concentrations |

This integration is a **proof-of-concept exporter**: you express the structure
of a kinetic model as typed [`FactMixin`](../../../concepts/datamodel.md) facts
(optionally *derived* and *validated* by `@axiom` rules and a solver), then emit
a valid Maud input folder. The Bayesian inference stays with Maud.

## Example

The [`maud_linear`](https://github.com/py-typedlogic/py-typedlogic/blob/main/tests/theorems/maud_linear.py)
example encodes the canonical Maud "linear" pathway
(`M1_e → M1_c → M2_c → M2_e`). Note that it does **not** assert the
`EnzymeReaction` associations Maud needs — it asserts a higher-level `Catalyzes`
relation, and an axiom derives them:

```python
@axiom
def enzyme_reaction_from_catalysis(e: str, r: str):
    if Catalyzes(enzyme_id=e, reaction_id=r):
        assert EnzymeReaction(enzyme_id=e, reaction_id=r)
```

Run the theory through any datalog solver to materialise the derived structure,
then export a Maud input folder:

```python
from typedlogic.parsers.pyparser.python_parser import PythonParser
from typedlogic.registry import get_solver
from typedlogic import Theory
from typedlogic.integrations.frameworks.maud.exporter import export_maud_input
import tests.theorems.maud_linear as ml

solver = get_solver("wellfounded")
solver.add(PythonParser().transform(ml))
for fact in ml.all_facts():
    solver.add_fact(fact)
solver.check()

derived = Theory()
derived.ground_terms = list(solver.model().ground_terms)
export_maud_input(derived, "linear_model")   # writes kinetic_model.toml, priors.toml, experiments.toml, config.toml
```

Or, to export hand-authored facts directly (no solver):

```python
from typedlogic.integrations.frameworks.maud.exporter import export_maud_input, theory_from_facts
import tests.theorems.maud_linear as ml

export_maud_input(theory_from_facts(ml.all_facts()), "linear_model")
```

The resulting folder is consumable by `maud sample linear_model`.

## API

### Schema

::: typedlogic.integrations.frameworks.maud.maud_model

### Compiler

::: typedlogic.integrations.frameworks.maud.maud_compiler.MaudCompiler

### Exporter

::: typedlogic.integrations.frameworks.maud.exporter.export_maud_input

::: typedlogic.integrations.frameworks.maud.exporter.theory_from_facts

::: typedlogic.integrations.frameworks.maud.exporter.MaudConfig
