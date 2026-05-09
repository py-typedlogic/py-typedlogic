import os
import subprocess
import sys
from pathlib import Path


def test_env():
    path = os.getenv("PATH")
    print(path)


def test_compiler_import_does_not_require_mypyc():
    """
    The compiler module must import without the optional mypy/mypyc runtime.

    This guards against accidentally adding development-only imports to the
    runtime path.
    """

    script = """
import importlib.abc
import sys


class BlockMypyc(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "mypyc" or fullname.startswith("mypyc."):
            raise ModuleNotFoundError(fullname)
        return None


sys.meta_path.insert(0, BlockMypyc())
import typedlogic.compiler
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
    subprocess.run([sys.executable, "-c", script], check=True, env=env)
