import os
from pathlib import Path
from shapeic_cellkit import CellKitCatalog, PrimitiveGeometry
from shapeic_cellkit import run_drc

catalog = CellKitCatalog.open(
    root=Path.cwd(),
    pdk="ihp-sg13g2",
    pdk_root=os.environ["PDK_ROOT"],
)

output_dir = Path("build")

primitive = catalog.primitive("simplediffpair")
rendered = primitive.render(
    PrimitiveGeometry(
        length_m=0.4e-6,
        finger_width_m=5.0e-6,
        nf=4,
    )
)

output = output_dir/"gds"/"simplediffpair.gds"
output.parent.mkdir(parents=True, exist_ok=True)
rendered.component.write_gds(str(output))

drc_script = (
    catalog.pdk_root
    / "libs.tech/klayout/tech/drc/ihp-sg13g2.drc"
)

drc_result = run_drc(
    gds_path=output,
    drc_script=drc_script,
    output_dir=output_dir/"drc"/"simplediffpair"
)

print("DRC:", "PASS" if drc_result.passed else "FAIL")
print("Reporte:", drc_result.report_path)
print("Log:", drc_result.log_path)
