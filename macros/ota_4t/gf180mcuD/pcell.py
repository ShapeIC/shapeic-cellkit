"""GF180MCU D physical implementation of the four-transistor OTA."""

from __future__ import annotations

import importlib.util
from functools import cache
from pathlib import Path

LAYOUT_POLICY = "symmetric-native-fingers-with-edge-dummies-v3"
IMPLEMENTATION_FILES = (
    Path(__file__).resolve().parents[3] / "technologies/gf180mcuD/pcells.py",
    Path(__file__).resolve().parents[3] / "primitives/simplediffpair/gf180mcuD/pcell.py",
    Path(__file__).resolve().parents[3] / "primitives/simplecurrentmirror/gf180mcuD/pcell.py",
)


def build(instances):
    if set(instances) != {"xdp", "xcm"}:
        raise ValueError("ota_4t requires exactly xdp and xcm geometries")
    diff = _primitive("simplediffpair").build(instances["xdp"], label_ports=False)
    mirror = _primitive("simplecurrentmirror").build(instances["xcm"], label_ports=False)
    return _implementation().build_ota_4t(instances, diff, mirror)


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


@cache
def _primitive(name):
    path = next(path for path in IMPLEMENTATION_FILES[1:] if path.parents[1].name == name)
    spec = importlib.util.spec_from_file_location(
        f"_shapeic_cellkit_{path.parent.name}_{name}", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load primitive PCell: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
