import importlib
from typing import Iterable

import pytest


CANDIDATE_MODULES: tuple[str, ...] = (
    "therapy_ops_agent",
    "therapy_ops",
    "app",
    "src",
)


def _load_first_available_module(candidates: Iterable[str]):
    for module_name in candidates:
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
    return None


@pytest.fixture(scope="session")
def sut_module():
    module = _load_first_available_module(CANDIDATE_MODULES)
    if module is None:
        pytest.skip(
            "No SUT module found. Set one of: "
            + ", ".join(CANDIDATE_MODULES)
            + "."
        )
    return module


def resolve_attr(module, *names: str):
    for name in names:
        if hasattr(module, name):
            return getattr(module, name)
    pytest.skip(f"None of the expected attributes were found: {names}")
