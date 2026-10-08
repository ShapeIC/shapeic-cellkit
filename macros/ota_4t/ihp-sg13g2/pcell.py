"""IHP SG13G2 physical implementation of the four-transistor OTA."""

from __future__ import annotations

import importlib.util
from functools import cache
from pathlib import Path

LAYOUT_POLICY = "symmetric-adjacent-with-edge-dummies-v3"
IMPLEMENTATION_FILES = (
    Path(__file__).resolve().parents[3] / "technologies/ihp-sg13g2/pcells.py",
    Path(__file__).resolve().parents[3] / "primitives/simplediffpair/ihp-sg13g2/pcell.py",
    Path(__file__).resolve().parents[3] / "primitives/simplecurrentmirror/ihp-sg13g2/pcell.py",
)


def build(instances):
    if set(instances) != {"xdp", "xcm"}:
        raise ValueError("ota_4t requires exactly xdp and xcm geometries")
    diff = _primitive("simplediffpair").build(instances["xdp"])
    mirror = _primitive("simplecurrentmirror").build(instances["xcm"])
    return build_ota_4t(instances, diff, mirror)


@cache
def _technology():
    path = IMPLEMENTATION_FILES[0]
    spec = importlib.util.spec_from_file_location(
        "_shapeic_cellkit_ihp_sg13g2_macro_pcells", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load IHP technology helpers: {path}")
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


def build_ota_4t(instances, diff_cell, mirror_cell):
    """Route the OTA using components built by its primitive providers."""
    technology = _technology()
    gf, _cells, _mos_core, tech = technology._backend()
    diff_geometry = instances["xdp"]
    mirror_geometry = instances["xcm"]
    component = _ota_4t(gf, tech, diff_cell, mirror_cell, diff_geometry, mirror_geometry)
    technology._validate_external_port_isolation(
        component, gf.kdb, ("VOUT", "VINP", "VINN", "IBIAS", "VDD", "VSS")
    )
    return component


def _ota_4t(gf, tech, diff_cell, mirror_cell, diff_geometry, mirror_geometry):
    technology = _technology()
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
            float(diff.dbbox().top) - float(mirror.dbbox().bottom) + 1.0,
        )
    )

    diff_dp = (technology._point(diff.ports["DP"])[0], technology._point(diff.ports["DP"])[1]+diff.ports["DP"].width/2-0.3/2)
    diff_dn = (technology._point(diff.ports["DN"])[0], technology._point(diff.ports["DN"])[1]+diff.ports["DN"].width/2-0.3/2)
    mirror_dout = technology._point(mirror.ports["DOUT"])
    mirror_dref = technology._point(mirror.ports["DREF"])
    left_x = min(
        float(diff.dbbox().left),
        float(mirror.dbbox().left),
        diff_dp[0],
        mirror_dout[0],
    ) - 0.5
    right_x = max(
        float(diff.dbbox().right),
        float(mirror.dbbox().right),
        diff_dn[0],
        mirror_dref[0],
    ) + 0.5
    route_y = float(diff.dbbox().top) + 0.5
    vout = (left_x, route_y)
    internal = (right_x, route_y)
    for terminal in (diff_dp, diff_dn, mirror_dout, mirror_dref, vout):
        technology._populate_via_stack(
            component,
            tech,
            row_width=0.3,
            column_width=0.3,
            center=terminal
        )
    for terminal in (diff_dp, mirror_dout):
        technology._wire(component, terminal, vout, layer="Metal2drawing")
    for terminal in (diff_dn, mirror_dref):
        technology._wire(component, terminal, internal, layer="Metal2drawing")

    mirror_source = technology._point(mirror.ports["S"])
    mirror_bulk = technology._point(mirror.ports["B"])
    technology._wire(component, mirror_source, mirror_bulk)
    technology._add_external_ports(
        component,
        {
            "VOUT": vout,
            "VINP": technology._point(diff.ports["GP"]),
            "VINN": technology._point(diff.ports["GN"]),
            "IBIAS": technology._point(diff.ports["S"]),
            "VDD": mirror_bulk,
            "VSS": technology._point(diff.ports["B"]),
        },
    )
    return component
