"""Minimal batch DRC runner for decks using input, report and log variables."""

from __future__ import annotations

import os
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DrcResult:
    """Outcome of a completed DRC run and its native output paths."""

    passed: bool
    log_path: Path
    report_path: Path


def run_drc(
    gds_path: str | os.PathLike[str],
    drc_script: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
    *,
    parameters: Mapping[str, object] | None = None,
    klayout_executable: str | os.PathLike[str] = "klayout",
) -> DrcResult:
    """Run an explicitly selected KLayout deck in batch mode.

    Parameters are converted to strings and supplied as deck variables. The
    names ``input``, ``report`` and ``log`` are reserved. Output files are
    overwritten; use a separate directory for each parameter variant.
    Execution and report failures raise RuntimeError referencing drc.log.
    """
    variables = dict(parameters or {})
    for name in variables:
        if name in {"input", "report", "log"}:
            raise ValueError(f"DRC parameter {name!r} is reserved")
        if not isinstance(name, str) or not name or "=" in name:
            raise ValueError(f"Invalid DRC parameter name: {name!r}")

    output = Path(output_dir).resolve()
    log_path = output / "drc.log"
    deck_log_path = output / "deck.log"
    report_path = output / "drc.lyrdb"
    input_path = Path(gds_path).resolve()
    script_path = Path(drc_script).resolve()
    if {input_path, script_path} & {log_path, deck_log_path, report_path}:
        raise ValueError("DRC inputs must not coincide with managed output files")
    variables = {
        "input": input_path,
        "report": report_path,
        "log": deck_log_path,
        **variables,
    }
    command = [os.fspath(klayout_executable), "-b", "-r", str(script_path)]
    for name, value in variables.items():
        command.extend(["-rd", f"{name}={value}"])

    output.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        try:
            report_path.unlink(missing_ok=True)
            deck_log_path.write_text("", encoding="utf-8")
            completed = subprocess.run(
                command, stdout=log, stderr=subprocess.STDOUT, check=False,
                shell=False,
            )
        except (OSError, ValueError) as exc:
            log.write(f"DRC execution failed: {exc}\n")
            raise RuntimeError(f"DRC execution failed; see {log_path}") from exc
        if completed.returncode != 0:
            raise RuntimeError(
                f"KLayout exited with code {completed.returncode}; see {log_path}"
            )

        try:
            root = ET.parse(report_path).getroot()
            items = root.findall("items")
            if root.tag != "report-database" or len(items) != 1:
                raise ValueError("expected a report-database with an items section")
            if any(item.tag != "item" for item in items[0]):
                raise ValueError("unexpected element in report items")
        except (OSError, ET.ParseError, ValueError) as exc:
            log.write(f"DRC report missing or invalid: {exc}\n")
            raise RuntimeError(
                f"DRC report missing or invalid at {report_path}; see {log_path}"
            ) from exc

    return DrcResult(
        passed=len(items[0]) == 0, log_path=log_path, report_path=report_path
    )
