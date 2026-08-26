"""SKY130A implementation of the simple differential pair."""

from __future__ import annotations

import importlib.util
from functools import cache
from pathlib import Path

LAYOUT_POLICY = "symmetric-native-fingers-with-edge-dummies-v1"
IMPLEMENTATION_FILES = (
    Path(__file__).resolve().parents[3] / "technologies/sky130A/pcells.py",
)


def build(geometry):
    return _implementation().build_simplediffpair(geometry)


@cache
def _implementation():
    path = IMPLEMENTATION_FILES[0]
    spec = importlib.util.spec_from_file_location("_shapeic_cellkit_sky130_pcells", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load SKY130A PCell implementation: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
