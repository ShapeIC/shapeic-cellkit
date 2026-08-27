"""GF180MCU D primitive PCells for ShapeIC physical characterization."""

from __future__ import annotations

import math

GF180MCU_PACKAGE_VERSION = "1.0.0"
LAYOUT_POLICY = "symmetric-native-fingers-with-edge-dummies-v2"

ROUTE_WIDTH_UM = 0.30
BUS_CLEARANCE_UM = 0.55
GRID_UM = 0.005


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
        import gf180mcu
        from gf180mcu.cells import nfet, pfet
        from gf180mcu.layers import LAYER
    except ImportError as error:
        raise RuntimeError(
            "the GF180MCU D PCells require gf180mcu==1.0.0 in a PDK-specific "
            "environment; see shapeic-layout/lut_generation/requirements-gf180.txt"
        ) from error
    if gf180mcu.__version__ != GF180MCU_PACKAGE_VERSION:
        raise RuntimeError(
            "the GF180MCU D PCells require "
            f"gf180mcu=={GF180MCU_PACKAGE_VERSION}, found {gf180mcu.__version__}"
        )
    gf180mcu.PDK.activate()
    return gf, LAYER, nfet, pfet


def _gf180_mos_device(factory, kind, length, wf, nf):
    if kind not in {"nmos", "pmos"}:
        raise ValueError(f"unsupported MOS kind '{kind}'")
    if not math.isfinite(length) or not math.isfinite(wf):
        raise ValueError("MOS length and finger width must be finite")
    length = _snap(length)
    wf = _snap(wf)
    if length < 0.28:
        raise ValueError(f"{kind} length={length} is below the 0.28 um minimum")
    if wf < 0.22:
        raise ValueError(f"{kind} finger width={wf} is below the 0.22 um minimum")
    if isinstance(nf, bool) or not isinstance(nf, int) or nf < 1:
        raise ValueError(f"{kind} nf must be a positive integer")
    return factory(
        l_gate=length,
        w_gate=wf,
        nf=nf,
        grw=0.22,
        volt="3.3V",
    )


def _bussed_mos(gf, layer, factory, kind, length, wf, nf):
    length = _snap(length)
    wf = _snap(wf)
    raw = _gf180_mos_device(factory, kind, length, wf, nf)
    component = _component(gf, _cell_name(f"{kind}_bussed", length, wf, nf))
    component.add_ref(raw)

    gate_to_diffusion, gate_to_poly, pitch = _mos_dimensions(length, wf)
    gate_x = [
        _snap(-((nf - 1) / 2.0) * pitch + index * pitch)
        for index in range(nf)
    ]
    gate_y = -(wf / 2.0 + gate_to_poly)
    gate_points = [(x, gate_y) for x in gate_x]
    gate_bus_y = gate_y
    for point in gate_points:
        _add_stack(component, layer, point, 1, 3)
        _wire(component, layer.metal3, point, (point[0], gate_bus_y))
    gate = ((min(gate_x) + max(gate_x)) / 2.0, gate_bus_y)
    _wire(
        component,
        layer.metal3,
        (min(gate_x), gate_bus_y),
        (max(gate_x), gate_bus_y),
    )

    left = gate_x[0] - (length / 2.0 + gate_to_diffusion)
    sd_x = [_snap(left + index * pitch) for index in range(nf + 1)]
    drain_points = [(x, 0.0) for index, x in enumerate(sd_x) if index % 2 == 0]
    source_points = [(x, 0.0) for index, x in enumerate(sd_x) if index % 2 == 1]
    top = float(raw.dbbox().top)
    bottom = float(raw.dbbox().bottom)
    source_y = top + BUS_CLEARANCE_UM
    drain_y = bottom - BUS_CLEARANCE_UM
    for point in source_points:
        _add_stack(component, layer, point, 1, 2)
        _wire(component, layer.metal2, point, (point[0], source_y))
    for point in drain_points:
        _add_stack(component, layer, point, 1, 3)
        _wire(component, layer.metal3, point, (point[0], drain_y))
    source = (_mean_x(source_points), source_y)
    drain = (_mean_x(drain_points), drain_y)
    _wire(
        component,
        layer.metal2,
        (min(x for x, _ in source_points), source_y),
        (max(x for x, _ in source_points), source_y),
    )
    _wire(
        component,
        layer.metal3,
        (min(x for x, _ in drain_points), drain_y),
        (max(x for x, _ in drain_points), drain_y),
    )

    body = _guard_ring_body_point(length, wf, nf, pitch)
    _add_stack(component, layer, body, 1, 4)

    _add_port(component, layer, "G", gate, 3)
    _add_port(component, layer, "S", source, 2)
    _add_port(component, layer, "D", drain, 3)
    _add_port(component, layer, "B", body, 4)
    return component


