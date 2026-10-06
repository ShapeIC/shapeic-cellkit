"""Shared ihp-sg13g2 device/routing helpers and OTA assembly."""

from __future__ import annotations

import math

IHP_GDSFACTORY_VERSION = "2.0.0"
IHP_TAP_SIZE_UM = 0.78
IHP_ROUTE_WIDTH_UM = 0.3
IHP_GATE_POLY_OVERLAP_UM = 0.02
IHP_BUS_CLEARANCE_UM = 0.2
LAYOUT_POLICY = "symmetric-adjacent-with-edge-dummies-v3"


def build_ota_4t(instances, diff_cell, mirror_cell):
    """Route the OTA using components built by its primitive providers."""
    gf, _cells, _mos_core, tech = _backend()
    diff_geometry = instances["xdp"]
    mirror_geometry = instances["xcm"]
    component = _ota_4t(gf, tech, diff_cell, mirror_cell, diff_geometry, mirror_geometry)
    _validate_external_port_isolation(
        component, gf.kdb, ("VOUT", "VINP", "VINN", "IBIAS", "VDD", "VSS")
    )
    return component


def _ota_4t(gf, tech, diff_cell, mirror_cell, diff_geometry, mirror_geometry):
    name = (
        f"ota_4t_ldp{diff_geometry.length_m * 1e6:.3f}"
        f"_wdp{diff_geometry.finger_width_m * 1e6:.3f}_ndp{diff_geometry.nf}"
        f"_lcm{mirror_geometry.length_m * 1e6:.3f}"
        f"_wcm{mirror_geometry.finger_width_m * 1e6:.3f}_ncm{mirror_geometry.nf}"
    ).replace(".", "p")
    component = gf.Component(name)
    diff = component.add_ref(diff_cell)
    mirror = component.add_ref(mirror_cell)
    mirror.move(
        (
            0.0,
            float(diff.dbbox().top) - float(mirror.dbbox().bottom) + 4.0,
        )
    )

    diff_dp = _point(diff.ports["DP"])
    diff_dn = _point(diff.ports["DN"])
    mirror_dout = _point(mirror.ports["DOUT"])
    mirror_dref = _point(mirror.ports["DREF"])
    left_x = min(
        float(diff.dbbox().left),
        float(mirror.dbbox().left),
        diff_dp[0],
        mirror_dout[0],
    ) - 1.0
    right_x = max(
        float(diff.dbbox().right),
        float(mirror.dbbox().right),
        diff_dn[0],
        mirror_dref[0],
    ) + 1.0
    vout = (left_x, (diff_dp[1] + mirror_dout[1]) / 2.0)
    internal = (right_x, (diff_dn[1] + mirror_dref[1]) / 2.0)
    for terminal in (diff_dp, diff_dn, mirror_dout, mirror_dref, vout):
        _add_metal1_metal2_via(component, tech, terminal)
    for terminal in (diff_dp, mirror_dout):
        _wire(component, terminal, vout, layer="Metal2drawing")
    for terminal in (diff_dn, mirror_dref):
        _wire(component, terminal, internal, layer="Metal2drawing")

    mirror_source = _point(mirror.ports["S"])
    mirror_bulk = _point(mirror.ports["B"])
    _wire(component, mirror_source, mirror_bulk)
    _add_external_ports(
        component,
        {
            "VOUT": vout,
            "VINP": _point(diff.ports["GP"]),
            "VINN": _point(diff.ports["GN"]),
            "IBIAS": _point(diff.ports["S"]),
            "VDD": mirror_bulk,
            "VSS": _point(diff.ports["B"]),
        },
    )
    return component


def _backend():
    try:
        import gdsfactory as gf
        import ihp
        from ihp import PDK, cells
        from ihp.cells.fet_transistors import TECH, _mos_core
    except ImportError as error:
        raise RuntimeError(
            "the IHP PCells require gdsfactory and ihp-gdsfactory"
        ) from error
    if ihp.__version__ != IHP_GDSFACTORY_VERSION:
        raise RuntimeError(
            "the IHP PCells require "
            f"ihp-gdsfactory=={IHP_GDSFACTORY_VERSION}, found {ihp.__version__}"
        )
    PDK.activate()
    return gf, cells, _mos_core, TECH


