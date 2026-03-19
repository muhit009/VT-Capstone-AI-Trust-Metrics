"""
tests/conftest.py — Prevent heavyweight model loading during unit tests.

confidence/__init__.py imports confidence_engine which loads NLI models on
import. This conftest stubs out the package-level __init__ so individual
submodules (fusion, config) can be imported without triggering model loading.
"""
import sys
import types

# Register a lightweight stub for the confidence package *before* any test
# module imports it.  Individual submodules (fusion, config) are still loaded
# from disk; only the package-level __init__ (which would load the NLI
# pipeline) is replaced.
if "confidence" not in sys.modules:
    stub = types.ModuleType("confidence")
    stub.__path__ = ["confidence"]   # so sub-imports like confidence.fusion work
    stub.__package__ = "confidence"
    sys.modules["confidence"] = stub