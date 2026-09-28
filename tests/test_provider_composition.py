from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shapeic_cellkit import CellKitCatalog, PrimitiveGeometry  # noqa: E402


class ProviderCompositionTests(unittest.TestCase):
    def open_catalog(self, root, pdk, pdk_root):
        rcfile = pdk_root / pdk / "libs.tech/magic" / f"{pdk}.magicrc"
        rcfile.parent.mkdir(parents=True, exist_ok=True)
        rcfile.touch()
        return CellKitCatalog.open(root, pdk, pdk_root)

    def test_ota_uses_primitive_providers_and_preserves_label_policy(self):
        geometries = {
            "xdp": PrimitiveGeometry(0.4e-6, 1.5e-6, 3),
            "xcm": PrimitiveGeometry(0.8e-6, 2.0e-6, 5),
        }
        with tempfile.TemporaryDirectory() as directory:
            for pdk in ("ihp-sg13g2", "sky130A", "gf180mcuD"):
                with self.subTest(pdk=pdk):
                    catalog = self.open_catalog(ROOT, pdk, Path(directory))
                    macro = catalog.macro_layout("ota_4t")
                    provider = macro.provider
                    diff = provider._primitive("simplediffpair")
                    mirror = provider._primitive("simplecurrentmirror")
                    diff_cell, mirror_cell = object(), object()
                    component = SimpleNamespace(
                        name="ota", ports=dict.fromkeys(macro.port_order)
                    )
                    with (
                        patch.object(diff, "build", return_value=diff_cell) as build_diff,
                        patch.object(mirror, "build", return_value=mirror_cell) as build_mirror,
                        patch.object(
                            provider._implementation(),
                            "build_ota_4t",
                            return_value=component,
                        ) as assemble,
                    ):
                        rendered = macro.render(geometries)

                    kwargs = {} if pdk == "ihp-sg13g2" else {"label_ports": False}
                    build_diff.assert_called_once_with(geometries["xdp"], **kwargs)
                    build_mirror.assert_called_once_with(geometries["xcm"], **kwargs)
                    assemble.assert_called_once_with(geometries, diff_cell, mirror_cell)
                    self.assertIs(rendered.component, component)

    def test_primitive_changes_invalidate_its_macro_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "cellkit"
            for name in ("primitives", "macros", "technologies"):
                shutil.copytree(ROOT / name, root / name)
            for pdk in ("ihp-sg13g2", "sky130A", "gf180mcuD"):
                catalog = self.open_catalog(root, pdk, Path(directory) / "pdks")
                for primitive in ("simplediffpair", "simplecurrentmirror"):
                    with self.subTest(pdk=pdk, primitive=primitive):
                        before_primitive = catalog.primitive(primitive)
                        before_macro = catalog.macro_layout("ota_4t")
                        source = root / "primitives" / primitive / pdk / "pcell.py"
                        with source.open("a") as handle:
                            handle.write("\n# Changed primitive implementation.\n")

                        self.assertNotEqual(
                            before_primitive.implementation_digest,
                            catalog.primitive(primitive).implementation_digest,
                        )
                        self.assertNotEqual(
                            before_macro.implementation_digest,
                            catalog.macro_layout("ota_4t").implementation_digest,
                        )


if __name__ == "__main__":
    unittest.main()