def _ihp_mos_device(mos_core, tech, kind, length, wf, nf):
    if kind not in {"nmos", "pmos"}:
        raise ValueError(f"unsupported MOS kind '{kind}'")
    if not math.isfinite(length) or not math.isfinite(wf):
        raise ValueError("MOS length and finger width must be finite")
    minimum_length = getattr(tech, f"{kind}_min_length")
    maximum_length = getattr(tech, f"{kind}_max_length")
    minimum_width = getattr(tech, f"{kind}_min_width")
    maximum_width = getattr(tech, f"{kind}_max_width")
    maximum_nf = getattr(tech, f"{kind}_max_nf")
    if not minimum_length <= length <= maximum_length:
        raise ValueError(
            f"{kind} length={length} out of range "
            f"[{minimum_length}, {maximum_length}]"
        )
    if not minimum_width <= wf <= maximum_width:
        raise ValueError(
            f"{kind} finger width={wf} out of range "
            f"[{minimum_width}, {maximum_width}]"
        )
    if isinstance(nf, bool) or not isinstance(nf, int) or not 1 <= nf <= maximum_nf:
        raise ValueError(f"{kind} nf={nf} out of range [1, {maximum_nf}]")
    return mos_core(
        width=wf * nf,
        length=length,
        nf=nf,
        is_pmos=kind == "pmos",
        is_hv=False,
    )


def _bussed_mos_device(gf, mos_core, tech, kind, length, wf, nf):
    raw = _ihp_mos_device(mos_core, tech, kind, length, wf, nf)
    component = gf.Component(_cell_name(f"{kind}_bussed", length, wf, nf))
    component.add_ref(raw)
    metal_columns = _layer_boxes(raw, "Metal1drawing")
    gate_fingers = _layer_boxes(raw, "GatPolydrawing")
    if len(metal_columns) != nf + 1:
        raise ValueError(
            f"{kind} nf={nf} exposes {len(metal_columns)} Metal1 columns; "
            f"expected {nf + 1}"
        )
    if len(gate_fingers) != nf:
        raise ValueError(
            f"{kind} nf={nf} exposes {len(gate_fingers)} gate fingers; expected {nf}"
        )

    source_columns = metal_columns[0::2]
    sd_ports = sorted(
        (port for port in raw.ports if port.name.startswith("SD") and port.name[2:].isdigit()),
        key=lambda port: int(port.name[2:]),
    )
    if [port.name for port in sd_ports] != [f"SD{i}" for i in range(nf + 1)]:
        raise ValueError(f"{kind} nf={nf} requires ports SD0 through SD{nf}")
    contact_cut_size = float(tech.cont_size)
    contact_pad_size = contact_cut_size + 2.0 * float(tech.gat_d)
    gate_bottom = min(box[1] for box in gate_fingers)
    gate_top = max(box[3] for box in gate_fingers)
    gate_bus_y = gate_bottom + IHP_GATE_POLY_OVERLAP_UM - contact_pad_size / 2.0
    contact_x = min(
        float(raw.dbbox().left)
        - float(tech.cont_gate_dist)
        - contact_pad_size / 2.0,
        source_columns[0][0] - contact_pad_size / 2.0 - IHP_BUS_CLEARANCE_UM,
    )
    _rectangle(
        component,
        "GatPolydrawing",
        contact_x - contact_pad_size / 2.0,
        gate_bus_y - contact_pad_size / 2.0,
        max(box[2] for box in gate_fingers),
        gate_bus_y + contact_pad_size / 2.0,
    )
    _rectangle(
        component,
        "Metal1drawing",
        contact_x - contact_pad_size / 2.0,
        gate_bus_y - contact_pad_size / 2.0,
        contact_x + contact_pad_size / 2.0,
        gate_bus_y + contact_pad_size / 2.0,
    )
    _rectangle(
        component,
        "Contdrawing",
        contact_x - contact_cut_size / 2.0,
        gate_bus_y - contact_cut_size / 2.0,
        contact_x + contact_cut_size / 2.0,
        gate_bus_y + contact_cut_size / 2.0,
    )
    source_bus_y = (
        gate_bus_y
        - contact_pad_size / 2.0
        - IHP_ROUTE_WIDTH_UM / 2.0
        - IHP_BUS_CLEARANCE_UM
    )
    drain_bus_y = gate_top + IHP_ROUTE_WIDTH_UM / 2.0 + IHP_BUS_CLEARANCE_UM
    terminal_centers = []
    for parity, side, bus_y in (
        (0, "bottom" if kind == "nmos" else "top",
         source_bus_y if kind == "nmos" else drain_bus_y),
        (1, "top" if kind == "nmos" else "bottom",
         drain_bus_y if kind == "nmos" else source_bus_y),
    ):
        ports = sd_ports[parity::2]
        xs = [float(port.center[0]) for port in ports]
        ys = [float(port.center[1]) for port in ports]
        offset = min(ys) - bus_y if side == "bottom" else bus_y - max(ys)
        _connect_ports_to_bus(
            component,
            tech,
            ports,
            offset=offset,
            verticalConnWidth=min(right - left for left, _, right, _ in metal_columns[parity::2]),
            horizontalLayer="Metal1drawing",
            verticalLayer="Metal1drawing",
            busWidth=IHP_ROUTE_WIDTH_UM,
            busSide=side,
            busDirection="Horizontal",
        )
        terminal_centers.append(((min(xs) + max(xs)) / 2.0, bus_y))
    source, drain = terminal_centers
    component.add_port(
        name="S",
        center=source,
        width=IHP_ROUTE_WIDTH_UM,
        orientation=270,
        layer="Metal1pin",
        port_type="electrical",
    )
    component.add_port(
        name="D",
        center=drain,
        width=IHP_ROUTE_WIDTH_UM,
        orientation=90,
        layer="Metal1pin",
        port_type="electrical",
    )
    component.add_port(
        name="G",
        center=(contact_x, gate_bus_y),
        width=contact_pad_size,
        orientation=180,
        layer="Metal1pin",
        port_type="electrical",
    )
    return component

