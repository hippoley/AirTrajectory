import unittest

from airtrajectory.contam_continuation import (
    classify_continuation_surface,
    compare_continuation_observations,
)


class ReadOnlyEngine:
    def getZoneMassFraction(self, zone, contaminant):
        return 0.001

    def getPathFlow(self, path):
        return 0.2

    def doSimStep(self, count):
        return None


class SetterEngine(ReadOnlyEngine):
    def setZoneMassFraction(self, zone, contaminant, value):
        return None

    def saveState(self):
        return b"state"

    def loadState(self, state):
        return None


class MassAdjustEngine(ReadOnlyEngine):
    def setZoneAddMass(self, zone, contaminant, mass):
        return 0


class RestartEngine(ReadOnlyEngine):
    def resget(self, date, time):
        return None

    def resout(self, date, time):
        return None


class ContamContinuationTests(unittest.TestCase):
    def test_read_only_surface_keeps_reinjection_unverified(self):
        result = classify_continuation_surface(ReadOnlyEngine())
        self.assertEqual(result["zone_mass_getters"], ["getZoneMassFraction"])
        self.assertEqual(result["zone_mass_setters"], [])
        self.assertEqual(result["restart_methods"], [])
        self.assertFalse(result["state_reinjection_verified"])
        by_id = {row["strategy_id"]: row for row in result["strategies"]}
        self.assertTrue(by_id["prj-contaminant-reseed"]["available"])
        self.assertFalse(by_id["prj-contaminant-reseed"]["verified"])
        self.assertFalse(by_id["native-runtime-state-api"]["available"])
        self.assertEqual(len(result["probe_sha256"]), 64)

    def test_native_state_setter_is_detected_but_not_auto_promoted(self):
        result = classify_continuation_surface(SetterEngine())
        self.assertIn("setZoneMassFraction", result["zone_mass_setters"])
        self.assertIn("loadState", result["state_methods"])
        by_id = {row["strategy_id"]: row for row in result["strategies"]}
        self.assertTrue(by_id["native-runtime-state-api"]["available"])
        self.assertFalse(by_id["native-runtime-state-api"]["verified"])
        self.assertFalse(result["state_reinjection_verified"])

    def test_zone_mass_adjustment_is_detected_but_not_auto_promoted(self):
        result = classify_continuation_surface(MassAdjustEngine())
        self.assertEqual(result["zone_mass_adjusters"], ["setZoneAddMass"])
        by_id = {row["strategy_id"]: row for row in result["strategies"]}
        self.assertTrue(by_id["native-zone-mass-adjustment"]["available"])
        self.assertFalse(by_id["native-zone-mass-adjustment"]["verified"])
        self.assertFalse(result["state_reinjection_verified"])

    def test_restart_surface_is_detected_but_still_needs_continuity_test(self):
        result = classify_continuation_surface(RestartEngine())
        self.assertEqual(result["restart_methods"], ["resget", "resout"])
        by_id = {row["strategy_id"]: row for row in result["strategies"]}
        self.assertTrue(by_id["native-contam-restart"]["available"])
        self.assertFalse(by_id["native-contam-restart"]["verified"])
        self.assertIn("continuous two-step", result["continuity_test_required"])


    def test_equivalence_receipt_promotes_only_matching_physical_state(self):
        continuous = {
            "co2_ppm": {"living": 1000.0, "bedroom": 850.0},
            "path_flow_kg_s": {"W1": -0.2, "W2": -0.1},
            "opening_pct": {"W1": 75.0, "W2": 35.0},
            "simulation_time": "Jan01 00:02:00",
        }
        resumed = {
            "co2_ppm": {"living": 1000.4, "bedroom": 850.3},
            "path_flow_kg_s": {"W1": -0.2000004, "W2": -0.1000002},
            "opening_pct": {"W1": 75.0, "W2": 35.0},
            "simulation_time": "Jan01 00:02:00",
        }
        result = compare_continuation_observations(
            continuous=continuous,
            resumed=resumed,
            co2_tolerance_ppm=1.0,
            flow_tolerance_kg_s=1e-6,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["state_reinjection_verified"])
        self.assertEqual(len(result["comparison_sha256"]), 64)

    def test_equivalence_receipt_fails_on_physical_or_time_discontinuity(self):
        continuous = {
            "co2_ppm": {"living": 1000.0},
            "path_flow_kg_s": {"W1": -0.2},
            "opening_pct": {"W1": 75.0},
            "simulation_time": "Jan01 00:02:00",
        }
        resumed = {
            "co2_ppm": {"living": 1015.0},
            "path_flow_kg_s": {"W1": -0.2},
            "opening_pct": {"W1": 75.0},
            "simulation_time": "Jan01 00:01:00",
        }
        result = compare_continuation_observations(
            continuous=continuous,
            resumed=resumed,
            co2_tolerance_ppm=1.0,
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["state_reinjection_verified"])
        self.assertFalse(result["checks"]["co2_within_tolerance"])
        self.assertFalse(result["checks"]["time_continuity"])

if __name__ == "__main__":
    unittest.main()
