import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar, Iterable, Iterator, List, Optional, Tuple

import llm
import yaml

from typedlogic import Sentence
from typedlogic.profiles import MixedProfile, OpenWorld, Profile, Unrestricted
from typedlogic.registry import get_compiler
from typedlogic.solver import Model, Solution, Solver

logger = logging.getLogger(__name__)

SYSTEM = """
Your task is to determine whether logical statements follow from a given set of axioms.
I will provide you with an initial list of axioms. I will then give a numbered set of
sentences. You will return whether that sentence follows from the axioms.

Give results as a simple yaml object like this:

```yaml
provable: [1, 3, 5]
not_provable: [2, 4, 6]
```

Do not provide proofs, just the yaml object.
"""

TEMPLATE = """
Background theory:

{program}

Which of the following are entailed:

{goals}

Answer:
"""

@dataclass
class LLMSolver(Solver):
    """
    A solver that uses an LLM.

    This is for research purposes only. LLM output can be reliable, slow, and expensive,
    and should not be used as a replacement for a deterministic logic-based solver.

    """

    model_name: str = field(default="gpt-4o")
    fol_syntax: str = field(default="fol")
    profile: ClassVar[Profile] = MixedProfile(Unrestricted(), OpenWorld())

    def models(self) -> Iterator[Model]:
        r = self.check()
        if r.satisfiable:
            yield Model()

    def prove(self, sentence: Sentence) -> Optional[bool]:
        results = list(self.prove_multiple([sentence]))
        return results[0][1]

    def prove_multiple(self, sentences: List[Sentence]) -> Iterable[Tuple[Sentence, Optional[bool]]]:
        compiler = get_compiler(self.fol_syntax)
        program = compiler.compile(self.base_theory)
        model = llm.get_model(self.model_name)
        enumerated_goals = dict(enumerate(sentences, 1))
        enumerated_goals_compiled = {i: compiler.compile_sentence(s) for i, s in enumerated_goals.items()}
        goals = "\n".join([f"{i}: {s}" for i, s in enumerated_goals_compiled.items()])
        prompt = TEMPLATE.format(program=program, goals=goals)
        #print(f"SYSTEM={SYSTEM}")
        #print(f"PROMPT={prompt}")
        response = model.prompt(prompt, system=SYSTEM)
        print(f"RESPONSE={response.text()}")
        obj = self.parse_response(response.text())
        for i in obj["provable"]:
            yield enumerated_goals[int(i)], True
        for i in obj["not_provable"]:
            yield enumerated_goals[int(i)], False

    def parse_response(self, text: str) -> Any:
        if "```" in text:
            text = text.split("```")[1].strip()
            if text.startswith("yaml"):
                text = text[5:].strip()
        return yaml.safe_load(text)


    def check(self) -> Solution:
        return Solution(satisfiable=None)
