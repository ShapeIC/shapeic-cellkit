from pathlib import Path
import sys

import klayout.db as kdb

PDK_KLAYOUT = (
    Path(__file__).resolve().parents[2]
    / "pdk/ihp-sg13g2/libs.tech/klayout"
)

sys.path.insert(0, str(PDK_KLAYOUT / "python"))
sys.path.insert(
    0,
    str(PDK_KLAYOUT / "python/pycell4klayout-api/source/python"),
)

# Registers the SG13_dev PCell library.
import sg13g2_pycell_lib  # noqa: F401, E402


def _add_path(
    cell: kdb.Cell,
    layer: int,
    points: list[kdb.DPoint],
    width: float,
) -> None:
    cell.shapes(layer).insert(kdb.DPath(points, width))


def _add_pin(
    cell: kdb.Cell,
    pin_layer: int,
    text_layer: int,
    name: str,
    center: kdb.DPoint,
    size: float,
) -> None:
    half_size = size / 2
    cell.shapes(pin_layer).insert(
        kdb.DBox(
            center.x - half_size,
            center.y - half_size,
            center.x + half_size,
            center.y + half_size,
        )
    )
    cell.shapes(text_layer).insert(kdb.DText(name, kdb.DTrans(center)))


def create_simple_diffpair(
    length: float = 0.4e-6,
    width: float = 8e-6,
    fingers: int = 4,
    gap: float = 0.5,
) -> kdb.Layout:
    """Create and route two identical SG13G2 NMOS devices.

    ``length`` and ``width`` use the units expected by the IHP PCell (meters),
    while ``gap`` is expressed in layout units (micrometers).
    """
    if kdb.Library.library_by_name("SG13_dev", "sg13g2") is None:
        raise RuntimeError("SG13_dev PCell library is not registered")

    layout = kdb.Layout()
    layout.technology_name = "sg13g2"
    top = layout.create_cell("SIMPLE_DIFFPAIR_NMOS")

    nmos = layout.create_cell(
        "nmos",
        "SG13_dev",
        {
            "l": length,
            "w": width,
            "ng": fingers,
        },
    )
    if nmos is None:
        raise RuntimeError("Could not create the SG13_dev nmos PCell")

    # Physical and pin layers from the SG13G2 layer map.
    metal1 = layout.layer(kdb.LayerInfo(8, 0, "Metal1"))
    metal2 = layout.layer(kdb.LayerInfo(10, 0, "Metal2"))
    metal2_pin = layout.layer(kdb.LayerInfo(10, 2, "Metal2.pin"))
    gatpoly = layout.layer(kdb.LayerInfo(5, 0, "GatPoly"))
    gatpoly_pin = layout.layer(kdb.LayerInfo(5, 2, "GatPoly.pin"))
    text = layout.layer(kdb.LayerInfo(63, 0, "TEXT"))

    device_offsets = [0.0, nmos.dbbox().width() + gap]
    for x_offset in device_offsets:
        top.insert(kdb.DCellInstArray(nmos, kdb.DTrans(x_offset, 0.0)))

    # The NMOS PCell produces alternating Metal1 bars: S, D, S, D, ...
    contact_boxes = sorted(
        (
            shape.dbox
            for shape in nmos.shapes(metal1).each()
            if shape.is_box()
        ),
        key=lambda box: box.center().x,
    )
    if len(contact_boxes) != fingers + 1:
        raise RuntimeError("Unexpected NMOS source/drain contact geometry")

    source_x = [box.center().x for box in contact_boxes[::2]]
    drain_x = [box.center().x for box in contact_boxes[1::2]]
    contact_bottom = contact_boxes[0].bottom
    contact_top = contact_boxes[0].top
    source_via_y = contact_bottom + 0.25 * (contact_top - contact_bottom)
    drain_via_y = contact_bottom + 0.75 * (contact_top - contact_bottom)

    via = layout.create_cell(
        "via_stack",
        "SG13_dev",
        {
            "b_layer": "Metal1",
            "t_layer": "Metal2",
            "vn_columns": 1,
            "vn_rows": 1,
        },
    )
    if via is None:
        raise RuntimeError("Could not create the Metal1-to-Metal2 via PCell")

    metal_width = 0.2
    source_bus_y = nmos.dbbox().bottom - 0.8
    drain_bus_y = nmos.dbbox().top + 0.6
    all_source_x: list[float] = []
    drain_groups: list[list[float]] = []

    for x_offset in device_offsets:
        placed_sources = [x + x_offset for x in source_x]
        placed_drains = [x + x_offset for x in drain_x]
        all_source_x.extend(placed_sources)
        drain_groups.append(placed_drains)

        for x in placed_sources:
            top.insert(kdb.DCellInstArray(via, kdb.DTrans(x, source_via_y)))
            _add_path(
                top,
                metal2,
                [kdb.DPoint(x, source_via_y), kdb.DPoint(x, source_bus_y)],
                metal_width,
            )

        for x in placed_drains:
            top.insert(kdb.DCellInstArray(via, kdb.DTrans(x, drain_via_y)))
            _add_path(
                top,
                metal2,
                [kdb.DPoint(x, drain_via_y), kdb.DPoint(x, drain_bus_y)],
                metal_width,
            )

    # Common source net shared by both transistors.
    _add_path(
        top,
        metal2,
        [
            kdb.DPoint(min(all_source_x), source_bus_y),
            kdb.DPoint(max(all_source_x), source_bus_y),
        ],
        metal_width,
    )
    source_pin = kdb.DPoint(
        (min(all_source_x) + max(all_source_x)) / 2,
        source_bus_y - 0.5,
    )
    _add_path(
        top,
        metal2,
        [kdb.DPoint(source_pin.x, source_bus_y), source_pin],
        metal_width,
    )
    _add_pin(top, metal2_pin, text, "S", source_pin, metal_width)

    # One independent drain net per transistor.
    for index, placed_drains in enumerate(drain_groups, start=1):
        _add_path(
            top,
            metal2,
            [
                kdb.DPoint(min(placed_drains), drain_bus_y),
                kdb.DPoint(max(placed_drains), drain_bus_y),
            ],
            metal_width,
        )
        drain_pin = kdb.DPoint(
            (min(placed_drains) + max(placed_drains)) / 2,
            drain_bus_y + 0.5,
        )
        _add_path(
            top,
            metal2,
            [kdb.DPoint(drain_pin.x, drain_bus_y), drain_pin],
            metal_width,
        )
        _add_pin(top, metal2_pin, text, f"D{index}", drain_pin, metal_width)

    # Join the fingers of each gate in GatPoly, keeping G1 and G2 separate.
    gate_boxes = sorted(
        (
            shape.dbox
            for shape in nmos.shapes(gatpoly).each()
            if shape.is_box()
        ),
        key=lambda box: box.center().x,
    )
    gate_width = 0.2
    gate_bus_y = nmos.dbbox().bottom - gate_width / 2 + 0.05

    for index, x_offset in enumerate(device_offsets, start=1):
        first_gate_x = gate_boxes[0].center().x + x_offset
        last_gate_x = gate_boxes[-1].center().x + x_offset
        _add_path(
            top,
            gatpoly,
            [
                kdb.DPoint(first_gate_x, gate_bus_y),
                kdb.DPoint(last_gate_x, gate_bus_y),
            ],
            gate_width,
        )

        if index == 1:
            gate_pin = kdb.DPoint(first_gate_x - 0.5, gate_bus_y)
            gate_edge = kdb.DPoint(first_gate_x, gate_bus_y)
        else:
            gate_pin = kdb.DPoint(last_gate_x + 0.5, gate_bus_y)
            gate_edge = kdb.DPoint(last_gate_x, gate_bus_y)

        _add_path(top, gatpoly, [gate_pin, gate_edge], gate_width)
        _add_pin(top, gatpoly_pin, text, f"G{index}", gate_pin, gate_width)

    return layout


if __name__ == "__main__":
    create_simple_diffpair().write("simplediffpair_nmos.gds")
