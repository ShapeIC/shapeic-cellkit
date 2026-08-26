"""PDK-independent data contracts exposed by :mod:`shapeic_cellkit`."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable

from .errors import ProviderContractError


class MosPolarity(str, Enum):
    """MOS polarity declared by a primitive manifest."""

    NMOS = "nmos"
    PMOS = "pmos"


@dataclass(frozen=True)
class PrimitiveGeometry:
    """Canonical physical primitive coordinates, always expressed in SI."""

    length_m: float
    finger_width_m: float
    nf: int

    def __post_init__(self) -> None:
        if not math.isfinite(self.length_m) or self.length_m <= 0.0:
            raise ValueError("length_m must be positive and finite")
        if not math.isfinite(self.finger_width_m) or self.finger_width_m <= 0.0:
            raise ValueError("finger_width_m must be positive and finite")
        if isinstance(self.nf, bool) or not isinstance(self.nf, int) or self.nf < 1:
            raise ValueError("nf must be a positive integer")

    @property
    def total_width_m(self) -> float:
        """Return the complete active width ``Wf * nf``."""

        return self.finger_width_m * self.nf


@dataclass(frozen=True)
class PhysicalMosBranch:
    """One active MOS branch expressed in physical multiport names."""

    name: str
    drain: str
    gate: str
    source: str
    bulk: str


@dataclass(frozen=True)
class RenderedCell:
    """PCell output plus the metadata required by physical LUT generation."""

    component: Any
    cell_name: str
    port_order: tuple[str, ...]
    layout_policy: str
    implementation_digest: str


@runtime_checkable
class PrimitivePCellProvider(Protocol):
    """Interface implemented by every technology-specific primitive PCell."""

    LAYOUT_POLICY: str

    def build(self, geometry: PrimitiveGeometry) -> Any: ...


@runtime_checkable
class MacroPCellProvider(Protocol):
    """Interface implemented by every technology-specific macro PCell."""

    LAYOUT_POLICY: str

    def build(self, instances: Mapping[str, PrimitiveGeometry]) -> Any: ...


@dataclass(frozen=True)
class MacroNet:
    """One logical macro net and the primitive terminals connected to it."""

    name: str
    external_port: str | None
    terminals: tuple[tuple[str, str], ...]


@runtime_checkable
class MagicTechnology(Protocol):
    """PDK-specific boundary consumed by the generic Magic backend."""

    name: str
    revision: str
    pdk_root: Path
    magic_rcfile: Path

    @property
    def magic_startup_commands(self) -> tuple[str, ...]: ...

    def normalize_pex(self, text: str, primitive: str) -> str:
        """Normalize raw Magic output without changing its electrical meaning."""
        ...

    def normalize_macro_pex(
        self,
        text: str,
        macro: str,
        bulk_ports: Mapping[str, str],
    ) -> str:
        """Normalize a flattened macro PEX to its declared external interface."""
        ...

    def normalize_mos_device(
        self, fields: list[str], primitive: str
    ) -> list[str]:
        """Normalize one extracted MOS instance for multiport simulation."""
        ...

    def validate_primitive_pex(
        self,
        text: str,
        primitive: str,
        polarity: MosPolarity,
        port_order: tuple[str, ...],
        branches: tuple[PhysicalMosBranch, ...],
        expected_subcircuit: str,
    ) -> None:
        """Validate that extracted devices reach every declared terminal bus."""
        ...


@dataclass(frozen=True)
class PrimitiveLayout:
    """Resolved logical descriptor and PCell provider for one primitive."""

    catalog_name: str
    lut_primitive: str
    polarity: MosPolarity
    operating_point_branch: str
    port_order: tuple[str, ...]
    branches: tuple[PhysicalMosBranch, ...]
    provider: PrimitivePCellProvider
    implementation_digest: str

    def render(self, geometry: PrimitiveGeometry) -> RenderedCell:
        component = self.provider.build(geometry)
        cell_name = _component_name(component)
        found_ports = _component_port_names(component)
        expected = set(self.port_order)
        if found_ports != expected:
            missing = sorted(expected - found_ports)
            extra = sorted(found_ports - expected)
            details = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if extra:
                details.append("unexpected: " + ", ".join(extra))
            raise ProviderContractError(
                f"primitive '{self.catalog_name}' PCell ports do not match its "
                f"physical descriptor ({'; '.join(details)})"
            )
        layout_policy = getattr(self.provider, "LAYOUT_POLICY", None)
        if not isinstance(layout_policy, str) or not layout_policy.strip():
            raise ProviderContractError(
                f"primitive '{self.catalog_name}' provider must define a non-empty "
                "LAYOUT_POLICY"
            )
        return RenderedCell(
            component=component,
            cell_name=cell_name,
            port_order=self.port_order,
            layout_policy=layout_policy,
            implementation_digest=self.implementation_digest,
        )


@dataclass(frozen=True)
class MacroLayout:
    """Resolved physical implementation of a macro, independent of Rust Macro."""

    name: str
    port_order: tuple[str, ...]
    instances: tuple[tuple[str, str], ...]
    nets: tuple[MacroNet, ...]
    provider: MacroPCellProvider
    implementation_digest: str

    def render(
        self, instances: Mapping[str, PrimitiveGeometry]
    ) -> RenderedCell:
        expected_instances = {name for name, _ in self.instances}
        if set(instances) != expected_instances:
            raise ProviderContractError(
                f"macro '{self.name}' geometry instances must be "
                f"{sorted(expected_instances)}, found {sorted(instances)}"
            )
        component = self.provider.build(instances)
        found_ports = _component_port_names(component)
        expected_ports = set(self.port_order)
        if found_ports != expected_ports:
            raise ProviderContractError(
                f"macro '{self.name}' PCell ports must be {list(self.port_order)}, "
                f"found {sorted(found_ports)}"
            )
        layout_policy = getattr(self.provider, "LAYOUT_POLICY", None)
        if not isinstance(layout_policy, str) or not layout_policy.strip():
            raise ProviderContractError(
                f"macro '{self.name}' provider must define a non-empty LAYOUT_POLICY"
            )
        return RenderedCell(
            component=component,
            cell_name=_component_name(component),
            port_order=self.port_order,
            layout_policy=layout_policy,
            implementation_digest=self.implementation_digest,
        )


def _component_name(component: Any) -> str:
    name = getattr(component, "name", None)
    if not isinstance(name, str) or not name.strip():
        raise ProviderContractError("PCell build result must have a non-empty name")
    return name


def _component_port_names(component: Any) -> set[str]:
    ports = getattr(component, "ports", None)
    if ports is None:
        raise ProviderContractError("PCell build result must expose ports")
    if isinstance(ports, Mapping):
        values = ports.keys()
    else:
        try:
            values = (getattr(port, "name") for port in ports)
        except TypeError as error:
            raise ProviderContractError(
                "PCell build result exposes a non-iterable ports collection"
            ) from error
    names = list(values)
    if any(not isinstance(name, str) or not name for name in names):
        raise ProviderContractError("PCell ports must have non-empty string names")
    if len(names) != len(set(names)):
        raise ProviderContractError("PCell exposes duplicate port names")
    return set(names)
