# tests/test_imports.py
import importlib
import pathlib


def test_all_scripts_import():
    scripts = pathlib.Path("scripts").glob("*.py")
    for path in scripts:
        mod = f"scripts.{path.stem}"
        importlib.import_module(mod)
