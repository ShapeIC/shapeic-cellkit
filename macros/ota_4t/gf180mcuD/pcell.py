"""GF180MCU D physical implementation of the four-transistor OTA."""

from __future__ import annotations

import importlib.util
from functools import cache
from pathlib import Path

LAYOUT_POLICY = "symmetric-native-fingers-with-edge-dummies-v3"
IMPLEMENTATION_FILES = (
    Path(__file__).resolve().parents[3] / "technologies/gf180mcuD/pcells.py",
)


def build(instances):
    return _implementation().build_ota_4t(instances)


@cache
def _implementation():
    path = IMPLEMENTATION_FILES[0]
    spec = importlib.util.spec_from_file_location(
        "_shapeic_cellkit_gf180_macro_pcells", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load GF180MCU D macro PCell implementation: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