def _interdigitated_mos_devices(gf, cell_name, mos_core, tech, kind, length, wf, nf):
    raw = _ihp_mos_device(mos_core, tech, kind, length, wf, nf+2) #+2 for dummys
    component = gf.Component(_cell_name(f"{cell_name}_{kind}", length, wf, nf))
    component.add_ref(raw)
    
    metal1BusWidth = 0.3
    metal2BusWidth = 0.3
    metal1Sep = 0.2
    metal2Sep = 0.21

    _connect_ports_to_bus(
        component, 
        tech,
        ports=[raw.ports["G3"], raw.ports["G4"]],
        offset=raw.ports["G3"].width/2+metal1BusWidth/2,
        verticalConnWidth=length,
        horizontalLayer="Metal1drawing",
        verticalLayer="GatPolydrawing",
        busWidth=metal1BusWidth,
        busSide="bottom",
        busDirection="Horizontal",
        pinName="GA",
        pinLayer="Metal1pin",
    )
    _connect_ports_to_bus(
        component, 
        tech,
        ports=[raw.ports["G2"], raw.ports["G5"]],
        offset=raw.ports["G2"].width/2+metal1BusWidth/2+metal1BusWidth+metal1Sep,
        verticalConnWidth=length,
        horizontalLayer="Metal1drawing",
        verticalLayer="GatPolydrawing",
        busWidth=metal1BusWidth,
        busSide="bottom",
        busDirection="Horizontal",
        pinName="GB",
        pinLayer="Metal1pin",
    )

    _connect_ports_to_bus(
        component, 
        tech,
        ports=[raw.ports["SD2"], raw.ports["SD4"]],
        offset=raw.ports["SD1"].width/2+metal1BusWidth/2,
        verticalConnWidth=0.16,
        horizontalLayer="Metal2drawing",
        verticalLayer="Metal1drawing",
        busWidth=metal2BusWidth,
        busSide="top",
        busDirection="Horizontal",
        pinName="S",
        pinLayer="Metal2pin",
    )
    _connect_ports_to_bus(
        component, 
        tech,
        ports=[raw.ports["SD1"], raw.ports["SD5"]],
        offset=raw.ports["SD0"].width/2+metal2BusWidth/2+metal2BusWidth+metal2Sep,
        verticalConnWidth=0.16,
        horizontalLayer="Metal2drawing",
        verticalLayer="Metal1drawing",
        busWidth=metal2BusWidth,
        busSide="top",
        busDirection="Horizontal",
        pinName="DA",
        pinLayer="Metal2pin",
    )
    _connect_ports_to_bus(
        component, 
        tech,
        ports=[raw.ports["SD3"]],
        offset=raw.ports["SD1"].width/2+metal1BusWidth/2+2*metal2BusWidth+2*metal2Sep,
        verticalConnWidth=0.16,
        horizontalLayer="Metal2drawing",
        verticalLayer="Metal1drawing",
        busWidth=metal2BusWidth,
        busSide="top",
        busDirection="Horizontal",
        pinName="DB",
        pinLayer="Metal2pin",
    )

    _connect_diff_to_gate(
        component,
        tech,
        gate_ports=[raw.ports["G1"]],
        diff_ports=[raw.ports["SD0"]],
        offset=raw.ports["G1"].width/2+metal1BusWidth/2,
        verticalConnWidthGates = length,
        verticalConnWidthDiff = 0.16,
        busWidth = 0.3,
        busSide="bottom",
        pinName="dummy0GS",
        pinLayer="Metal1pin",
        pinTextLayer=None
    )
    _connect_diff_to_gate(
        component,
        tech,
        gate_ports=[raw.ports["G6"]],
        diff_ports=[raw.ports["SD6"]],
        offset=raw.ports["G6"].width/2+metal1BusWidth/2,
        verticalConnWidthGates = length,
        verticalConnWidthDiff = 0.16,
        busWidth = 0.3,
        busSide="bottom",
        pinName="dummy1GS",
        pinLayer="Metal1pin",
        pinTextLayer=None
    )

    return component

