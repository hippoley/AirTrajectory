from pathlib import Path
import unittest

from airtrajectory.layout import LayoutContract
from airtrajectory.ventilation_paths import discover_ventilation_paths


ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ROOT / "web" / "data" / "home_topology.fixed.json"
ALTERNATE = ROOT / "tests" / "data" / "topology.alt-two-room.json"


class VentilationPathTests(unittest.TestCase):
    def test_primary_topology_discovers_three_cross_ventilation_paths(self):
        topology = LayoutContract.from_file(PRIMARY).to_building_topology()
        paths = discover_ventilation_paths(topology)
        by_openings = {path.opening_ids: path for path in paths}

        self.assertEqual(
            set(by_openings),
            {
                ("W1", "D1", "W2"),
                ("W1", "D2", "W3"),
                ("W2", "D1", "D2", "W3"),
            },
        )
        self.assertEqual(
            by_openings[("W1", "D1", "W2")].zones,
            ("living", "bedroom"),
        )
        self.assertAlmostEqual(
            by_openings[("W1", "D1", "W2")].max_bottleneck_area_m2,
            1.5,
        )

    def test_alternate_topology_uses_non_demo_ids_without_hardcoding(self):
        topology = LayoutContract.from_file(ALTERNATE).to_building_topology()
        paths = discover_ventilation_paths(topology)

        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].opening_ids, ("AX", "LINK9", "BZ"))
        self.assertEqual(paths[0].zones, ("zone_alpha", "zone_beta"))
        self.assertNotIn("W1", paths[0].opening_ids)

    def test_disconnected_exterior_openings_are_not_fabricated(self):
        payload = {
            "schema_version": "0.1",
            "topology_id": "test.disconnected.v1",
            "source_kind": "fixed-floorplan",
            "outside_id": "OUTSIDE",
            "capabilities": {
                "floorplan_geometry_editable": False,
                "opening_position_editable": True,
                "opening_state_editable": True,
                "arbitrary_topology_import": "reserved",
                "contam_compiler": "reserved",
            },
            "rooms": [
                {"id": "a", "name": "A", "x": 0, "y": 0, "w": 1, "h": 1, "volume_m3": 10},
                {"id": "b", "name": "B", "x": 2, "y": 0, "w": 1, "h": 1, "volume_m3": 10},
            ],
            "walls": [
                {"id": "wa", "kind": "exterior", "source": "a", "target": "OUTSIDE", "x1": 0, "y1": 0, "x2": 0, "y2": 1},
                {"id": "wb", "kind": "exterior", "source": "b", "target": "OUTSIDE", "x1": 3, "y1": 0, "x2": 3, "y2": 1},
            ],
            "openings": [
                {"id": "OA", "kind": "window", "wall_id": "wa", "source": "a", "target": "OUTSIDE", "position_t": 0.5, "initial_open_pct": 0, "max_area_m2": 1, "render_side": "left", "position_editable": True, "state_editable": True},
                {"id": "OB", "kind": "window", "wall_id": "wb", "source": "b", "target": "OUTSIDE", "position_t": 0.5, "initial_open_pct": 0, "max_area_m2": 1, "render_side": "right", "position_editable": True, "state_editable": True},
            ],
            "compiler_contract": {},
        }

        topology = LayoutContract.from_dict(payload).to_building_topology()
        self.assertEqual(discover_ventilation_paths(topology), [])


if __name__ == "__main__":
    unittest.main()
