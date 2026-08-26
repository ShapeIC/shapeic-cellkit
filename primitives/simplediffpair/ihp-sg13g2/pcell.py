"""IHP SG13G2 implementation of the simple differential pair."""

from __future__ import annotations

import importlib.util
from functools import cache
from pathlib import Path

LAYOUT_POLICY = "symmetric-adjacent-with-edge-dummies-v3"
IMPLEMENTATION_FILES = (
    Path(__file__).resolve().parents[3] / "technologies/ihp-sg13g2/pcells.py",
)


def build(geometry):
    return _implementation().build_simplediffpair(geometry)


@cache
def _implementation():
    path = IMPLEMENTATION_FILES[0]
    spec = importlib.util.spec_from_file_location(
        "_shapeic_cellkit_ihp_sg13g2_pcells", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load IHP PCell implementation: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
