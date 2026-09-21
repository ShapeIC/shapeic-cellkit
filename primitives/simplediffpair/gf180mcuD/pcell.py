"""GF180MCU D implementation of the simple differential pair."""

from __future__ import annotations

import importlib.util
from functools import cache
from pathlib import Path

LAYOUT_POLICY = "symmetric-native-fingers-with-edge-dummies-v3"
IMPLEMENTATION_FILES = (
    Path(__file__).resolve().parents[3] / "technologies/gf180mcuD/pcells.py",
)


def build(geometry, *, label_ports=True):
    technology = _technology()
    gf, layer, nfet, _pfet = technology._backend()
    device = technology._bussed_mos(
        gf,
        layer,
        nfet,
        "nmos",
        geometry.length_m * 1.0e6,
        geometry.finger_width_m * 1.0e6,
        geometry.nf,
    )
    return _simple_diff_pair(gf, layer, device, geometry, label_ports=label_ports)


def _simple_diff_pair(gf, layer, device, geometry, *, label_ports=True):
    technology = _technology()
    component = technology._component(
        gf,
        technology._cell_name(
            "simplediffpair",
            geometry.length_m * 1e6,
            geometry.finger_width_m * 1e6,
            geometry.nf,
        ),
    )
    refs = technology._place_four(component, device)
    left, right, dummy_left, dummy_right = refs
    source_y = max(float(ref.dbbox().top) for ref in refs) + 0.9
    source = (0.0, source_y)
    for ref in refs:
        terminal = technology._point(ref.ports["S"])
        technology._wire(component, layer.metal2, terminal, (terminal[0], source_y))
    technology._wire_terminal_span(component, layer.metal2, refs, ("G", "D", "S"), source_y)
    for ref in (dummy_left, dummy_right):
        technology._tie_dummy_to_source(component, layer, ref, source_y)

    bulk_y = min(float(ref.dbbox().bottom) for ref in refs) - 0.9
    bulk = (0.0, bulk_y)
    for ref in refs:
        terminal = technology._point(ref.ports["B"])
        technology._wire(component, layer.metal4, terminal, (terminal[0], bulk_y))
    technology._wire_across(component, layer.metal4, refs, "B", bulk_y)

    technology._copy_port(component, layer, "DP", left.ports["D"], 3, label=label_ports)
    technology._copy_port(component, layer, "DN", right.ports["D"], 3, label=label_ports)
    technology._copy_port(component, layer, "GP", left.ports["G"], 3, label=label_ports)
    technology._copy_port(component, layer, "GN", right.ports["G"], 3, label=label_ports)
    technology._add_port(component, layer, "S", source, 2, label=label_ports)
    technology._add_port(component, layer, "B", bulk, 4, label=label_ports)
    return component


@cache
def _technology():
    path = IMPLEMENTATION_FILES[0]
    spec = importlib.util.spec_from_file_location("_shapeic_cellkit_gf180_pcells", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load GF180MCU D technology layout helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
