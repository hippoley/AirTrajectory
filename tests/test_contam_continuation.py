import unittest

from airtrajectory.contam_continuation import classify_continuation_surface


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

    def test_restart_surface_is_detected_but_still_needs_continuity_test(self):
        result = classify_continuation_surface(RestartEngine())
        self.assertEqual(result["restart_methods"], ["resget", "resout"])
        by_id = {row["strategy_id"]: row for row in result["strategies"]}
        self.assertTrue(by_id["native-contam-restart"]["available"])
        self.assertFalse(by_id["native-contam-restart"]["verified"])
        self.assertIn("continuous two-step", result["continuity_test_required"])


if __name__ == "__main__":
    unittest.main()
