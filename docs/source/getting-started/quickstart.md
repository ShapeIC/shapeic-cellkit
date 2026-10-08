# Quickstart

In this tutorial, you will generate a **parameterized differential-pair layout** for IHP SG13G2, export it to GDSII, and open the result in KLayout.

```{note}
All commands in this tutorial run **inside the IIC-OSIC-TOOLS container**. Complete the [Installation](installation.md) guide first.
```

## 1. Prepare the environment

Open a shell inside the container and navigate to the CellKit checkout:

```bash
cd /foss/designs/shapeic-cellkit
sak-pdk ihp-sg13g2
```

The commands below use `.venv/bin/python` directly, so activating the virtual environment is optional. Confirm that the PDK is available:

```bash
test -d "$PDK_ROOT/ihp-sg13g2" && echo 'PDK found'
```

## 2. Create your first layout

Create a file named `examples/getting_started.py` with the following contents:

```python
import os
from pathlib import Path

from shapeic_cellkit import CellKitCatalog, PrimitiveGeometry


def main() -> None:
    # Load the layout catalog from this repository checkout.
    catalog = CellKitCatalog.open(
        root=Path.cwd(),
        pdk="ihp-sg13g2",
        pdk_root=os.environ["PDK_ROOT"],
    )

    # Select a technology-specific differential-pair implementation.
    primitive = catalog.primitive("simplediffpair")

    # Specify the transistor geometry in SI units (meters).
    geometry = PrimitiveGeometry(
        length_m=0.4e-6,
        finger_width_m=5.0e-6,
        nf=4,
    )

    # Render the layout and write a GDSII file.
    rendered = primitive.render(geometry)
    output = Path("build/gds/simplediffpair.gds")
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered.component.write_gds(str(output))

    print(f"GDSII written to: {output.resolve()}")


if __name__ == "__main__":
    main()
```

```{important}
The current `CellKitCatalog.open()` API requires **all three** arguments: `root`, `pdk`, and `pdk_root`. In this example, `root=Path.cwd()` works because the script is executed from the **repository root**. This requirement may be simplified in a future version of CellKit.
```

## 3. Run the generator

From the repository root, run:

```bash
.venv/bin/python examples/getting_started.py
```

The GDSII output is written to:

```text
build/gds/simplediffpair.gds
```

If generation fails with a missing Python module such as `gdsfactory` or `kfactory`, ensure that the required layout dependencies are installed **inside the `.venv` environment**, as described in [Installation](installation.md).

## 4. View the layout

Open the generated GDSII file with the KLayout application provided by the container:

```bash
klayout build/gds/simplediffpair.gds
```

For graphical applications, start IIC-OSIC-TOOLS in X11 or VNC mode rather than its shell-only mode.

## 5. Explore the catalog

You can discover the primitive names defined in the catalog with:

```python
print(catalog.primitive_names())
```

Add this statement after `CellKitCatalog.open()` in your script to inspect the available catalog entries. Note that an entry in the catalog does not guarantee that a PCell implementation exists for every PDK.

## Next steps

You have generated your first CellKit layout. Consult the User Guide for additional primitives and macros, technology-specific configurations, and DRC/LVS verification workflows.
