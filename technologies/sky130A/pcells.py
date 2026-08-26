"""SKY130A primitive PCells for ShapeIC physical characterization."""

from __future__ import annotations

import math

SKY130_PACKAGE_VERSION = "1.0.0"
LAYOUT_POLICY = "symmetric-native-fingers-with-edge-dummies-v1"

ROUTE_WIDTH_UM = 0.30
BUS_CLEARANCE_UM = 0.45


def build_simplediffpair(geometry):
    gf, layer, nfet, _pfet = _backend()
    device = _bussed_mos(
        gf,
        layer,
        nfet,
        "nmos",
        geometry.length_m * 1.0e6,
        geometry.finger_width_m * 1.0e6,
        geometry.nf,
    )
    return _simple_diff_pair(gf, layer, device, geometry)


def build_currentmirror(geometry):
    gf, layer, _nfet, pfet = _backend()
    device = _bussed_mos(
        gf,
        layer,
        pfet,
        "pmos",
        geometry.length_m * 1.0e6,
        geometry.finger_width_m * 1.0e6,
        geometry.nf,
    )
    return _current_mirror(gf, layer, device, geometry)


def _backend():
    try:
        import gdsfactory as gf
        import sky130
        from sky130.layers import LAYER
        from sky130.pcells.mosfets import (
            sky130_fd_pr__nfet_01v8,
            sky130_fd_pr__pfet_01v8,
        )
    except ImportError as error:
        raise RuntimeError(
            "the SKY130A PCells require sky130==1.0.0 in a PDK-specific "
            "environment; see shapeic-layout/lut_generation/"
            "requirements-sky130.txt"
        ) from error
    if sky130.__version__ != SKY130_PACKAGE_VERSION:
        raise RuntimeError(
            "the SKY130A PCells require "
            f"sky130=={SKY130_PACKAGE_VERSION}, found {sky130.__version__}"
        )
    sky130.PDK.activate()
    return gf, LAYER, sky130_fd_pr__nfet_01v8, sky130_fd_pr__pfet_01v8


def _sky130_mos_device(factory, kind, length, wf, nf):
    if kind not in {"nmos", "pmos"}:
        raise ValueError(f"unsupported MOS kind '{kind}'")
    if not math.isfinite(length) or not math.isfinite(wf):
        raise ValueError("MOS length and finger width must be finite")
    # The public geometry arrives in SI and can produce values such as
    # 0.41999999999999993 um after conversion. SKY130 geometry is defined on
    # a 5 nm grid, so normalize before applying its hard limits.
    length = _snap(length)
    wf = _snap(wf)
    if length < 0.15:
        raise ValueError(f"{kind} length={length} is below the 0.15 um minimum")
    if wf < 0.42:
        raise ValueError(f"{kind} finger width={wf} is below the 0.42 um minimum")
    if isinstance(nf, bool) or not isinstance(nf, int) or nf < 1:
        raise ValueError(f"{kind} nf must be a positive integer")
    return factory(
        gate_width=wf,
        gate_length=length,
        nf=nf,
        guard_ring=True,
    )


def _bussed_mos(gf, layer, factory, kind, length, wf, nf):
    raw = _sky130_mos_device(factory, kind, length, wf, nf)
    component = gf.Component(_cell_name(f"{kind}_bussed", length, wf, nf))
    component.add_ref(raw)

    gate_to_contact = 0.275 if kind == "nmos" else 0.320
    gate_x = _gate_centers(length, nf)
    gate_points = [
        (x, _gate_contact_y(index, length, wf, nf, gate_to_contact))
        for index, x in enumerate(gate_x)
    ]
    # Keep the gate bus between the poly contact and the guard ring. A larger
    # offset overlaps the body stack at the minimum 0.42 um device width.
    gate_bus_y = -(wf / 2.0 + gate_to_contact + 0.12)
    for point in gate_points:
        _wire(component, layer.met1drawing, point, (point[0], gate_bus_y))
    gate = ((min(gate_x) + max(gate_x)) / 2.0, gate_bus_y)
    _wire(
        component,
        layer.met1drawing,
        (min(gate_x), gate_bus_y),
        (max(gate_x), gate_bus_y),
    )

    sd_x = _source_drain_centers(length, nf)
    source_parity = nf % 2
    source_points = [(x, 0.0) for index, x in enumerate(sd_x) if index % 2 == source_parity]
    drain_points = [(x, 0.0) for index, x in enumerate(sd_x) if index % 2 != source_parity]
    top = float(raw.dbbox().top)
    bottom = float(raw.dbbox().bottom)
    source_y = top + BUS_CLEARANCE_UM
    drain_y = bottom - BUS_CLEARANCE_UM
    for point in source_points:
        _add_stack(component, layer, point, 1, 2)
        _wire(component, layer.met2drawing, point, (point[0], source_y))
    for point in drain_points:
        _add_stack(component, layer, point, 1, 3)
        _wire(component, layer.met3drawing, point, (point[0], drain_y))
    source = (_mean_x(source_points), source_y)
    drain = (_mean_x(drain_points), drain_y)
    _wire(
        component,
        layer.met2drawing,
        (min(x for x, _ in source_points), source_y),
        (max(x for x, _ in source_points), source_y),
    )
    _wire(
        component,
        layer.met3drawing,
        (min(x for x, _ in drain_points), drain_y),
        (max(x for x, _ in drain_points), drain_y),
    )

    body = _guard_ring_body_point(length, wf, nf, gate_to_contact)
    _add_li1_to_metal1(component, layer, body)
    _add_stack(component, layer, body, 1, 4)

    _add_port(component, layer, "G", gate, 1)
    _add_port(component, layer, "S", source, 2)
    _add_port(component, layer, "D", drain, 3)
    _add_port(component, layer, "B", body, 4)
    return component


