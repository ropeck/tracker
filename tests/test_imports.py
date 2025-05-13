"""Check syntax of all python code by importing all modules."""

import importlib
import pathlib


def test_all_scripts_import() -> None:
    scripts = pathlib.Path("scripts").glob("*.py")
    for path in scripts:
        mod = f"scripts.{path.stem}"
        importlib.import_module(mod)
