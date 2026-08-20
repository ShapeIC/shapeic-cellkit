from pathlib import Path
import sys

import klayout.db as kdb

pdk_klayout = (
    Path(__file__).resolve().parents[2]
    / "pdk/ihp-sg13g2/libs.tech/klayout"
)

sys.path.insert(0, str(pdk_klayout / "python"))
sys.path.insert(
    0,
    str(pdk_klayout / "python/pycell4klayout-api/source/python"),
)

# Este import registra SG13_dev como efecto secundario.
import sg13g2_pycell_lib  # noqa: F401, E402

if kdb.Library.library_by_name("SG13_dev", "sg13g2") is None:
    raise RuntimeError("No se pudo registrar la librería SG13_dev")

layout = kdb.Layout()
layout.technology_name = "sg13g2"

top = layout.create_cell("TOP")

l = 0.4e-6
wf = 8e-6
nf = 4      #this is per device

nmos0 = layout.create_cell(
    "nmos",
    "SG13_dev",
    {
        "l": l,
        "w": wf,
        "ng": nf,
    },
)
nmos1 = layout.create_cell(
    "nmos",
    "SG13_dev",
    {
        "l": l,
        "w": wf,
        "ng": nf,
    },
)

if nmos0 is None:
    raise RuntimeError("No se pudo crear la PCell pmos")

top.insert(
    kdb.DCellInstArray(
        nmos0,
        kdb.DTrans(kdb.DVector(0, 0)),
    )
)

layout.write("pmos_test.gds")
