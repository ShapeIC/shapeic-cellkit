"""SKY130A implementation of the simple current mirror."""

from __future__ import annotations

import importlib.util
from functools import cache
from pathlib import Path

LAYOUT_POLICY = "symmetric-native-fingers-with-edge-dummies-v1"
IMPLEMENTATION_FILES = (
    Path(__file__).resolve().parents[3] / "technologies/sky130A/pcells.py",
)


def build(geometry, *, label_ports=True):
    technology = _technology()
    gf, layer, _nfet, pfet = technology._backend()
    device = technology._bussed_mos(
        gf,
        layer,
        pfet,
        "pmos",
        geometry.length_m * 1.0e6,
        geometry.finger_width_m * 1.0e6,
        geometry.nf,
    )
    return _current_mirror(gf, layer, device, geometry, label_ports=label_ports)


def _current_mirror(gf, layer, device, geometry, *, label_ports=True):
    technology = _technology()
    component = technology._component(
        gf,
        technology._cell_name(
            "currentmirror",
            geometry.length_m * 1e6,
            geometry.finger_width_m * 1e6,
            geometry.nf,
        ),
    )
    refs = technology._place_four(component, device)
    output, reference, dummy_left, dummy_right = refs
    source_y = max(float(ref.dbbox().top) for ref in refs) + 0.8
    source = (0.0, source_y)
    for ref in refs:
        terminal = technology._point(ref.ports["S"])
        technology._wire(component, layer.met2drawing, terminal, (terminal[0], source_y))
    technology._wire_terminal_span(
        component, layer.met2drawing, refs, ("G", "D", "S"), source_y
    )
    for ref in (dummy_left, dummy_right):
        technology._tie_dummy_to_source(component, layer, ref, source_y)

    reference_drain = technology._point(reference.ports["D"])
    technology._add_stack(component, layer, reference_drain, 1, 3)
    output_gate = technology._point(output.ports["G"])
    reference_gate = technology._point(reference.ports["G"])
    gate_y = min(output_gate[1], reference_gate[1])
    technology._wire(
        component,
        layer.met1drawing,
        output_gate,
        reference_gate,
    )
    technology._wire(
        component,
        layer.met1drawing,
        reference_drain,
        (reference_drain[0], gate_y),
    )
    technology._wire(
        component,
        layer.met1drawing,
        (reference_drain[0], gate_y),
        reference_gate,
    )

    bulk_y = min(float(ref.dbbox().bottom) for ref in refs) - 0.8
    bulk = (0.0, bulk_y)
    for ref in refs:
        terminal = technology._point(ref.ports["B"])
        technology._wire(component, layer.met4drawing, terminal, (terminal[0], bulk_y))
    technology._wire_across(component, layer.met4drawing, refs, "B", bulk_y)

    technology._copy_port(component, layer, "DOUT", output.ports["D"], 3, label=label_ports)
    technology._copy_port(component, layer, "DREF", reference.ports["D"], 3, label=label_ports)
    technology._add_port(component, layer, "S", source, 2, label=label_ports)
    technology._add_port(component, layer, "B", bulk, 4, label=label_ports)
    return component


@cache
def _technology():
    path = IMPLEMENTATION_FILES[0]
    spec = importlib.util.spec_from_file_location("_shapeic_cellkit_sky130_pcells", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load SKY130A technology layout helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