def _add_terminal_bus(component, columns, bus_y, *, connect_from_top):
    centers = [(box[0] + box[2]) / 2.0 for box in columns]
    for left, bottom, right, top in columns:
        edge = top if connect_from_top else bottom
        _rectangle(
            component,
            "Metal1drawing",
            left,
            min(edge, bus_y - IHP_ROUTE_WIDTH_UM / 2.0),
            right,
            max(edge, bus_y + IHP_ROUTE_WIDTH_UM / 2.0),
        )
    _rectangle(
        component,
        "Metal1drawing",
        min(centers) - IHP_ROUTE_WIDTH_UM / 2.0,
        bus_y - IHP_ROUTE_WIDTH_UM / 2.0,
        max(centers) + IHP_ROUTE_WIDTH_UM / 2.0,
        bus_y + IHP_ROUTE_WIDTH_UM / 2.0,
    )
    return (min(centers) + max(centers)) / 2.0, bus_y


def _layer_boxes(component, layer):
    dbu = float(component.kcl.dbu)
    boxes = []
    for polygon in component.get_polygons(merge=False, by="name").get(layer, []):
        box = polygon.bbox()
        boxes.append(
            (
                float(box.left) * dbu,
                float(box.bottom) * dbu,
                float(box.right) * dbu,
                float(box.top) * dbu,
            )
        )
    return sorted(boxes, key=lambda box: (box[0], box[1], box[2], box[3]))


def _rectangle(component, layer, left, bottom, right, top):
    if right <= left or top <= bottom:
        raise ValueError(
            f"invalid {layer} rectangle ({left}, {bottom})..({right}, {top})"
        )
    component.add_polygon(
        [(left, bottom), (right, bottom), (right, top), (left, top)], layer=layer
    )


def _add_metal1_metal2_via(component, tech, center):
    x, y = center
    via_size = float(tech.via1_size)
    pad_size = via_size + 2.0 * float(tech.via1_enc_metal)
    for layer, size in (
        ("Metal1drawing", pad_size),
        ("Metal2drawing", pad_size),
        ("Via1drawing", via_size),
    ):
        _rectangle(
            component,
            layer,
            x - size / 2.0,
            y - size / 2.0,
            x + size / 2.0,
            y + size / 2.0,
        )


