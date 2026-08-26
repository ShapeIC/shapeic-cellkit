from __future__ import annotations

import json
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shapeic_cellkit import (  # noqa: E402
    CellKitCatalog,
    InvalidPdkNameError,
    ManifestValidationError,
    MosPolarity,
    PdkDirectoryNotFoundError,
    PrimitiveGeometry,
    ProviderContractError,
    ProviderNotFoundError,
    load_primitive_descriptor,
)


class PrimitiveDescriptorTests(unittest.TestCase):
    def test_derives_diff_pair_physical_topology(self) -> None:
        descriptor = load_primitive_descriptor(
            ROOT / "primitives/simplediffpair/primitive.json"
        )

        self.assertEqual(descriptor.catalog_name, "simplediffpair")
        self.assertEqual(descriptor.lut_primitive, "simplediffpair")
        self.assertEqual(descriptor.polarity, MosPolarity.NMOS)
        self.assertEqual(descriptor.operating_point_branch, "m1")
        self.assertEqual(
            descriptor.port_order,
            ("DP", "DN", "GP", "GN", "S", "B"),
        )
        self.assertEqual(
            (
                descriptor.branches[0].drain,
                descriptor.branches[0].gate,
                descriptor.branches[0].source,
                descriptor.branches[0].bulk,
            ),
            ("DP", "GP", "S", "B"),
        )
        self.assertEqual(
            (
                descriptor.branches[1].drain,
                descriptor.branches[1].gate,
                descriptor.branches[1].source,
                descriptor.branches[1].bulk,
            ),
            ("DN", "GN", "S", "B"),
        )

    def test_preserves_current_mirror_lut_alias_and_shared_supply_terminals(self) -> None:
        descriptor = load_primitive_descriptor(
            ROOT / "primitives/simplecurrentmirror/primitive.json"
        )

        self.assertEqual(descriptor.catalog_name, "simplecurrentmirror")
        self.assertEqual(descriptor.lut_primitive, "currentmirror")
        self.assertEqual(descriptor.polarity, MosPolarity.PMOS)
        self.assertEqual(descriptor.port_order, ("DOUT", "DREF", "S", "B"))
        self.assertEqual(
            (
                descriptor.branches[0].drain,
                descriptor.branches[0].gate,
                descriptor.branches[0].source,
                descriptor.branches[0].bulk,
            ),
            ("DOUT", "DREF", "S", "B"),
        )
        self.assertEqual(
            (
                descriptor.branches[1].drain,
                descriptor.branches[1].gate,
                descriptor.branches[1].source,
                descriptor.branches[1].bulk,
            ),
            ("DREF", "DREF", "S", "B"),
        )

    def test_rejects_an_unknown_branch_pin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "primitive.json"
            raw = json.loads(
                (ROOT / "primitives/simplediffpair/primitive.json").read_text()
            )
            raw["small_signal"]["branches"][0]["vd"] = "MISSING"
            path.write_text(json.dumps(raw), encoding="utf-8")

            with self.assertRaisesRegex(
                ManifestValidationError,
                "undeclared primitive pin 'MISSING'",
            ):
                load_primitive_descriptor(path)

    def test_rejects_a_missing_operating_point_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "primitive.json"
            raw = json.loads(
                (ROOT / "primitives/simplediffpair/primitive.json").read_text()
            )
            raw["physical_model"]["operating_point_branch"] = "missing"
            path.write_text(json.dumps(raw), encoding="utf-8")

            with self.assertRaisesRegex(
                ManifestValidationError,
                "operating_point_branch 'missing' does not exist",
            ):
                load_primitive_descriptor(path)

    def test_rejects_duplicate_physical_ports_in_source_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "primitive.json"
            path.write_text(
                '''{
                    "name":"pair",
                    "transistor_type":"nmos",
                    "ports":{"VD":{},"VG":{},"VS":{},"VB":{}},
                    "small_signal":{"branches":[{
                        "name":"m1","vd":"VD","vg":"VG","vs":"VS","vb":"VB"
                    }]},
                    "physical_model":{
                        "lut_primitive":"pair",
                        "operating_point_branch":"m1",
                        "ports":{"D":"VD","D":"VG","S":"VS","B":"VB"}
                    }
                }''',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ManifestValidationError,
                "duplicate JSON field 'D'",
            ):
                load_primitive_descriptor(path)


