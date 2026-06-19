import importlib


def test_package_imports():
    mod = importlib.import_module("jailbird")
    assert mod.__version__ == "0.1.0"
