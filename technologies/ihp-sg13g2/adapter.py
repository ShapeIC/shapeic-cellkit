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
        # The current IHP RC parser already accepts Magic's native output. Device
        # normalization for delta-C remains in the legacy adapter until Step 4.
        del primitive
        return text


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