def _simple_diff_pair(gf, layer, device, geometry):
    component = _component(
        gf,
        _cell_name(
            "simplediffpair",
            geometry.length_m * 1e6,
            geometry.finger_width_m * 1e6,
            geometry.nf,
        ),
    )
    refs = _place_four(component, device)
    left, right, dummy_left, dummy_right = refs
    source_y = max(float(ref.dbbox().top) for ref in refs) + 0.9
    source = (0.0, source_y)
    for ref in refs:
        terminal = _point(ref.ports["S"])
        _wire(component, layer.metal2, terminal, (terminal[0], source_y))
    _wire_terminal_span(component, layer.metal2, refs, ("G", "D", "S"), source_y)
    for ref in (dummy_left, dummy_right):
        _tie_dummy_to_source(component, layer, ref, source_y)

    bulk_y = min(float(ref.dbbox().bottom) for ref in refs) - 0.9
    bulk = (0.0, bulk_y)
    for ref in refs:
        terminal = _point(ref.ports["B"])
        _wire(component, layer.metal4, terminal, (terminal[0], bulk_y))
    _wire_across(component, layer.metal4, refs, "B", bulk_y)

    _copy_port(component, layer, "DP", left.ports["D"], 3)
    _copy_port(component, layer, "DN", right.ports["D"], 3)
    _copy_port(component, layer, "GP", left.ports["G"], 3)
    _copy_port(component, layer, "GN", right.ports["G"], 3)
    _add_port(component, layer, "S", source, 2)
    _add_port(component, layer, "B", bulk, 4)
    return component


def _current_mirror(gf, layer, device, geometry):
    component = _component(
        gf,
        _cell_name(
            "currentmirror",
            geometry.length_m * 1e6,
            geometry.finger_width_m * 1e6,
            geometry.nf,
        ),
    )
    refs = _place_four(component, device)
    output, reference, dummy_left, dummy_right = refs
    source_y = max(float(ref.dbbox().top) for ref in refs) + 0.9
    source = (0.0, source_y)
    for ref in refs:
        terminal = _point(ref.ports["S"])
        _wire(component, layer.metal2, terminal, (terminal[0], source_y))
    _wire_terminal_span(component, layer.metal2, refs, ("G", "D", "S"), source_y)
    for ref in (dummy_left, dummy_right):
        _tie_dummy_to_source(component, layer, ref, source_y)

    reference_drain = _point(reference.ports["D"])
    output_gate = _point(output.ports["G"])
    reference_gate = _point(reference.ports["G"])
    gate_bus_y = source_y
    output_gate_bus = (output_gate[0], gate_bus_y)
    reference_gate_bus = (reference_gate[0], gate_bus_y)
    _wire(component, layer.metal3, output_gate, output_gate_bus)
    _wire(component, layer.metal3, reference_gate, reference_gate_bus)
    _wire(component, layer.metal3, output_gate_bus, reference_gate_bus)
    _wire(
        component,
        layer.metal3,
        reference_drain,
        (reference_drain[0], gate_bus_y),
    )

    bulk_y = min(float(ref.dbbox().bottom) for ref in refs) - 0.9
    bulk = (0.0, bulk_y)
    for ref in refs:
        terminal = _point(ref.ports["B"])
        _wire(component, layer.metal4, terminal, (terminal[0], bulk_y))
    _wire_across(component, layer.metal4, refs, "B", bulk_y)

    _copy_port(component, layer, "DOUT", output.ports["D"], 3)
    _copy_port(component, layer, "DREF", reference.ports["D"], 3)
    _add_port(component, layer, "S", source, 2)
    _add_port(component, layer, "B", bulk, 4)
    return component


