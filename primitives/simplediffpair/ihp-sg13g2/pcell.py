"""IHP SG13G2 implementation of the simple differential pair."""

from __future__ import annotations

import importlib.util
from functools import cache
from pathlib import Path

from kfactory import technology

LAYOUT_POLICY = "symmetric-adjacent-with-edge-dummies-v3"
IMPLEMENTATION_FILES = (
    Path(__file__).resolve().parents[3] / "technologies/ihp-sg13g2/pcells.py",
)


def build(geometry):
    technology = _technology()
    gf, cells, mos_core, tech = technology._backend()
    component = _simple_diff_pair_cc(
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

def _simple_diff_pair_cc(gf, cells, mos_core, tech, length, wf, nf):
    technology = _technology()
    component = gf.Component(technology._cell_name("simplediffpair", length, wf, nf))

    device_sep = 0.2
    metal1BusWidth = 0.3
    metal1Sep = 0.2

    device_bottom = technology._interdigitated_mos_devices(gf, "device_bottom", mos_core, tech, "nmos", length, wf, nf)
    device_top = technology._interdigitated_mos_devices(gf, "device_top", mos_core, tech, "nmos", length, wf, nf) 

    device_bottom.rotate(180)
    device_bottom.ymin=0
    device_bottom.xmin=0

    device_top.xmin = 0
    device_top.ymin = device_bottom.ymax+device_sep

    component.add_ref(device_bottom)
    component.add_ref(device_top)

    technology._connect_ports_to_bus(
        component, 
        tech,
        ports=[device_bottom.ports["S"], device_top.ports["S"]],
        offset=(device_bottom.xmax-device_bottom.xmin)/2+metal1Sep+metal1BusWidth/2,
        verticalConnWidth=0.3,
        horizontalLayer="Metal2drawing",
        verticalLayer="Metal1drawing",
        busWidth=metal1BusWidth,
        busSide="left",
        busDirection="Vertical",
        pinName="S",
        pinLayer="Metal1pin",
        pinTextLayer="Metal1text"
    )
    technology._connect_ports_to_bus(
        component, 
        tech,
        ports=[device_bottom.ports["DA"], device_top.ports["DB"]],
        offset=(device_bottom.xmax-device_bottom.xmin)/2+metal1Sep+metal1BusWidth/2+metal1Sep+metal1BusWidth,
        verticalConnWidth=0.3,
        horizontalLayer="Metal2drawing",
        verticalLayer="Metal1drawing",
        busWidth=metal1BusWidth,
        busSide="left",
        busDirection="Vertical",
        pinName="DP",
        pinLayer="Metal1pin",
        pinTextLayer="Metal1text"
    )
    technology._connect_ports_to_bus(
        component, 
        tech,
        ports=[device_bottom.ports["DB"], device_top.ports["DA"]],
        offset=(device_bottom.xmax-device_bottom.xmin)/2+metal1Sep+metal1BusWidth/2,
        verticalConnWidth=0.3,
        horizontalLayer="Metal2drawing",
        verticalLayer="Metal1drawing",
        busWidth=metal1BusWidth,
        busSide="right",
        busDirection="Vertical",
        pinName="DN",
        pinLayer="Metal1pin",
        pinTextLayer="Metal1text"
    )

    connWidth = 0.3
    technology._add_segment(
        component,
        start=(device_bottom.ports["GA"].center[0]- device_bottom.ports["GA"].width/2+connWidth/2, device_bottom.ports["GA"].center[1]),
        end=(device_bottom.ports["GA"].center[0]- device_bottom.ports["GA"].width/2+connWidth/2, device_top.ports["GB"].center[1]),
        width=connWidth,
        layer="Metal2drawing",
        pinName="GN",
        pinLayer="Metal2pin",
        pinTextLayer="Metal2text"
    )

    technology._add_segment(
        component,
        start=(device_top.ports["GA"].center[0]+device_top.ports["GA"].width/2-connWidth/2, device_top.ports["GA"].center[1]),
        end=(device_top.ports["GA"].center[0]+device_top.ports["GA"].width/2-connWidth/2, device_bottom.ports["GB"].center[1]),
        width=connWidth,
        layer="Metal2drawing",
        pinName="GP",
        pinLayer="Metal2pin",
        pinTextLayer="Metal2text"
    )

    technology._populate_via_stack(
        component,
        tech,
        column_width=connWidth,
        row_width=connWidth,
        center=(device_bottom.ports["GA"].center[0]- device_bottom.ports["GA"].width/2+connWidth/2, device_bottom.ports["GA"].center[1]),
    )
    technology._populate_via_stack(
        component,
        tech,
        column_width=connWidth,
        row_width=connWidth,
        center=(device_bottom.ports["GA"].center[0]- device_bottom.ports["GA"].width/2+connWidth/2, device_top.ports["GB"].center[1]),
    )
    technology._populate_via_stack(
        component,
        tech,
        column_width=connWidth,
        row_width=connWidth,
        center=(device_top.ports["GA"].center[0]+device_top.ports["GA"].width/2-connWidth/2, device_top.ports["GA"].center[1]),
    )
    technology._populate_via_stack(
        component,
        tech,
        column_width=connWidth,
        row_width=connWidth,
        center=(device_top.ports["GA"].center[0]+device_top.ports["GA"].width/2-connWidth/2, device_bottom.ports["GB"].center[1]),
    )

    guard_bbox = (
        (component.xmin, component.ymin),
        (component.xmax, component.ymax),
    )
    component.add_ref(cells.guard_ring(
        width=0.32,
        guardRingSpacing=0.22,
        bbox=guard_bbox
    ))

    component.add_port(
        name="B",
        center=((component.xmin+component.xmax)/2, component.ymin + 0.38/2),
        width=0.32,
        orientation=0,
        layer="Metal1pin"
    )
    component.add_label(text="B", position=((component.xmin+component.xmax)/2, component.ymin + 0.38/2), layer="Metal1text")

    technology._add_segment(
        component,
        start=device_top.ports["dummy0GS"].center,
        end=(component.xmin+0.38/2, device_top.ports["dummy0GS"].center[1]),
        width=connWidth,
        layer="Metal2drawing"
    )

    technology._add_segment(
        component,
        start=device_top.ports["dummy1GS"].center,
        end=(component.xmax-0.38/2, device_top.ports["dummy0GS"].center[1]),
        width=connWidth,
        layer="Metal2drawing"
    )

    technology._add_segment(
        component,
        start=device_bottom.ports["dummy0GS"].center,
        end=(component.xmax-0.38/2, device_bottom.ports["dummy0GS"].center[1]),
        width=connWidth,
        layer="Metal2drawing"
    )

    technology._add_segment(
        component,
        start=device_bottom.ports["dummy1GS"].center,
        end=(component.xmin+0.38/2, device_bottom.ports["dummy0GS"].center[1]),
        width=connWidth,
        layer="Metal2drawing"
    )

    technology._populate_ports_via_stack(
        component,
        tech,
        ports=[
            device_top.ports["dummy0GS"], 
            device_top.ports["dummy1GS"], 
            device_bottom.ports["dummy0GS"], 
            device_bottom.ports["dummy1GS"]
        ],
        column_width=connWidth,
        row_width=connWidth,
    )

    technology._populate_via_stack(
        component,
        tech,
        column_width=connWidth,
        row_width=connWidth,
        center=( component.xmin+0.38/2, device_top.ports["dummy0GS"].center[1]),
    )
    technology._populate_via_stack(
        component,
        tech,
        column_width=connWidth,
        row_width=connWidth,
        center=( component.xmax-0.38/2, device_top.ports["dummy1GS"].center[1]),
    )
    technology._populate_via_stack(
        component,
        tech,
        column_width=connWidth,
        row_width=connWidth,
        center=( component.xmin+0.38/2, device_bottom.ports["dummy1GS"].center[1]),
    )
    technology._populate_via_stack(
        component,
        tech,
        column_width=connWidth,
        row_width=connWidth,
        center=( component.xmax-0.38/2, device_bottom.ports["dummy0GS"].center[1]),
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
