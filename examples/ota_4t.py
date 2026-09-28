
import os
from pathlib import Path

from shapeic_cellkit import CellKitCatalog, PrimitiveGeometry

# Raíz del repositorio, independiente del directorio de ejecución.
ROOT = Path(__file__).resolve().parents[1]

catalog = CellKitCatalog.open(
    root=ROOT,
    pdk="ihp-sg13g2",
    pdk_root=os.environ["PDK_ROOT"],
)

macro = catalog.macro_layout("ota_4t")

# Geometría de cada primitiva que compone el OTA.
rendered = macro.render({
    "xdp": PrimitiveGeometry(  # Par diferencial NMOS
        length_m=0.4e-6,
        finger_width_m=1.5e-6,
        nf=4,
    ),
    "xcm": PrimitiveGeometry(  # Espejo de corriente PMOS
        length_m=0.4e-6,
        finger_width_m=2.0e-6,
        nf=4,
    ),
})

output = ROOT / "build" / "ota_4t.gds"
output.parent.mkdir(parents=True, exist_ok=True)
rendered.component.write_gds(str(output))

print(f"GDS generado: {output}")
