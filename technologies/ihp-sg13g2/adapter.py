"""IHP SG13G2 boundary for ShapeIC's generic Magic orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IhpSg13g2Technology:
    name: str
    revision: str
    pdk_root: Path
    magic_rcfile: Path
    magic_startup_commands: tuple[str, ...]

    def normalize_pex(self, text: str, primitive: str) -> str:
        del primitive
        return text

    def normalize_macro_pex(
        self, text: str, macro: str, bulk_ports: dict[str, str]
    ) -> str:
        del macro
        expected = {"nmos", "pmos"}
        if set(bulk_ports) != expected:
            raise ValueError(
                f"IHP macro bulk bindings must define {sorted(expected)}, "
                f"found {sorted(bulk_ports)}"
            )
        replacements: dict[str, str] = {}
        for line in _logical_lines(text):
            fields = line.split()
            if not fields or not fields[0].casefold().startswith("x") or len(fields) < 6:
                continue
            supply = {
                "sg13_lv_nmos": bulk_ports["nmos"],
                "sg13_lv_pmos": bulk_ports["pmos"],
            }.get(fields[5].casefold())
            if supply is None:
                continue
            bulk = fields[4].casefold()
            previous = replacements.get(bulk)
            if previous is not None and previous != supply:
                raise ValueError(
                    f"extracted bulk node '{fields[4]}' is shared by both polarities"
                )
            replacements[bulk] = supply
        if not replacements:
            raise ValueError("extracted macro contains no recognized IHP MOS bulk nodes")
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
        if len(fields) < 6:
            raise ValueError("an extracted IHP MOS instance requires at least six fields")
        normalized = fields.copy()
        normalized[4] = "B"
        return normalized


def create_technology(
    pdk_root: Path, metadata: dict[str, Any]
) -> IhpSg13g2Technology:
    technology = _table(metadata, "technology")
    magic = _table(metadata, "magic")
    name = _string(technology, "name")
    revision = _string(technology, "revision")
    rcfile = _installed_path(pdk_root, _string(magic, "rcfile"))
    commands = magic.get("startup_commands", [])
    if not isinstance(commands, list) or any(
        not isinstance(command, str) or not command.strip() for command in commands
    ):
        raise ValueError("magic.startup_commands must be a list of non-empty strings")
    return IhpSg13g2Technology(
        name=name,
        revision=revision,
        pdk_root=pdk_root.resolve(),
        magic_rcfile=rcfile,
        magic_startup_commands=tuple(commands),
    )


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
    if path.is_absolute():
        raise ValueError("technology paths must be relative to PDK_ROOT/PDK")
    installed = pdk_root.resolve()
    resolved = (installed / path).resolve()
    if not resolved.is_relative_to(installed):
        raise ValueError("technology path escapes PDK_ROOT/PDK")
    return resolved


def _logical_lines(text: str) -> list[str]:
    logical: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        if line.startswith("+") and logical:
            logical[-1] += " " + line[1:].strip()
        else:
            logical.append(line)
    return logical
