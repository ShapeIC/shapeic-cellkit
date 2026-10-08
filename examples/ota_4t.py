
import os
from pathlib import Path

from shapeic_cellkit import CellKitCatalog, PrimitiveGeometry, run_drc

catalog = CellKitCatalog.open(
    root=Path.cwd(),
    pdk="ihp-sg13g2",
    pdk_root=os.environ["PDK_ROOT"],
)

output_dir = Path("build")

macro = catalog.macro_layout("ota_4t")

rendered = macro.render({
    "xdp": PrimitiveGeometry(  # Diffpair NMOS
        length_m=0.4e-6,
        finger_width_m=1.5e-6,
        nf=4,
    ),
    "xcm": PrimitiveGeometry(  # Currentmirror PMOS
        length_m=0.4e-6,
        finger_width_m=2.0e-6,
        nf=2,
    ),
})

output = output_dir/"gds"/"ota_4t.gds"
output.parent.mkdir(parents=True, exist_ok=True)
rendered.component.write_gds(str(output))

drc_script = (
    catalog.pdk_root
    / "libs.tech/klayout/tech/drc/ihp-sg13g2.drc"
)

drc_result = run_drc(
    gds_path=output,
    drc_script=drc_script,
    output_dir=output_dir/"drc"/"ota_4t"
)

print("DRC:", "PASS" if drc_result.passed else "FAIL")
print("Reporte:", drc_result.report_path)
print("Log:", drc_result.log_path)
