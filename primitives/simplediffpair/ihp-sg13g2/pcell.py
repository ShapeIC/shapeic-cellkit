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
    technology = _technology()
    gf, cells, mos_core, tech = technology._backend()
    component = _simple_diff_pair(
        gf,
        cells,
        mos_core,
        tech,
        geometry.length_m * 1.0e6,
        geometry.finger_width_m * 1.0e6,
        geometry.nf,
    )
    technology._validate_external_port_isolation(
        component, gf.kdb, ("DP", "DN", "GP", "GN", "S", "B")
    )
    return component


def _simple_diff_pair(gf, cells, mos_core, tech, length, wf, nf):
    technology = _technology()
    component = gf.Component(technology._cell_name("simplediffpair", length, wf, nf))
    device = technology._bussed_mos_device(gf, mos_core, tech, "nmos", length, wf, nf)
    pitch = float(device.dbbox().right) - float(device.dbbox().left) + 1.2
    left = component.add_ref(device)
    right = component.add_ref(device)
    left.move((-pitch / 2, 0))
    right.move((pitch / 2, 0))
    dummy_left = component.add_ref(device)
    dummy_right = component.add_ref(device)
    dummy_left.move((-3.0 * pitch / 2, 0))
    dummy_right.move((3.0 * pitch / 2, 0))

    devices = (left, right, dummy_left, dummy_right)
    source_y = min(float(ref.dbbox().bottom) for ref in devices) - 1.0
    source = (0.0, source_y)
    for ref in devices:
        technology._wire(component, technology._point(ref.ports["S"]), source)
    for ref in (dummy_left, dummy_right):
        technology._wire(component, technology._point(ref.ports["D"]), source)
        technology._wire(component, technology._point(ref.ports["G"]), source)

    bulk_ref = component.add_ref(
        cells.ptap1(width=technology.IHP_TAP_SIZE_UM, length=technology.IHP_TAP_SIZE_UM)
    )
    bulk_ref.move((0.0, source_y - 1.5))
    technology._add_external_ports(
        component,
        {
            "DP": technology._point(left.ports["D"]),
            "DN": technology._point(right.ports["D"]),
            "GP": technology._point(left.ports["G"]),
            "GN": technology._point(right.ports["G"]),
            "S": source,
            "B": technology._point(bulk_ref.ports["TAP"]),
        },
    )
    return component


@cache
def _technology():
    path = IMPLEMENTATION_FILES[0]
    spec = importlib.util.spec_from_file_location(
        "_shapeic_cellkit_ihp_sg13g2_pcells", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load IHP technology layout helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