def _simple_diff_pair(gf, layer, device, geometry):
    component = gf.Component(
        _cell_name(
            "simplediffpair",
            geometry.length_m * 1e6,
            geometry.finger_width_m * 1e6,
            geometry.nf,
        )
    )
    refs = _place_four(component, device)
    left, right, dummy_left, dummy_right = refs
    source_y = max(float(ref.dbbox().top) for ref in refs) + 0.8
    source = (0.0, source_y)
    for ref in refs:
        terminal = _point(ref.ports["S"])
        _wire(component, layer.met2drawing, terminal, (terminal[0], source_y))
    _wire_terminal_span(
        component, layer.met2drawing, refs, ("G", "D", "S"), source_y
    )
    for ref in (dummy_left, dummy_right):
        _tie_dummy_to_source(component, layer, ref, source_y)

    bulk_y = min(float(ref.dbbox().bottom) for ref in refs) - 0.8
    bulk = (0.0, bulk_y)
    for ref in refs:
        terminal = _point(ref.ports["B"])
        _wire(component, layer.met4drawing, terminal, (terminal[0], bulk_y))
    _wire_across(component, layer.met4drawing, refs, "B", bulk_y)

    _copy_port(component, layer, "DP", left.ports["D"], 3)
    _copy_port(component, layer, "DN", right.ports["D"], 3)
    _copy_port(component, layer, "GP", left.ports["G"], 1)
    _copy_port(component, layer, "GN", right.ports["G"], 1)
    _add_port(component, layer, "S", source, 2)
    _add_port(component, layer, "B", bulk, 4)
    return component


def _current_mirror(gf, layer, device, geometry):
    component = gf.Component(
        _cell_name(
            "currentmirror",
            geometry.length_m * 1e6,
            geometry.finger_width_m * 1e6,
            geometry.nf,
        )
    )
    refs = _place_four(component, device)
    output, reference, dummy_left, dummy_right = refs
    source_y = max(float(ref.dbbox().top) for ref in refs) + 0.8
    source = (0.0, source_y)
    for ref in refs:
        terminal = _point(ref.ports["S"])
        _wire(component, layer.met2drawing, terminal, (terminal[0], source_y))
    _wire_terminal_span(
        component, layer.met2drawing, refs, ("G", "D", "S"), source_y
    )
    for ref in (dummy_left, dummy_right):
        _tie_dummy_to_source(component, layer, ref, source_y)

    reference_drain = _point(reference.ports["D"])
    _add_stack(component, layer, reference_drain, 1, 3)
    output_gate = _point(output.ports["G"])
    reference_gate = _point(reference.ports["G"])
    gate_y = min(output_gate[1], reference_gate[1])
    _wire(
        component,
        layer.met1drawing,
        output_gate,
        reference_gate,
    )
    _wire(
        component,
        layer.met1drawing,
        reference_drain,
        (reference_drain[0], gate_y),
    )
    _wire(
        component,
        layer.met1drawing,
        (reference_drain[0], gate_y),
        reference_gate,
    )

    bulk_y = min(float(ref.dbbox().bottom) for ref in refs) - 0.8
    bulk = (0.0, bulk_y)
    for ref in refs:
        terminal = _point(ref.ports["B"])
        _wire(component, layer.met4drawing, terminal, (terminal[0], bulk_y))
    _wire_across(component, layer.met4drawing, refs, "B", bulk_y)

    _copy_port(component, layer, "DOUT", output.ports["D"], 3)
    _copy_port(component, layer, "DREF", reference.ports["D"], 3)
    _add_port(component, layer, "S", source, 2)
    _add_port(component, layer, "B", bulk, 4)
    return component


def _place_four(component, device):
    width = float(device.dbbox().right) - float(device.dbbox().left)
    pitch = width + 1.0
    refs = tuple(component.add_ref(device) for _ in range(4))
    # Return active-left, active-right, dummy-left, dummy-right.
    for ref, offset in zip(refs, (-0.5, 0.5, -1.5, 1.5), strict=True):
        ref.move((offset * pitch, 0.0))
    return refs


def _tie_dummy_to_source(component, layer, ref, source_y):
    gate = _point(ref.ports["G"])
    drain = _point(ref.ports["D"])
    _add_stack(component, layer, gate, 1, 2)
    _add_stack(component, layer, drain, 2, 3)
    for terminal in (gate, drain):
        _wire(component, layer.met2drawing, terminal, (terminal[0], source_y))