def _wire(component, start, stop, *, layer="Metal1drawing"):
    width = IHP_ROUTE_WIDTH_UM
    x1, y1 = start
    x2, y2 = stop
    if abs(y2 - y1) > 1.0e-12:
        _rectangle(
            component,
            layer,
            x1 - width / 2.0,
            min(y1, y2) - width / 2.0,
            x1 + width / 2.0,
            max(y1, y2) + width / 2.0,
        )
    if abs(x2 - x1) > 1.0e-12:
        _rectangle(
            component,
            layer,
            min(x1, x2) - width / 2.0,
            y2 - width / 2.0,
            max(x1, x2) + width / 2.0,
            y2 + width / 2.0,
        )


def _add_external_ports(component, ports):
    for name, center in ports.items():
        component.add_port(
            name=name,
            center=center,
            width=IHP_ROUTE_WIDTH_UM,
            orientation=0,
            layer="Metal1pin",
            port_type="electrical",
        )
        component.add_label(text=name, position=center, layer="Metal1pin")


def _validate_external_port_isolation(component, kdb, port_names):
    polygons = component.get_polygons(merge=True, by="name").get(
        "Metal1drawing", []
    )
    if not polygons:
        raise ValueError("PCell has no Metal1 geometry")
    owners = {}
    for name in port_names:
        center = _point(component.ports[name])
        point = kdb.Point(
            round(center[0] / component.kcl.dbu),
            round(center[1] / component.kcl.dbu),
        )
        matches = [
            index for index, polygon in enumerate(polygons) if polygon.inside(point)
        ]
        if len(matches) != 1:
            raise ValueError(
                f"external port {name} touches {len(matches)} Metal1 components"
            )
        component_index = matches[0]
        if component_index in owners:
            raise ValueError(
                f"external ports {owners[component_index]} and {name} are shorted "
                "on Metal1"
            )
        owners[component_index] = name


def _point(port):
    return float(port.center[0]), float(port.center[1])


def _cell_name(primitive, length, wf, nf):
    return f"{primitive}_l{length:.3f}_wf{wf:.3f}_nf{nf}".replace(".", "p")

