import os
from pathlib import Path
from shapeic_cellkit import CellKitCatalog, PrimitiveGeometry

catalog = CellKitCatalog.open(
    root=Path.cwd(),
    pdk="ihp-sg13g2",
    pdk_root=os.environ["PDK_ROOT"],
)

primitive = catalog.primitive("simplediffpair")
rendered = primitive.render(
    PrimitiveGeometry(
        length_m=0.4e-6,
        finger_width_m=1.5e-6,
        nf=4,
    )
)

output = Path("build/simplediffpair.gds")
output.parent.mkdir(parents=True, exist_ok=True)
rendered.component.write_gds(str(output))
print(output.resolve())
