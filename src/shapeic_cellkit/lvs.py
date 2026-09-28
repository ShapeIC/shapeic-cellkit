"""Minimal batch LVS runner with a parameterized reference SPICE template."""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LvsResult:
    """Outcome of a completed LVS comparison and its native output paths."""

    passed: bool
    log_path: Path
    report_path: Path
    schematic_path: Path


def run_lvs(
    gds_path: str | os.PathLike[str],
    lvs_script: str | os.PathLike[str],
    spice_template: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
    *,
    spice_parameters: Mapping[str, object] | None = None,
    parameters: Mapping[str, object] | None = None,
    klayout_executable: str | os.PathLike[str] = "klayout",
) -> LvsResult:
    """Render ``{{name}}`` placeholders and run an explicit KLayout LVS deck.

    SPICE values are substituted literally, without expressions or unit
    conversion. Deck parameters are stringified and passed using ``-rd``;
    input, schematic, report, log and target_netlist are reserved variables.
    Outputs are overwritten; use a separate directory for each variant.
    Requires the klayout Python module to read the native comparison report.
    Only exact circuit matches pass. Execution/report errors raise RuntimeError
    referencing lvs.log; a completed mismatch returns passed=False.
    """
    variables = dict(parameters or {})
    for name in variables:
        if name in {"input", "schematic", "report", "log", "target_netlist"}:
            raise ValueError(f"LVS parameter {name!r} is reserved")
        if not isinstance(name, str) or not name or "=" in name:
            raise ValueError(f"Invalid LVS parameter name: {name!r}")

    output = Path(output_dir).resolve()
    log_path = output / "lvs.log"
    deck_log_path = output / "deck.log"
    report_path = output / "lvs.lvsdb"
    schematic_path = output / "schematic.spice"
    extracted_path = output / "extracted.spice"
    input_path = Path(gds_path).resolve()
    script_path = Path(lvs_script).resolve()
    template_path = Path(spice_template).resolve()
    outputs = {log_path, deck_log_path, report_path, schematic_path, extracted_path}
    if {input_path, script_path, template_path} & {path.resolve() for path in outputs}:
        raise ValueError("LVS inputs must not coincide with managed output files")

    values = dict(spice_parameters or {})

    def substitute(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"Invalid SPICE placeholder: {name!r}")
        if name not in values:
            raise ValueError(f"Missing SPICE parameter: {name!r}")
        return str(values[name])

    schematic = re.sub(
        r"\{\{(.*?)\}\}", substitute, template_path.read_text(encoding="utf-8")
    )
    variables = {
        "input": input_path,
        "schematic": schematic_path,
        "report": report_path,
        "log": deck_log_path,
        "target_netlist": extracted_path,
        **variables,
    }
    command = [os.fspath(klayout_executable), "-b", "-r", str(script_path)]
    for name, value in variables.items():
        command.extend(["-rd", f"{name}={value}"])

    output.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        try:
            import klayout.db as db

            report_path.unlink(missing_ok=True)
            extracted_path.unlink(missing_ok=True)
            deck_log_path.write_text("", encoding="utf-8")
            schematic_path.write_text(schematic, encoding="utf-8")
            completed = subprocess.run(
                command, stdout=log, stderr=subprocess.STDOUT, check=False,
                shell=False,
            )
        except (ImportError, OSError, ValueError) as exc:
            log.write(f"LVS execution failed: {exc}\n")
            raise RuntimeError(f"LVS execution failed; see {log_path}") from exc
        if completed.returncode != 0:
            raise RuntimeError(
                f"KLayout exited with code {completed.returncode}; see {log_path}"
            )

        try:
            report = db.LayoutVsSchematic()
            report.read(str(report_path))
            xref = report.xref()
            if xref is None or xref.circuit_count() == 0:
                raise ValueError("expected a report with compared circuits")
            passed = all(
                pair.status() == db.NetlistCrossReference.Match
                for pair in xref.each_circuit_pair()
            )
        except (OSError, RuntimeError, ValueError) as exc:
            log.write(f"LVS report missing or invalid: {exc}\n")
            raise RuntimeError(
                f"LVS report missing or invalid at {report_path}; see {log_path}"
            ) from exc

    return LvsResult(
        passed=passed, log_path=log_path, report_path=report_path,
        schematic_path=schematic_path,
    )