def _connect_ports_to_bus(
    c,
    tech,
    ports,
    offset=0.5,
    verticalConnWidth = 0.3,
    horizontalConnWidth = 0.3,
    horizontalLayer="Metal1drawing",
    verticalLayer="Metal1drawing",
    busWidth = 0.3,
    busSide="bottom",
    busDirection="Horizontal",
    pinName=None,
    pinLayer=None,
    pinTextLayer=None
):

    xs = [float(port.center[0]) for port in ports]
    ys = [float(port.center[1]) for port in ports]


    if busDirection=="Horizontal":
        if busSide=="bottom":
            bus_y = min(ys) - offset
        elif busSide=="top":
            bus_y = max(ys) + offset
        elif busSide=="middle":
            bus_y = (min(ys)+max(ys))/2+offset
        else:
            bus_y = min(ys) - offset

        c.add_polygon(
            [
                (min(xs) - verticalConnWidth / 2, bus_y - busWidth / 2),
                (max(xs) + verticalConnWidth / 2, bus_y - busWidth / 2),
                (max(xs) + verticalConnWidth / 2, bus_y + busWidth / 2),
                (min(xs) - verticalConnWidth / 2, bus_y + busWidth / 2),
            ],
            layer=horizontalLayer,
        )

        for port in ports:
            x, y = map(float, port.center)

            c.add_polygon(
                [
                    (x - verticalConnWidth / 2, min(y,bus_y) - busWidth / 2),
                    (x + verticalConnWidth / 2, min(y,bus_y) - busWidth / 2),
                    (x + verticalConnWidth / 2, max(y,bus_y) + busWidth / 2),
                    (x - verticalConnWidth / 2, max(y,bus_y) + busWidth / 2),
                ],
                layer=verticalLayer,
            )

            if horizontalLayer != verticalLayer:
                bottom_layer, top_layer = _via_stack_layers(horizontalLayer, verticalLayer)

                _populate_via_stack(
                    c,
                    tech,
                    column_width=busWidth,
                    row_width=busWidth,
                    center=(x,bus_y),
                    bottom_layer=bottom_layer,
                    top_layer=top_layer
                )
    elif busDirection=="Vertical":
        # Bus al lado de los dispositivos
        if busSide=="left":
            bus_x = min(xs) - offset
        elif busSide=="right":
            bus_x = max(xs) + offset
        elif busSide=="middle":
            bus_x = (min(xs)+max(xs))/2+offset
        else:
            bus_x = min(xs) - offset

        c.add_polygon(
            [
                (bus_x - busWidth / 2, min(ys) - busWidth / 2),
                (bus_x + busWidth / 2, min(ys) - busWidth / 2),
                (bus_x + busWidth / 2, max(ys) + busWidth / 2),
                (bus_x - busWidth / 2, max(ys) + busWidth / 2),
            ],
            layer=verticalLayer,
        )

        for port in ports:
            x, y = map(float, port.center)

            c.add_polygon(
                [
                    (min(x,bus_x) - horizontalConnWidth / 2, y - horizontalConnWidth / 2),
                    (max(x,bus_x) + horizontalConnWidth / 2, y - horizontalConnWidth / 2),
                    (max(x,bus_x) + horizontalConnWidth / 2, y + horizontalConnWidth / 2),
                    (min(x,bus_x) - horizontalConnWidth / 2, y + horizontalConnWidth / 2),
                ],
                layer=horizontalLayer,
            )

            if horizontalLayer != verticalLayer:
                bottom_layer, top_layer = _via_stack_layers(horizontalLayer, verticalLayer)

                _populate_via_stack(
                    c,
                    tech,
                    column_width=busWidth,
                    row_width=busWidth,
                    center=(bus_x,y),
                    bottom_layer=bottom_layer,
                    top_layer=top_layer
                )

    if pinName != None and busDirection=="Horizontal":
        c.add_polygon(
            [
                (min(xs) - verticalConnWidth / 2, bus_y - busWidth / 2),
                (max(xs) + verticalConnWidth / 2, bus_y - busWidth / 2),
                (max(xs) + verticalConnWidth / 2, bus_y + busWidth / 2),
                (min(xs) - verticalConnWidth / 2, bus_y + busWidth / 2),
            ],
            layer=pinLayer,
        )
        if pinTextLayer!=None:
            c.add_label(text=pinName, position=((min(xs)+max(xs))/2, bus_y), layer=pinTextLayer)

        c.add_port(
            name=pinName,
            center=((min(xs)+max(xs))/2, bus_y),
            width=max(xs)-min(xs)+verticalConnWidth,
            orientation=0,
            layer=pinLayer
        )
    elif pinName != None and busDirection=="Vertical":
        c.add_polygon(
            [
                (bus_x - busWidth / 2, min(ys) - busWidth / 2),
                (bus_x + busWidth / 2, min(ys) - busWidth / 2),
                (bus_x + busWidth / 2, max(ys) + busWidth / 2),
                (bus_x - busWidth / 2, max(ys) + busWidth / 2),
            ],
            layer=pinLayer,
        )
        if pinTextLayer!=None:
            c.add_label(text=pinName, position=(bus_x, (min(ys)+max(ys))/2), layer=pinTextLayer)

        c.add_port(
            name=pinName,
            center=(bus_x, (min(ys)+max(ys))/2),
            width=max(ys)-min(ys)+busWidth,
            orientation=90,
            layer=pinLayer
        )

def _via_stack_layers(first_layer, second_layer):
    # Los nombres de dibujo se convierten a los nombres usados por via_stack.
    layer_order = {
        "Activ": 0,
        "GatPoly": 0,
        "Metal1": 1,
        "Metal2": 2,
        "Metal3": 3,
        "Metal4": 4,
        "Metal5": 5,
        "TopMetal1": 6,
        "TopMetal2": 7,
    }
    first = first_layer.removesuffix("drawing")
    second = second_layer.removesuffix("drawing")
    for layer in (first, second):
        if layer not in layer_order:
            raise ValueError(f"Unsupported via stack layer: {layer}")
    if first != second and layer_order[first] == layer_order[second]:
        raise ValueError(f"Cannot stack between {first} and {second}")
    if layer_order[first] <= layer_order[second]:
        return first, second
    return second, first