def _mos_dimensions(length, wf):
    contact_size = 0.23
    diffusion_surround = 0.065
    diffusion_poly_space = 0.10
    gate_to_diffusion = 0.26
    minimum_contacted_width = contact_size + 2.0 * diffusion_surround
    contact_stem = gate_to_diffusion - minimum_contacted_width / 2.0
    growth = diffusion_poly_space - contact_stem
    if wf + 0.0005 < minimum_contacted_width and growth > 0.0:
        gate_to_diffusion += growth

    gate_to_poly = 0.28
    minimum_poly_contact = contact_size + 2.0 * diffusion_surround
    if wf + 0.0005 < minimum_contacted_width and length + 0.0005 < minimum_poly_contact:
        gate_to_poly += (minimum_poly_contact - wf) / 2.0

    diffusion_growth = max(0.23, gate_to_diffusion + contact_size / 2.0)
    finger_extent = 2.0 * (
        length / 2.0 + diffusion_growth + diffusion_surround
    )
    pitch = finger_extent - (2.0 * diffusion_surround + contact_size)
    return _snap(gate_to_diffusion), _snap(gate_to_poly), _snap(pitch)


def _guard_ring_body_point(length, wf, nf, pitch):
    gate_to_diffusion, gate_to_poly, _ = _mos_dimensions(length, wf)
    diffusion_growth = max(0.23, gate_to_diffusion + 0.23 / 2.0)
    finger_extent = 2.0 * (length / 2.0 + diffusion_growth + 0.065)
    core_x = (nf - 1) * pitch + finger_extent
    core_y = wf + 2.0 * max(0.22, gate_to_poly + 0.065 + 0.23 / 2.0)
    guard_x = core_x + 2.0 * (0.33 + 0.065) + 0.23
    guard_y = core_y + 2.0 * (0.10 + 0.065) + 0.23
    return (-_snap(guard_x / 2.0), _snap(guard_y / 2.0))


def _place_four(component, device):
    width = float(device.dbbox().right) - float(device.dbbox().left)
    pitch = width + 1.2
    refs = tuple(component.add_ref(device) for _ in range(4))
    for ref, offset in zip(refs, (-0.5, 0.5, -1.5, 1.5), strict=True):
        ref.move((offset * pitch, 0.0))
    return refs


def _tie_dummy_to_source(component, layer, ref, source_y):
    gate = _point(ref.ports["G"])
    drain = _point(ref.ports["D"])
    _add_stack(component, layer, gate, 2, 3)
    _add_stack(component, layer, drain, 2, 3)
    for terminal in (gate, drain):
        _wire(component, layer.metal2, terminal, (terminal[0], source_y))


def _wire_across(component, routing_layer, refs, port, y):
    xs = [_point(ref.ports[port])[0] for ref in refs]
    _wire(component, routing_layer, (min(xs), y), (max(xs), y))


def _wire_terminal_span(component, routing_layer, refs, ports, y):
    xs = [_point(ref.ports[port])[0] for ref in refs for port in ports]
    _wire(component, routing_layer, (min(xs), y), (max(xs), y))


def _add_stack(component, layer, center, first, last):
    metals = {
        1: layer.metal1,
        2: layer.metal2,
        3: layer.metal3,
        4: layer.metal4,
    }
    vias = {1: layer.via1, 2: layer.via2, 3: layer.via3}
    via_sizes = {1: 0.26, 2: 0.28, 3: 0.28}
    metal_sizes = {1: 0.40, 2: 0.42, 3: 0.42, 4: 0.42}
    low, high = sorted((first, last))
    for metal in range(low, high + 1):
        _square(component, metals[metal], center, metal_sizes[metal])
    for via in range(low, high):
        _square(component, vias[via], center, via_sizes[via])


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
    drawing_layer = getattr(layer, f"metal{metal}")
    label_layer = getattr(layer, f"metal{metal}_label")
    component.add_port(
        name=name,
        center=center,
        width=ROUTE_WIDTH_UM,
        orientation=0,
        layer=drawing_layer,
        port_type="electrical",
    )
    component.add_label(text=name, position=center, layer=label_layer)


def _copy_port(component, layer, name, port, metal):
    _add_port(component, layer, name, _point(port), metal)


def _mean_x(points):
    return sum(x for x, _ in points) / len(points)


def _point(port):
    return float(port.center[0]), float(port.center[1])


def _snap(value):
    return round(value / GRID_UM) * GRID_UM


def _component(gf, name):
    return gf.Component(kdb_cell=gf.kcl.create_cell(name, allow_duplicate=True))


def _cell_name(primitive, length, wf, nf):
    return f"{primitive}_l{length:.3f}_wf{wf:.3f}_nf{nf}".replace(".", "p")
