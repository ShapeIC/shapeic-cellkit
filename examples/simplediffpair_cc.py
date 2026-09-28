import os
from pathlib import Path
from shapeic_cellkit import CellKitCatalog, PrimitiveGeometry
from shapeic_cellkit import run_drc, run_lvs

catalog = CellKitCatalog.open(
    root=Path.cwd(),
    pdk="ihp-sg13g2",
    pdk_root=os.environ["PDK_ROOT"],
)

output_dir = Path("build")

primitive = catalog.primitive("simplediffpair")
geometry = PrimitiveGeometry(
    length_m=0.4e-6,
    finger_width_m=5.0e-6,
    nf=4,
)
rendered = primitive.render(geometry)

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

lvs_result = run_lvs(
    gds_path=output,
    lvs_script=catalog.pdk_root / "libs.tech/klayout/tech/lvs/sg13g2.lvs",
    spice_template=catalog.root / "primitives/simplediffpair/primitive.spice",
    output_dir=output_dir / "lvs" / "simplediffpair",
    spice_parameters={
        "subckt_name": rendered.cell_name,
        "model": "sg13_lv_nmos",
        # IHP's LVS reader uses total width (W * m), not W * ng.
        "w": geometry.total_width_m * 1e6,
        "l": geometry.length_m * 1e6,
        "ng": geometry.nf,
        "m": 1,
        #dummies
        "w_dummy": geometry.finger_width_m*2,
        "l_dummy": geometry.length_m,
        "ng_dummy": 2,
    },
    parameters={"topcell": rendered.cell_name},
)

print("LVS:", "PASS" if lvs_result.passed else "FAIL")
print("Reporte:", lvs_result.report_path)
print("Log:", lvs_result.log_path)
print("SPICE:", lvs_result.schematic_path)