def _populate_via_stack(c, tech, column_width=10.0, row_width=10.0, center=[0,0], bottom_layer="Metal1", top_layer="Metal2"):
    from ihp.cells import via_stack

    via1_size = tech.via1_size_rf
    via1_spacing = tech.via1_spacing_wide
    via1_enc = tech.via1_enc

    column_num_float = (column_width-via1_enc+via1_spacing)/(via1_size+via1_spacing)
    column_num_int = int(column_num_float)
    column_num_dec = column_num_float-column_num_int

    row_num_float = (row_width-via1_enc+via1_spacing)/(via1_size+via1_spacing)
    row_num_int = int(row_num_float)

    via_stack1 = c.add_ref(via_stack(bottom_layer=bottom_layer, top_layer=top_layer, vn_columns=row_num_int, vn_rows=column_num_int, size=(row_width, column_width)))
    via_stack1.x=center[0]
    via_stack1.y=center[1]

    return via_stack1

def _get_sd_ports_even_odd(ref):
    sd_ports = []

    for p in ref.ports:
        if p.name.startswith("SD"):
            idx = int(p.name.replace("SD", ""))
            sd_ports.append((idx, p))

    sd_ports = sorted(sd_ports, key=lambda x: x[0])

    even_ports = [p for idx, p in sd_ports if idx % 2 == 0]
    odd_ports  = [p for idx, p in sd_ports if idx % 2 == 1]

    return even_ports, odd_ports    

def _connect_diff_to_gate(
    c,
    tech,
    gate_ports,
    diff_ports,
    offset=0.5,
    verticalConnWidthGates = 0.3,
    horizontalConnWidthGates = 0.3,
    verticalConnWidthDiff = 0.3,
    horizontalConnWidthDiff = 0.3,
    horizontalLayerGates="Metal1drawing",
    verticalLayerGates="GatPolydrawing",
    horizontalLayerDiff="Metal1drawing",
    verticalLayerDiff="Metal1drawing",
    busWidth = 0.3,
    busSide="bottom",
    busDirection="Horizontal",
    pinName=None,
    pinLayer=None,
    pinTextLayer=None
):
    
    _connect_ports_to_bus(
        c, 
        tech, 
        diff_ports, 
        offset, 
        verticalConnWidthDiff, 
        horizontalConnWidthDiff,
        horizontalLayerDiff,
        verticalLayerDiff,
        busWidth,
        busSide,
        busDirection,
    )
    _connect_ports_to_bus(
        c, 
        tech, 
        gate_ports, 
        offset, 
        verticalConnWidthGates, 
        horizontalConnWidthGates,
        horizontalLayerGates,
        verticalLayerGates,
        busWidth,
        busSide,
        busDirection,
    )

    xs = [float(port.center[0]) for port in gate_ports+diff_ports]
    ys = [float(port.center[1]) for port in gate_ports+diff_ports]

    if busDirection=="Horizontal":
        if busSide=="bottom":
            bus_y = min(ys) - offset
        elif busSide=="top":
            bus_y = max(ys) + offset
        elif busSide=="middle":
            bus_y = (min(ys)+max(ys))/2+offset
        else:
            bus_y = min(ys) - offset

        c.add_polygon(
            [
                (min(xs), bus_y - busWidth / 2),
                (max(xs), bus_y - busWidth / 2),
                (max(xs), bus_y + busWidth / 2),
                (min(xs), bus_y + busWidth / 2),
            ],
            layer=horizontalLayerDiff,
        )

    elif busDirection=="Vertical":
        # Bus al lado de los dispositivos
        if busSide=="left":
            bus_x = min(xs) - offset
        elif busSide=="right":
            bus_x = max(xs) + offset
        elif busSide=="middle":
            bus_x = (min(xs)+max(xs))/2+offset
        else:
            bus_x = min(xs) - offset

        c.add_polygon(
            [
                (bus_x - busWidth / 2, min(ys) ),
                (bus_x + busWidth / 2, min(ys) ),
                (bus_x + busWidth / 2, max(ys) ),
                (bus_x - busWidth / 2, max(ys) ),
            ],
            layer=verticalLayerDiff,
        )

    if pinName != None and busDirection=="Horizontal":
        c.add_polygon(
            [
                (min(xs), bus_y - busWidth / 2),
                (max(xs), bus_y - busWidth / 2),
                (max(xs), bus_y + busWidth / 2),
                (min(xs), bus_y + busWidth / 2),
            ],
            layer=pinLayer,
        )
        if pinTextLayer!=None:
            c.add_label(text=pinName, position=((min(xs)+max(xs))/2, bus_y), layer=pinTextLayer)

        c.add_port(
            name=pinName,
            center=((min(xs)+max(xs))/2, bus_y),
            width=max(xs)-min(xs)+busWidth,
            orientation=0,
            layer=pinLayer
        )
    elif pinName != None and busDirection=="Vertical":
        c.add_polygon(
            [
                (bus_x - busWidth / 2, min(ys) - busWidth / 2),
                (bus_x + busWidth / 2, min(ys) - busWidth / 2),
                (bus_x + busWidth / 2, max(ys) + busWidth / 2),
                (bus_x - busWidth / 2, max(ys) + busWidth / 2),
            ],
            layer=pinLayer,
        )
        if pinTextLayer!=None:
            c.add_label(text=pinName, position=(bus_x, (min(ys)+max(ys))/2), layer=pinTextLayer)

        c.add_port(
            name=pinName,
            center=(bus_x, (min(ys)+max(ys))/2),
            width=max(ys)-min(ys)+busWidth,
            orientation=90,
            layer=pinLayer
        )

