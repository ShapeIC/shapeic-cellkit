"""IHP SG13G2 implementation of the simple current mirror."""

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
    component = _current_mirror(
        gf,
        cells,
        mos_core,
        tech,
        geometry.length_m * 1.0e6,
        geometry.finger_width_m * 1.0e6,
        geometry.nf,
    )
    technology._validate_external_port_isolation(
        component, gf.kdb, ("DOUT", "DREF", "S", "B")
    )
    return component


def _current_mirror(gf, cells, mos_core, tech, length, wf, nf):
    technology = _technology()
    component = gf.Component(technology._cell_name("currentmirror", length, wf, nf))
    device = technology._bussed_mos_device(gf, mos_core, tech, "pmos", length, wf, nf)
    pitch = float(device.dbbox().right) - float(device.dbbox().left) + 1.2
    output = component.add_ref(device)
    reference = component.add_ref(device)
    output.move((-pitch / 2, 0))
    reference.move((pitch / 2, 0))
    dummy_left = component.add_ref(device)
    dummy_right = component.add_ref(device)
    dummy_left.move((-3.0 * pitch / 2, 0))
    dummy_right.move((3.0 * pitch / 2, 0))

    devices = (output, reference, dummy_left, dummy_right)
    source_y = max(float(ref.dbbox().top) for ref in devices) + 1.0
    source = (0.0, source_y)
    for ref in devices:
        technology._wire(component, technology._point(ref.ports["S"]), source)
    for ref in (dummy_left, dummy_right):
        technology._wire(component, technology._point(ref.ports["D"]), source)
        technology._wire(component, technology._point(ref.ports["G"]), source)

    reference_drain = technology._point(reference.ports["D"])
    gate_bus = (0.0, min(float(ref.dbbox().bottom) for ref in devices) - 1.0)
    for terminal in (
        technology._point(output.ports["G"]),
        technology._point(reference.ports["G"]),
        reference_drain,
    ):
        technology._wire(component, terminal, gate_bus)
    bulk_ref = component.add_ref(
        cells.ntap1(width=technology.IHP_TAP_SIZE_UM, length=technology.IHP_TAP_SIZE_UM)
    )
    bulk_ref.move((0.0, source_y + 1.5))
    bulk = technology._point(bulk_ref.ports["TAP"])
    component.add_polygon(
        [
            (-2.0 * pitch, -wf / 2 - 1.0),
            (2.0 * pitch, -wf / 2 - 1.0),
            (2.0 * pitch, bulk[1] + 1.0),
            (-2.0 * pitch, bulk[1] + 1.0),
        ],
        layer="NWelldrawing",
    )
    technology._add_external_ports(
        component,
        {
            "DOUT": technology._point(output.ports["D"]),
            "DREF": reference_drain,
            "S": source,
            "B": bulk,
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