def _wire_across(component, routing_layer, refs, port, y):
    xs = [_point(ref.ports[port])[0] for ref in refs]
    _wire(component, routing_layer, (min(xs), y), (max(xs), y))


def _wire_terminal_span(component, routing_layer, refs, ports, y):
    xs = [_point(ref.ports[port])[0] for ref in refs for port in ports]
    _wire(component, routing_layer, (min(xs), y), (max(xs), y))


def _gate_centers(length, nf):
    if nf == 1:
        return [0.0]
    shared = max(0.145, 0.165 if length < 0.17 else 0.145)
    pitch = max(length + 2.0 * shared, 0.48)
    return [_snap(-((nf - 1) / 2.0) * pitch + index * pitch) for index in range(nf)]


def _source_drain_centers(length, nf):
    if nf == 1:
        return [-(length / 2.0 + 0.145), length / 2.0 + 0.145]
    shared = max(0.145, 0.165 if length < 0.17 else 0.145)
    pitch = max(length + 2.0 * shared, 0.48)
    return [_snap(-(nf / 2.0) * pitch + index * pitch) for index in range(nf + 1)]


def _gate_contact_y(index, length, wf, nf, gate_to_contact):
    if nf == 1 or length >= 0.26:
        side = -1.0
    else:
        side = -1.0 if index % 2 == 0 else 1.0
    return side * (wf / 2.0 + gate_to_contact)


def _guard_ring_body_point(length, wf, nf, gate_to_contact):
    if nf == 1:
        diffusion_half_x = length / 2.0 + 0.29
    else:
        diffusion_half_x = abs(_source_drain_centers(length, nf)[-1]) + 0.145
    ring_center_x = diffusion_half_x + 0.125 + 0.215 + 0.085
    ring_center_y = wf / 2.0 + gate_to_contact + 0.51
    return (-ring_center_x, -ring_center_y)


def _add_li1_to_metal1(component, layer, center):
    _square(component, layer.mcondrawing, center, 0.17)
    _square(component, layer.met1drawing, center, 0.23)


def _add_stack(component, layer, center, first, last):
    metal_layers = {
        1: layer.met1drawing,
        2: layer.met2drawing,
        3: layer.met3drawing,
        4: layer.met4drawing,
    }
    via_layers = {
        1: layer.viadrawing,
        2: layer.via2drawing,
        3: layer.via3drawing,
    }
    via_sizes = {1: 0.15, 2: 0.20, 3: 0.20}
    metal_sizes = {1: 0.30, 2: 0.32, 3: 0.32, 4: 0.32}
    low, high = sorted((first, last))
    for metal in range(low, high + 1):
        _square(component, metal_layers[metal], center, metal_sizes[metal])
    for via in range(low, high):
        _square(component, via_layers[via], center, via_sizes[via])


def _wire(component, layer, start, stop):
    x1, y1 = start
    x2, y2 = stop
    if abs(y2 - y1) > 1.0e-12:
        _rectangle(
            component,
            layer,
            x1 - ROUTE_WIDTH_UM / 2.0,
            min(y1, y2) - ROUTE_WIDTH_UM / 2.0,
            x1 + ROUTE_WIDTH_UM / 2.0,
            max(y1, y2) + ROUTE_WIDTH_UM / 2.0,
        )
    if abs(x2 - x1) > 1.0e-12:
        _rectangle(
            component,
            layer,
            min(x1, x2) - ROUTE_WIDTH_UM / 2.0,
            y2 - ROUTE_WIDTH_UM / 2.0,
            max(x1, x2) + ROUTE_WIDTH_UM / 2.0,
            y2 + ROUTE_WIDTH_UM / 2.0,
        )


def _square(component, layer, center, size):
    x, y = center
    _rectangle(
        component,
        layer,
        x - size / 2.0,
        y - size / 2.0,
        x + size / 2.0,
        y + size / 2.0,
    )


def _rectangle(component, layer, left, bottom, right, top):
    component.add_polygon(
        [(left, bottom), (right, bottom), (right, top), (left, top)], layer=layer
    )


def _add_port(component, layer, name, center, metal):
    pin_layer = getattr(layer, f"met{metal}pin")
    component.add_port(
        name=name,
        center=center,
        width=ROUTE_WIDTH_UM,
        orientation=0,
        layer=pin_layer,
        port_type="electrical",
    )
    # SKY130 Magic only promotes labels on the PIN datatype to subcircuit ports.
    component.add_label(text=name, position=center, layer=pin_layer)


def _copy_port(component, layer, name, port, metal):
    _add_port(component, layer, name, _point(port), metal)


def _mean_x(points):
    return sum(x for x, _ in points) / len(points)


def _point(port):
    return float(port.center[0]), float(port.center[1])


def _snap(value):
    return round(value / 0.005) * 0.005


def _cell_name(primitive, length, wf, nf):
    return f"{primitive}_l{length:.3f}_wf{wf:.3f}_nf{nf}".replace(".", "p")
