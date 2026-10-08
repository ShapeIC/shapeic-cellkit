# Installation

ShapeIC CellKit is designed to run inside the [IIC-OSIC-TOOLS](https://github.com/iic-jku/IIC-OSIC-TOOLS) container. The container supplies the EDA tools and installed Process Design Kits (PDKs), while CellKit and its Python layout dependencies are installed into a Python 3.12 virtual environment.

```{important}
Unless explicitly marked **On the host**, run every command in this guide **inside the IIC-OSIC-TOOLS container**.
```

## 1. Start IIC-OSIC-TOOLS

**On the host:** Install Docker or Podman, then follow the [official IIC-OSIC-TOOLS instructions](https://github.com/iic-jku/IIC-OSIC-TOOLS) to configure and launch the container.

For example, clone its repository:

```bash
git clone https://github.com/iic-jku/IIC-OSIC-TOOLS.git
cd IIC-OSIC-TOOLS
```

To start a graphical session on a compatible Linux host, use:

```bash
./start_x.sh
```

Alternatively, follow the upstream instructions for a VNC session (for example, `./start_vnc.sh`). Launch scripts and graphical requirements may vary by platform and container version; refer to the upstream documentation.

The standard container configuration mounts a persistent designs directory at `/foss/designs`. Keep your CellKit checkout there so generated layouts remain available between sessions.

## 2. Clone ShapeIC CellKit

**Inside the container:**

```bash
cd /foss/designs
git clone https://github.com/ShapeIC/shapeic-cellkit.git
cd shapeic-cellkit
```

The repository checkout is required by the current catalog API: the `primitives/`, `macros/`, and `technologies/` directories are loaded from the filesystem rather than installed as Python package data.

## 3. Install Python 3.12 and CellKit

CellKit requires **Python 3.12** (`>=3.12,<3.13`). The container's default `python` command is not assumed to be compatible.

We recommend [uv](https://docs.astral.sh/uv/) to create a virtual environment. If `uv` is unavailable, follow the [official uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/) **inside the container**. For example:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Make sure `uv` is on your `PATH`, then create the environment and install CellKit:

```bash
uv venv --python 3.12
uv pip install -e .
```

No `ihp` or `sky130` extra is required. The project's `pyproject.toml` declares the Python layout libraries as **regular dependencies**, including the [custom IHP fork](https://github.com/lild4d4/IHP) and [SkyWater SKY130](https://github.com/gdsfactory/skywater130), both installed from Git revisions compatible with the selected `gdsfactory` version.

You do **not** need to install `gdsfactory` separately or clone the `IHP` fork into a local `IHP/` directory for normal use. Python packages are installed into `.venv`; EDA executables and the actual PDK files come from IIC-OSIC-TOOLS.

You can activate the virtual environment if you prefer:

```bash
source .venv/bin/activate
```

Activation is optional. The following commands address `.venv/bin/python` directly, so they work without activation.

## 4. Select the PDK

The [Quickstart](quickstart.md) uses **IHP SG13G2**. Select it in the container shell:

```bash
sak-pdk ihp-sg13g2
```

Check the PDK location:

```bash
echo "$PDK_ROOT"
test -d "$PDK_ROOT/ihp-sg13g2" && echo 'IHP SG13G2 PDK found'
```

## 5. Verify the installation

From the CellKit repository root, confirm that the packages can be imported:

```bash
.venv/bin/python --version
.venv/bin/python -c "import shapeic_cellkit, ihp, sky130, gdsfactory; print('CellKit and layout libraries imported successfully')"
```

Check the installed dependency metadata:

```bash
uv pip check
```

These checks confirm that Python can import the packages and that their declared requirements are satisfied; they do not verify a technology-specific layout generator. Continue with the [Quickstart](quickstart.md) to generate a GDSII layout.

```{note}
Installing the SkyWater Python package does not, by itself, imply that every CellKit primitive has a SkyWater implementation. Availability depends on the PDK-specific providers present in the CellKit catalog.
```

## Alternative: venv and pip

If Python 3.12 and `pip` are already available inside the container, you may use standard Python tooling instead:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

The Git dependency declarations use standard Python package dependency syntax and are not specific to `uv`.