class CatalogTests(unittest.TestCase):
    def test_ihp_provider_passes_total_width_to_the_device_core(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdk_root = Path(directory) / "pdks"
            rcfile = pdk_root / "ihp-sg13g2/libs.tech/magic/ihp-sg13g2.magicrc"
            rcfile.parent.mkdir(parents=True)
            rcfile.write_text("", encoding="ascii")
            provider = CellKitCatalog.open(
                ROOT, "ihp-sg13g2", pdk_root
            ).primitive("simplediffpair").provider
            implementation = provider._implementation()
            captured = {}

            def mos_core(**parameters):
                captured.update(parameters)
                return object()

            tech = SimpleNamespace(
                nmos_min_length=0.13,
                nmos_max_length=10.0,
                nmos_min_width=0.15,
                nmos_max_width=10.0,
                nmos_max_nf=50,
            )
            implementation._ihp_mos_device(
                mos_core, tech, "nmos", 0.4, 1.5, 3
            )

            self.assertEqual(captured["width"], 4.5)
            self.assertEqual(captured["length"], 0.4)
            self.assertEqual(captured["nf"], 3)
            self.assertFalse(captured["is_pmos"])

    @unittest.skipUnless(
        importlib.util.find_spec("gdsfactory") and importlib.util.find_spec("ihp"),
        "requires the optional IHP layout backend",
    )
    def test_ihp_providers_render_the_validated_lut_interfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"MPLCONFIGDIR": directory}
        ):
            pdk_root = Path(directory) / "pdks"
            rcfile = pdk_root / "ihp-sg13g2/libs.tech/magic/ihp-sg13g2.magicrc"
            rcfile.parent.mkdir(parents=True)
            rcfile.write_text("", encoding="ascii")
            catalog = CellKitCatalog.open(ROOT, "ihp-sg13g2", pdk_root)

            cases = (
                (
                    "simplediffpair",
                    ("DP", "DN", "GP", "GN", "S", "B"),
                    "simplediffpair_l0p800_wf0p150_nf1",
                ),
                (
                    "simplecurrentmirror",
                    ("DOUT", "DREF", "S", "B"),
                    "currentmirror_l0p800_wf0p150_nf1",
                ),
            )
            for primitive, ports, cell_name in cases:
                with self.subTest(primitive=primitive):
                    rendered = catalog.primitive(primitive).render(
                        PrimitiveGeometry(0.8e-6, 0.15e-6, 1)
                    )
                    self.assertEqual(rendered.port_order, ports)
                    self.assertEqual(rendered.cell_name, cell_name)
                    self.assertEqual(
                        rendered.layout_policy,
                        "symmetric-adjacent-with-edge-dummies-v3",
                    )

    def test_opens_fake_technology_and_renders_fake_primitive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, pdk_root = _fake_cellkit(Path(directory), include_provider=True)
            catalog = CellKitCatalog.open(root, "test-pdk", pdk_root)

            self.assertEqual(catalog.pdk, "test-pdk")
            self.assertEqual(catalog.primitive_names(), ("pair",))
            self.assertEqual(catalog.technology().name, "test-pdk")
            self.assertEqual(catalog.technology().revision, "test-revision")
            self.assertEqual(
                catalog.technology().normalize_pex("raw pex", "pair"), "raw pex"
            )
            self.assertEqual(len(catalog.technology_digest), 64)
            self.assertEqual(
                catalog.primitive_descriptor_for_lut("pair-lut").catalog_name,
                "pair",
            )
            primitive = catalog.primitive("pair")
            rendered = primitive.render(PrimitiveGeometry(0.4e-6, 1.0e-6, 2))

            self.assertEqual(rendered.cell_name, "pair_nf2")
            self.assertEqual(rendered.port_order, ("D", "G", "S", "B"))
            self.assertEqual(rendered.layout_policy, "fake-layout-v1")
            self.assertEqual(len(rendered.implementation_digest), 64)

    def test_rejects_unsafe_pdk_names_before_provider_loading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, pdk_root = _fake_cellkit(Path(directory), include_provider=True)
            for value in ("", ".", "..", "nested/pdk", "/absolute"):
                with self.subTest(value=value):
                    with self.assertRaises(InvalidPdkNameError):
                        CellKitCatalog.open(root, value, pdk_root)

    def test_reports_missing_installed_pdk_separately(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, pdk_root = _fake_cellkit(Path(directory), include_provider=True)
            (pdk_root / "test-pdk/magicrc").unlink()
            (pdk_root / "test-pdk").rmdir()

            with self.assertRaises(PdkDirectoryNotFoundError):
                CellKitCatalog.open(root, "test-pdk", pdk_root)

    def test_reports_missing_primitive_provider_separately(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, pdk_root = _fake_cellkit(Path(directory), include_provider=False)
            catalog = CellKitCatalog.open(root, "test-pdk", pdk_root)

            with self.assertRaises(ProviderNotFoundError):
                catalog.primitive("pair")

    def test_rejects_provider_port_mismatch_when_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, pdk_root = _fake_cellkit(
                Path(directory), include_provider=True, missing_rendered_port=True
            )
            primitive = CellKitCatalog.open(root, "test-pdk", pdk_root).primitive(
                "pair"
            )

            with self.assertRaisesRegex(ProviderContractError, "missing: B"):
                primitive.render(PrimitiveGeometry(0.4e-6, 1.0e-6, 1))

    def test_reports_provider_import_failure_separately_from_missing_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, pdk_root = _fake_cellkit(Path(directory), include_provider=True)
            provider = root / "primitives/pair/test-pdk/pcell.py"
            provider.write_text("this is not valid Python", encoding="utf-8")
            catalog = CellKitCatalog.open(root, "test-pdk", pdk_root)

            with self.assertRaisesRegex(
                ProviderContractError,
                "could not import PCell provider",
            ):
                catalog.primitive("pair")

    def test_loads_and_renders_a_fake_macro_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, pdk_root = _fake_cellkit(Path(directory), include_provider=True)
            macro_root = root / "macros/ota"
            provider_root = macro_root / "test-pdk"
            provider_root.mkdir(parents=True)
            (macro_root / "layout.json").write_text(
                json.dumps(
                    {
                        "name": "ota",
                        "port_order": ["IN", "OUT"],
                        "instances": {"xpair": "pair"},
                    }
                ),
                encoding="utf-8",
            )
            (provider_root / "pcell.py").write_text(
                "LAYOUT_POLICY = 'fake-macro-v1'\n"
                "class Port:\n"
                "    def __init__(self, name): self.name = name\n"
                "class Component:\n"
                "    name = 'ota'\n"
                "    ports = [Port('IN'), Port('OUT')]\n"
                "def build(instances): return Component()\n",
                encoding="utf-8",
            )
            catalog = CellKitCatalog.open(root, "test-pdk", pdk_root)
            macro = catalog.macro_layout("ota")
            rendered = macro.render(
                {"xpair": PrimitiveGeometry(0.4e-6, 1.0e-6, 2)}
            )

            self.assertEqual(macro.instances, (("xpair", "pair"),))
            self.assertEqual(rendered.port_order, ("IN", "OUT"))
            self.assertEqual(rendered.layout_policy, "fake-macro-v1")


def _fake_cellkit(
    base: Path,
    *,
    include_provider: bool,
    missing_rendered_port: bool = False,
) -> tuple[Path, Path]:
    root = base / "cellkit"
    primitive_root = root / "primitives/pair"
    technology_root = root / "technologies/test-pdk"
    pdk_root = base / "pdks"
    primitive_root.mkdir(parents=True)
    technology_root.mkdir(parents=True)
    (pdk_root / "test-pdk").mkdir(parents=True)
    (pdk_root / "test-pdk/magicrc").write_text("", encoding="ascii")
    (root / "macros").mkdir()
    (primitive_root / "primitive.json").write_text(
        json.dumps(
            {
                "name": "pair",
                "transistor_type": "nmos",
                "ports": {name: {"name": name} for name in ("VD", "VG", "VS", "VB")},
                "small_signal": {
                    "branches": [
                        {
                            "name": "m1",
                            "vd": "VD",
                            "vg": "VG",
                            "vs": "VS",
                            "vb": "VB",
                        }
                    ]
                },
                "physical_model": {
                    "lut_primitive": "pair-lut",
                    "operating_point_branch": "m1",
                    "ports": {"D": "VD", "G": "VG", "S": "VS", "B": "VB"},
                },
            }
        ),
        encoding="utf-8",
    )
    (technology_root / "technology.toml").write_text(
        '[technology]\nname = "test-pdk"\n', encoding="utf-8"
    )
    (technology_root / "adapter.py").write_text(
        "class Technology:\n"
        "    name = 'test-pdk'\n"
        "    revision = 'test-revision'\n"
        "    magic_startup_commands = ()\n"
        "    def __init__(self, pdk_root):\n"
        "        self.pdk_root = pdk_root\n"
        "        self.magic_rcfile = pdk_root / 'magicrc'\n"
        "    def normalize_pex(self, text, primitive):\n"
        "        return text\n"
        "    def normalize_mos_device(self, fields, primitive):\n"
        "        return fields\n"
        "def create_technology(pdk_root, metadata):\n"
        "    return Technology(pdk_root)\n",
        encoding="utf-8",
    )
    if include_provider:
        provider_root = primitive_root / "test-pdk"
        provider_root.mkdir()
        ports = "('D', 'G', 'S')" if missing_rendered_port else "('D', 'G', 'S', 'B')"
        (provider_root / "pcell.py").write_text(
            "LAYOUT_POLICY = 'fake-layout-v1'\n"
            "class Port:\n"
            "    def __init__(self, name): self.name = name\n"
            "class Component:\n"
            "    def __init__(self, nf):\n"
            "        self.name = f'pair_nf{nf}'\n"
            f"        self.ports = [Port(name) for name in {ports}]\n"
            "def build(geometry):\n"
            "    return Component(geometry.nf)\n",
            encoding="utf-8",
        )
    return root, pdk_root


if __name__ == "__main__":
    unittest.main()
