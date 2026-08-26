"""Manifest parsing and logical-to-physical topology validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import MosPolarity, PhysicalMosBranch
from .errors import ManifestValidationError


@dataclass(frozen=True)
class PrimitiveDescriptor:
    catalog_name: str
    lut_primitive: str
    polarity: MosPolarity
    operating_point_branch: str
    port_order: tuple[str, ...]
    branches: tuple[PhysicalMosBranch, ...]


def load_primitive_descriptor(path: Path) -> PrimitiveDescriptor:
    """Load the physical primitive descriptor without importing its PCell."""

    try:
        raw = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestValidationError(
            f"could not load primitive manifest '{path}': {error}"
        ) from error
    if not isinstance(raw, dict):
        raise ManifestValidationError(f"primitive manifest '{path}' must be an object")

    context = f"primitive manifest '{path}'"
    name = _required_string(raw, "name", context)
    polarity_value = _required_string(raw, "transistor_type", context).lower()
    try:
        polarity = MosPolarity(polarity_value)
    except ValueError as error:
        raise ManifestValidationError(
            f"{context} transistor_type must be 'nmos' or 'pmos'"
        ) from error

    physical = _required_object(raw, "physical_model", context)
    lut_primitive = _required_string(physical, "lut_primitive", context)
    operating_point_branch = _required_string(
        physical, "operating_point_branch", context
    )
    port_map = _required_object(physical, "ports", context)
    if not port_map:
        raise ManifestValidationError(f"{context} physical_model.ports must not be empty")
    for physical_port, primitive_pin in port_map.items():
        if not isinstance(physical_port, str) or not physical_port:
            raise ManifestValidationError(
                f"{context} contains an empty physical port name"
            )
        if not isinstance(primitive_pin, str) or not primitive_pin:
            raise ManifestValidationError(
                f"{context} physical port '{physical_port}' must map to a pin name"
            )

    declared_ports = _required_object(raw, "ports", context)
    unknown_pins = sorted(set(port_map.values()) - set(declared_ports))
    if unknown_pins:
        raise ManifestValidationError(
            f"{context} physical_model references undeclared primitive pins: "
            + ", ".join(unknown_pins)
        )

    small_signal = _required_object(raw, "small_signal", context)
    raw_branches = small_signal.get("branches")
    if not isinstance(raw_branches, list) or not raw_branches:
        raise ManifestValidationError(
            f"{context} small_signal.branches must be a non-empty list"
        )
    branches = tuple(
        _physical_branch(value, index, port_map, declared_ports, context)
        for index, value in enumerate(raw_branches)
    )
    branch_names = [branch.name for branch in branches]
    if len(branch_names) != len(set(branch_names)):
        raise ManifestValidationError(
            f"{context} small_signal.branches contains duplicate names"
        )
    if operating_point_branch not in branch_names:
        raise ManifestValidationError(
            f"{context} operating_point_branch '{operating_point_branch}' does not exist"
        )

    return PrimitiveDescriptor(
        catalog_name=name,
        lut_primitive=lut_primitive,
        polarity=polarity,
        operating_point_branch=operating_point_branch,
        port_order=tuple(port_map),
        branches=branches,
    )


def _physical_branch(
    value: object,
    index: int,
    port_map: dict[str, Any],
    declared_ports: dict[str, Any],
    context: str,
) -> PhysicalMosBranch:
    branch_context = f"{context} small_signal.branches[{index}]"
    if not isinstance(value, dict):
        raise ManifestValidationError(f"{branch_context} must be an object")
    name = _required_string(value, "name", branch_context)
    resolved = {
        terminal: _resolve_physical_port(
            _required_string(value, manifest_field, branch_context),
            terminal,
            port_map,
            declared_ports,
            branch_context,
        )
        for terminal, manifest_field in (
            ("drain", "vd"),
            ("gate", "vg"),
            ("source", "vs"),
            ("bulk", "vb"),
        )
    }
    return PhysicalMosBranch(name=name, **resolved)


def _resolve_physical_port(
    primitive_pin: str,
    terminal: str,
    port_map: dict[str, Any],
    declared_ports: dict[str, Any],
    context: str,
) -> str:
    if primitive_pin not in declared_ports:
        raise ManifestValidationError(
            f"{context} references undeclared primitive pin '{primitive_pin}'"
        )
    matches = [
        physical_port
        for physical_port, mapped_pin in port_map.items()
        if mapped_pin == primitive_pin
    ]
    if len(matches) == 1:
        return matches[0]
    preferred = {
        "drain": "D",
        "gate": "G",
        "source": "S",
        "bulk": "B",
    }[terminal]
    exact = [port for port in matches if port.casefold() == preferred.casefold()]
    if len(exact) == 1:
        return exact[0]
    if not matches:
        raise ManifestValidationError(
            f"{context} pin '{primitive_pin}' used as {terminal} has no physical port"
        )
    raise ManifestValidationError(
        f"{context} pin '{primitive_pin}' used as {terminal} maps ambiguously to "
        + ", ".join(matches)
    )


def _required_object(values: dict[str, Any], name: str, context: str) -> dict[str, Any]:
    value = values.get(name)
    if not isinstance(value, dict):
        raise ManifestValidationError(f"{context} requires object '{name}'")
    return value


def _required_string(values: dict[str, Any], name: str, context: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ManifestValidationError(f"{context} requires non-empty string '{name}'")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ManifestValidationError(f"duplicate JSON field '{key}'")
        output[key] = value
    return output
