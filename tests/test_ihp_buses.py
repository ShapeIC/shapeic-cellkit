import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class Component:
    def __init__(self, name):
        self.name = name
        self.polygons = []
        self.ports = {}

    def add_ref(self, cell):
        return cell

    def add_polygon(self, points, layer):
        self.polygons.append((points, layer))

    def add_port(self, name, **parameters):
        self.ports[name] = SimpleNamespace(**parameters)


class IhpBusTests(unittest.TestCase):
    def test_all_diffusion_ports_reach_their_metal1_bus(self):
        path = Path(__file__).resolve().parents[1] / "technologies/ihp-sg13g2/pcells.py"
        spec = importlib.util.spec_from_file_location("ihp_bus_helpers", path)
        helpers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helpers)
        tech = SimpleNamespace(cont_size=0.16, gat_d=0.06, cont_gate_dist=0.2)

        for kind in ("nmos", "pmos"):
            for nf in (1, 2, 3, 50):
                with self.subTest(kind=kind, nf=nf):
                    # A synthetic MOS core with alternating diffusion columns.
                    columns = [(i - 0.1, -0.5, i + 0.1, 0.5) for i in range(nf + 1)]
                    gates = [(i + 0.4, -0.6, i + 0.6, 0.6) for i in range(nf)]
                    raw = SimpleNamespace(
                        ports=[SimpleNamespace(name=f"SD{i}", center=(i, 0)) for i in reversed(range(nf + 1))],
                        dbbox=lambda: SimpleNamespace(left=-0.1),
                    )
                    with (
                        patch.object(helpers, "_ihp_mos_device", return_value=raw),
                        patch.object(helpers, "_layer_boxes", side_effect=[columns, gates]),
                        patch.object(helpers, "_connect_ports_to_bus", wraps=helpers._connect_ports_to_bus) as connect,
                        patch.object(helpers, "_populate_via_stack") as via,
                    ):
                        cell = helpers._bussed_mos_device(
                            SimpleNamespace(Component=Component), None, tech, kind, 0.4, 1.0, nf
                        )

                    self.assertEqual(connect.call_count, 2)
                    via.assert_not_called()
                    self.assertEqual(set(cell.ports), {"S", "D", "G"})
                    self.assertEqual(cell.ports["S"].center[1] < cell.ports["D"].center[1], kind == "nmos")
                    for parity, name in enumerate(("S", "D")):
                        expected = list(range(parity, nf + 1, 2))
                        self.assertEqual(
                            [port.name for port in connect.call_args_list[parity].args[2]],
                            [f"SD{i}" for i in expected],
                        )
                        bus_y = cell.ports[name].center[1]
                        for x in expected:
                            # One continuous Metal1 branch covers the terminal and bus center.
                            self.assertTrue(any(
                                layer == "Metal1drawing"
                                and min(p[0] for p in points) <= x <= max(p[0] for p in points)
                                and min(p[1] for p in points) <= min(0, bus_y)
                                and max(p[1] for p in points) >= max(0, bus_y)
                                for points, layer in cell.polygons
                            ))