def _populate_ports_via_stack(
    component,
    tech,
    ports,
    column_width=10.0,
    row_width=10.0,
    bottom_layer="Metal1",
    top_layer="Metal2"
):
    for port in ports:
        _populate_via_stack(
            component,
            tech,
            column_width,
            row_width,
            port.center,
            bottom_layer,
            top_layer
        )

def _add_segment(component, start, end, *, width, layer, pinName=None, pinLayer=None,
                 pinTextLayer=None):
    import gdsfactory as gf

    path = gf.Path([start, end])
    segment = gf.path.extrude(path, width=width, layer=layer)
    component.add_ref(segment)

    segment_direction = _segment_direction(path)

    if pinName!=None:
        if segment_direction=="horizontal":
            segment = gf.path.extrude(path, width=width, layer=pinLayer)
            component.add_ref(segment)
            component.add_port(
                name=pinName,
                center=((start[0]+end[0])/2, (start[1]+end[1])/2),
                width=abs(start[0]-end[0]),
                orientation=0,
                layer=pinLayer
            )
            if pinTextLayer!=None:
                component.add_label(text=pinName, position=((start[0]+end[0])/2, (start[1]+end[1])/2), layer=pinTextLayer)
        if segment_direction=="vertical":
            segment = gf.path.extrude(path, width=width, layer=pinLayer)
            component.add_ref(segment)
            component.add_port(
                name=pinName,
                center=((start[0]+end[0])/2, (start[1]+end[1])/2),
                width=abs(start[1]-end[1]),
                orientation=90,
                layer=pinLayer
            )
            if pinTextLayer!=None:
                component.add_label(text=pinName, position=((start[0]+end[0])/2, (start[1]+end[1])/2), layer=pinTextLayer)

def _segment_direction(path, tolerance=1e-9):
    if len(path.points) != 2:
        raise ValueError("Se requiere un path de exactamente dos puntos")

    (x1, y1), (x2, y2) = path.points
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)

    if dx <= tolerance and dy <= tolerance:
        raise ValueError("El segmento tiene longitud cero")
    if dy <= tolerance:
        return "horizontal"
    if dx <= tolerance:
        return "vertical"
    return "diagonal"

def _add_port(
    component,
    pinName,
    center,
    width,
    length,
    orientation=0,
    pinLayer="Metal1pin",
    pinTextLayer="Metal1text"
):

    import gdsfactory as gf
    
    component.add_port(
        name=pinName,
        center=center,
        width=width,
        orientation=0,
        layer=pinLayer
    )
    if pinTextLayer!=None:
        component.add_label(text=pinName, position=center, layer=pinTextLayer)

    if orientation==0:
        component.add_polygon(
            [
                (center[0] - width/2, center[1] - length/2),
                (center[0] + width/2, center[1] - length/2),
                (center[0] + width/2, center[1] + length/2),
                (center[0] - width/2, center[1] + length/2),
            ],
            layer=pinLayer,
        )
