from collections import defaultdict
from typing import Optional, Union, ClassVar, Dict, List, Any

from typedlogic import Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.integrations.frameworks.owldl.owltop import (
    OntologyElement,
    TransitiveObjectProperty,
    SymmetricObjectProperty,
    InverseFunctionalObjectProperty,
    instance_of,
    Axiom,
)


class OWLPyCompiler(Compiler):
    """
    Writes theories to OWL files.

    TODO: incomplete
    """

    default_suffix: ClassVar[str] = "py"

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        imported_classes = set()
        s = ""
        owl_axioms = []
        owl_axiom_index: Dict[str, List[Axiom]] = defaultdict(list)
        for sentence in theory.sentences:
            if "owl_axiom" in sentence.annotations:
                axiom = sentence.annotations["owl_axiom"]
                owl_axioms.append(axiom)
                args = list(vars(axiom))
                about = getattr(axiom, args[0])
                if isinstance(about, OntologyElement):
                    about = about.__name__
                elif isinstance(about, type):
                    about = about.__name__
                if axiom not in owl_axiom_index[str(about)]:
                    owl_axiom_index[str(about)].append(axiom)

        # for about, axioms in owl_axiom_index.items():
        #    s += f"# {about} :: {axioms}\n"

        for pd in theory.predicate_definitions:
            if pd.predicate in ("Thing", "TopObjectProperty", "TopDataProperty"):
                imported_classes.add(pd.predicate)
                continue
            parents = ", ".join(pd.parents) if pd.parents else ""
            s += "\n@predicate\n"
            axioms = owl_axiom_index.get(pd.predicate, [])
            for axiom in axioms:
                s += f"# {axiom} :: {len(vars(axiom))}\n"
            s += f"class {pd.predicate}({parents}):\n"
            curr_len = len(s)
            done = set()
            for axiom in axioms:
                if str(axiom) in done:
                    continue
                kw = type(axiom).frame_keyword
                if kw:
                    all_vars = list(vars(axiom))
                    if len(all_vars) == 1:
                        # Characteristic axiom
                        s += f"    {kw} = True ## {axiom}\n"
                        done.add(str(axiom))
                    elif len(all_vars) == 2:
                        # Binary axiom
                        second_arg = all_vars[1]
                        arg_repr = self.as_python(getattr(axiom, second_arg))
                        s += f"    {kw} = {arg_repr}\n"
                        done.add(str(axiom))

            if len(s) == curr_len:
                s += f"    pass\n"

        hdr = "from typedlogic.decorators import predicate\n\n"
        hdr += "from typedlogic.integrations.frameworks.owldl import (\n"
        for ic in imported_classes:
            hdr += f"    {ic},\n"
        hdr += ")\n\n"
        s = hdr + s
        return s

    def as_python(self, x: Any) -> str:
        if isinstance(x, type):
            return x.__name__
        return str(x)
