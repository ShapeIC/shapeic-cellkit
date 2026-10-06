# shapeic-cellkit

Library of analog primitives and macro layouts, usable by ShapeIC and by
standalone Python layout scripts.

Each `primitives/<name>/<pdk>/pcell.py` owns its primitive's `build(geometry)`
implementation, including device placement, connections and external ports.
Shared MOS construction, routing and via helpers live in
`technologies/<pdk>/pcells.py`, alongside the existing OTA routing assembly.

An optional `primitives/<name>/<pdk>/geometry.json` declares simple PCell
limits in SI units. It may contain `required_nf` (active fingers per device,
excluding dummies) and `max_finger_width_m` (inclusive). For example, the IHP
`simplediffpair` requires four fingers and at most 10 µm per finger. Query the
limits with `catalog.primitive_geometry_limits("simplediffpair")`; primitive
and macro renders check them before calling the PCell provider. If the file is
absent, CellKit adds no geometry limit for that implementation.

The `ota_4t` providers reuse the primitive PCells before assembling the macro.
Their `IMPLEMENTATION_FILES` include both primitive providers and the shared
technology helpers so changes to any of these files affect the macro's
implementation digest. SKY130A and GF180MCU primitives accept
`label_ports=False` when embedded in the OTA, preserving its extraction labels.

Run the catalog tests with `python3 -m unittest discover -s tests`.
Real layout tests require the corresponding PDK backend and pinned versions.

LVS can be launched with `shapeic_cellkit.run_lvs`. It requires the `klayout`
executable on `PATH` (or an explicit `klayout_executable`) and the Python
module, installable with `python3 -m pip install klayout`.

```python
from shapeic_cellkit import run_lvs

result = run_lvs(
    gds_path="build/gds/simplediffpair.gds",
    lvs_script=pdk_root / "libs.tech/klayout/tech/lvs/sg13g2.lvs",
    spice_template="primitives/simplediffpair/primitive.spice",
    output_dir="build/lvs/simplediffpair",
    spice_parameters={
        "subckt_name": topcell, "model": "sg13_lv_nmos",
        "w": 20, "l": 0.4, "ng": 4, "m": 1,
    },
    parameters={"topcell": topcell},
)
print(result.passed, result.report_path, result.schematic_path)
```

Here `pdk_root` is the installed `ihp-sg13g2` directory and `topcell` is the
GDS cell name. See `examples/simplediffpair_cc.py` for a complete example.
`spice_parameters` substitutes `{{name}}` literally; missing values raise
`ValueError`. There are no expressions or automatic unit conversions. This
template uses micrometers for `w` and `l`; the IHP LVS reader expects total
width, so the example converts `geometry.total_width_m` to micrometers.
`parameters` supplies independent deck variables via `-rd`; `input`,
`schematic`, `report`, `log` and `target_netlist` are reserved.

The deck must write a native LVS comparison report to `$report`, using
`$input` and `$schematic` as inputs. The output directory contains
`schematic.spice`, `lvs.lvsdb`, `lvs.log`, and `deck.log`; decks supporting
`$target_netlist` also write `extracted.spice`. Outputs are overwritten on
each run, so use separate directories for different variants. Only exact
circuit matches return `passed=True`; mismatches and warnings return `False`.
Execution errors or missing/invalid comparison reports raise `RuntimeError`
with the log path. Reading reports requires the Python `klayout` module;
the native-report tests in `tests/test_lvs.py` skip when it is unavailable.
