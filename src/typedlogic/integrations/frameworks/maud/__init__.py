"""
Maud integration for typedlogic.

`Maud <https://github.com/biosustain/Maud>`_ is a tool from the DTU Biosustain
group for fitting Bayesian statistical models of metabolic networks. It performs
continuous-parameter Bayesian inference (via `Stan <https://mc-stan.org>`_) over
mechanistic enzyme-kinetic models, estimating real-valued quantities such as
kinetic constants (kcat, Km), thermodynamic parameters (formation energies), and
steady-state concentrations and fluxes.

typedlogic is *not* a replacement for that numerical inference. What it can
usefully contribute is the **structural / symbolic layer** of a kinetic model:
the reaction network, stoichiometry, enzyme-reaction associations, regulatory
interactions, typing and consistency checks. This integration lets you express
that structure as typed :class:`~typedlogic.FactMixin` facts (optionally derived
and validated by axioms and a solver) and then *export* a valid Maud input
folder, leaving the Bayesian inference to Maud/Stan.

This is a proof-of-concept exporter, not a full Maud binding. The clean division
of labour is:

* **typedlogic** -- symbolic structure, typing, validation of the kinetic model
* **Maud / Stan** -- continuous Bayesian inference over that model

The main entry points are:

* :mod:`~typedlogic.integrations.frameworks.maud.maud_model` -- the typed schema
* :class:`~typedlogic.integrations.frameworks.maud.maud_compiler.MaudCompiler`
* :func:`~typedlogic.integrations.frameworks.maud.exporter.export_maud_input`
"""
