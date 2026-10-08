"""GF180MCU D physical implementation of the four-transistor OTA."""

from __future__ import annotations

import importlib.util
from functools import cache
from pathlib import Path

LAYOUT_POLICY = "symmetric-native-fingers-with-edge-dummies-v3"
IMPLEMENTATION_FILES = (
    Path(__file__).resolve().parents[3] / "technologies/gf180mcuD/pcells.py",
    Path(__file__).resolve().parents[3] / "primitives/simplediffpair/gf180mcuD/pcell.py",
    Path(__file__).resolve().parents[3] / "primitives/simplecurrentmirror/gf180mcuD/pcell.py",
)


def build(instances):
    if set(instances) != {"xdp", "xcm"}:
        raise ValueError("ota_4t requires exactly xdp and xcm geometries")
    diff = _primitive("simplediffpair").build(instances["xdp"], label_ports=False)
    mirror = _primitive("simplecurrentmirror").build(instances["xcm"], label_ports=False)
    return build_ota_4t(instances, diff, mirror)


@cache
def _technology():
    path = IMPLEMENTATION_FILES[0]
    spec = importlib.util.spec_from_file_location(
        "_shapeic_cellkit_gf180_macro_pcells", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load GF180MCU D technology helpers: {path}")
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
    gf, layer, _nfet, _pfet = technology._backend()
    diff_geometry = instances["xdp"]
    mirror_geometry = instances["xcm"]
    return _ota_4t(gf, layer, diff_cell, mirror_cell, diff_geometry, mirror_geometry)


def _ota_4t(gf, layer, diff_cell, mirror_cell, diff_geometry, mirror_geometry):
    technology = _technology()
    name = (
        f"ota_4t_ldp{diff_geometry.length_m * 1e6:.3f}"
        f"_wdp{diff_geometry.finger_width_m * 1e6:.3f}_ndp{diff_geometry.nf}"
        f"_lcm{mirror_geometry.length_m * 1e6:.3f}"
        f"_wcm{mirror_geometry.finger_width_m * 1e6:.3f}_ncm{mirror_geometry.nf}"
    ).replace(".", "p")
    component = technology._component(gf, name)
    diff = component.add_ref(diff_cell)
    mirror = component.add_ref(mirror_cell)
    mirror.move(
        (
            0.0,
            float(diff.dbbox().top) - float(mirror.dbbox().bottom) + 3.0,
        )
    )

    diff_dp = technology._point(diff.ports["DP"])
    diff_dn = technology._point(diff.ports["DN"])
    mirror_dout = technology._point(mirror.ports["DOUT"])
    mirror_dref = technology._point(mirror.ports["DREF"])
    left_x = min(float(diff.dbbox().left), float(mirror.dbbox().left)) - 0.9
    right_x = max(float(diff.dbbox().right), float(mirror.dbbox().right)) + 0.9
    vout = (left_x, (diff_dp[1] + mirror_dout[1]) / 2.0)
    mirror_reference = (right_x, (diff_dn[1] + mirror_dref[1]) / 2.0)
    diff_lane_y = float(diff.dbbox().bottom) - 0.7
    mirror_lane_y = float(mirror.dbbox().bottom) - 0.7
    technology._route_to_side(component, layer.metal3, diff_dp, vout, diff_lane_y)
    technology._route_to_side(component, layer.metal3, mirror_dout, vout, mirror_lane_y)
    technology._route_to_side(
        component, layer.metal3, diff_dn, mirror_reference, diff_lane_y
    )
    technology._route_to_side(
        component, layer.metal3, mirror_dref, mirror_reference, mirror_lane_y
    )

    mirror_source = technology._point(mirror.ports["S"])
    mirror_bulk = technology._point(mirror.ports["B"])
    supply = (right_x + 1.2, mirror_source[1])
    technology._wire(component, layer.metal2, mirror_source, supply)
    technology._add_stack(component, layer, supply, 2, 4)
    technology._wire(component, layer.metal4, supply, mirror_bulk)

    technology._add_port(component, layer, "VOUT", vout, 3)
    technology._copy_port(component, layer, "VINP", diff.ports["GP"], 3)
    technology._copy_port(component, layer, "VINN", diff.ports["GN"], 3)
    technology._copy_port(component, layer, "IBIAS", diff.ports["S"], 2)
    technology._add_port(component, layer, "VDD", supply, 4)
    technology._copy_port(component, layer, "VSS", diff.ports["B"], 4)
    return component
