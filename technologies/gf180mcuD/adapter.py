"""GF180MCU D boundary for ShapeIC's generic Magic orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_MODELS = {
    "nmos": "nfet_03v3",
    "pmos": "pfet_03v3",
}


@dataclass(frozen=True)
class Gf180McuDTechnology:
    name: str
    revision: str
    pdk_root: Path
    magic_rcfile: Path
    magic_startup_commands: tuple[str, ...]

    def normalize_pex(self, text: str, primitive: str) -> str:
        del primitive
        return text

    def normalize_macro_pex(
        self, text: str, macro: str, bulk_ports: Mapping[str, str]
    ) -> str:
        del macro
        expected = set(_MODELS)
        if set(bulk_ports) != expected:
            raise ValueError(
                f"GF180MCU D macro bulk bindings must define {sorted(expected)}, "
                f"found {sorted(bulk_ports)}"
            )
        replacements: dict[str, str] = {}
        for line in _logical_lines(text):
            fields = line.split()
            polarity = _model_polarity(_device_model(fields))
            if polarity is None:
                continue
            bulk_index = _bulk_index(fields)
            bulk = fields[bulk_index].casefold()
            supply = bulk_ports[polarity]
            previous = replacements.get(bulk)
            if previous is not None and previous != supply:
                raise ValueError(
                    f"extracted bulk node '{fields[bulk_index]}' is shared by "
                    "both polarities"
                )
            replacements[bulk] = supply
        if not replacements:
            raise ValueError(
                "extracted macro contains no recognized GF180MCU D MOS bulk nodes"
            )
        output = []
        for raw in text.splitlines():
            fields = raw.split()
            if not fields or raw.lstrip().startswith("*"):
                output.append(raw)
            else:
                output.append(
                    " ".join(replacements.get(field.casefold(), field) for field in fields)
                )
        return "\n".join(output) + "\n"

    def normalize_mos_device(
        self, fields: list[str], primitive: str
    ) -> list[str]:
        del primitive
        if _model_polarity(_device_model(fields)) is None:
            raise ValueError("unrecognized extracted GF180MCU D MOS instance")
        normalized = fields.copy()
        normalized[_bulk_index(normalized)] = "B"
        return normalized

    def validate_primitive_pex(
        self,
        text: str,
        primitive: str,
        polarity,
        port_order: tuple[str, ...],
        branches,
        expected_subcircuit: str,
    ) -> None:
        del primitive
        lines = _logical_lines(text)
        headers = [
            fields
            for line in lines
            if (fields := line.split()) and fields[0].casefold() == ".subckt"
        ]
        if len(headers) != 1 or len(headers[0]) < 2:
            raise ValueError("primitive PEX must contain one flattened subcircuit")
        header = headers[0]
        if header[1].casefold() != expected_subcircuit.casefold():
            raise ValueError(
                f"expected PEX subcircuit '{expected_subcircuit}', found '{header[1]}'"
            )
        found_ports = tuple(header[2:])
        if tuple(value.casefold() for value in found_ports) != tuple(
            value.casefold() for value in port_order
        ):
            raise ValueError(
                f"primitive PEX ports must be {port_order}, found {found_ports}"
            )

        expected_model = _MODELS[polarity.value]
        resistors: list[tuple[str, str]] = []
        devices: list[tuple[str, str, str, str]] = []
        for line in lines:
            fields = line.split()
            if not fields:
                continue
            kind = fields[0][0].casefold()
            if kind == "r" and len(fields) >= 4:
                resistors.append((fields[1], fields[2]))
                continue
            model = _device_model(fields)
            if _model_polarity(model) is None:
                continue
            if model.casefold() != expected_model.casefold():
                raise ValueError("primitive PEX contains an unexpected MOS polarity")
            devices.append(tuple(fields[1:5]))
        if not devices:
            raise ValueError("primitive PEX contains no recognized GF180MCU D MOS devices")

        connectivity = _Connectivity(port_order)
        for device in devices:
            for node in device:
                connectivity.add(node)
        for first, second in resistors:
            connectivity.union(first, second)

        def matches(device, branch) -> bool:
            drain, gate, source, _bulk = device
            return connectivity.equivalent(gate, branch.gate) and (
                (
                    connectivity.equivalent(drain, branch.drain)
                    and connectivity.equivalent(source, branch.source)
                )
                or (
                    connectivity.equivalent(source, branch.drain)
                    and connectivity.equivalent(drain, branch.source)
                )
            )

        for branch in branches:
            if not any(matches(device, branch) for device in devices):
                raise ValueError(
                    f"primitive PEX has no device matching branch '{branch.name}'"
                )
        source_ports = {branch.source for branch in branches}

        def dummy(device) -> bool:
            drain, gate, source, _bulk = device
            return any(
                connectivity.equivalent(drain, port)
                and connectivity.equivalent(gate, port)
                and connectivity.equivalent(source, port)
                for port in source_ports
            )

        unmatched = [
            device
            for device in devices
            if not dummy(device)
            and not any(matches(device, branch) for branch in branches)
        ]
        if unmatched:
            raise ValueError(
                f"primitive PEX has {len(unmatched)} MOS finger(s) outside the "
                "declared terminal buses"
            )


def create_technology(
    pdk_root: Path, metadata: dict[str, Any]
) -> Gf180McuDTechnology:
    technology = _table(metadata, "technology")
    magic = _table(metadata, "magic")
    commands = magic.get("startup_commands", [])
    if not isinstance(commands, list) or any(
        not isinstance(command, str) or not command.strip() for command in commands
    ):
        raise ValueError("magic.startup_commands must be a list of non-empty strings")
    return Gf180McuDTechnology(
        name=_string(technology, "name"),
        revision=_string(technology, "revision"),
        pdk_root=pdk_root.resolve(),
        magic_rcfile=_installed_path(pdk_root, _string(magic, "rcfile")),
        magic_startup_commands=tuple(commands),
    )


def _device_model(fields: list[str]) -> str | None:
    if not fields:
        return None
    kind = fields[0][0].casefold()
    if kind in {"x", "m"} and len(fields) >= 6:
        return fields[5]
    return None


def _bulk_index(fields: list[str]) -> int:
    if _device_model(fields) is None or len(fields) < 6:
        raise ValueError("an extracted GF180MCU D MOS instance requires D G S B model")
    return 4


def _model_polarity(model: str | None) -> str | None:
    if model is None:
        return None
    key = model.casefold()
    for polarity, expected in _MODELS.items():
        if key == expected.casefold():
            return polarity
    return None


def _logical_lines(text: str) -> list[str]:
    output: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        if line.startswith("+") and output:
            output[-1] += " " + line[1:].strip()
        else:
            output.append(line)
    return output


def _table(raw: dict[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"missing [{name}] table")
    return value


def _string(raw: dict[str, Any], name: str) -> str:
    value = raw.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _installed_path(pdk_root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("technology paths must stay below PDK_ROOT/PDK")
    resolved = (pdk_root / path).resolve()
    if not resolved.is_relative_to(pdk_root.resolve()):
        raise ValueError("technology path escapes PDK_ROOT/PDK")
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


class _Connectivity:
    def __init__(self, nodes=()) -> None:
        self.parents: dict[str, str] = {}
        for node in nodes:
            self.add(node)

    def add(self, node: str) -> str:
        key = node.casefold()
        self.parents.setdefault(key, key)
        return key

    def find(self, node: str) -> str:
        key = self.add(node)
        parent = self.parents[key]
        if parent != key:
            self.parents[key] = self.find(parent)
        return self.parents[key]

    def union(self, first: str, second: str) -> None:
        first_root = self.find(first)
        second_root = self.find(second)
        if first_root != second_root:
            self.parents[second_root] = first_root

    def equivalent(self, first: str, second: str) -> bool:
        return self.find(first) == self.find(second)
