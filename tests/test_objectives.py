import unittest

from airtrajectory.objectives import (
    ComfortBand,
    MultiEnvironmentObjective,
    evaluate_candidate_outcome,
    hold_candidate,
    rank_candidate_outcomes,
)


class MultiEnvironmentObjectiveTests(unittest.TestCase):
    def setUp(self):
        self.objective=MultiEnvironmentObjective(
            co2_reference_ppm=1000,
            pm25_reference_ug_m3=15,
            temperature_band_c=ComfortBand(20,26),
            humidity_band_pct=ComfortBand(35,65),
        )
        self.origin={
            "co2_ppm":{"living":1400,"bedroom":1200},
            "pm25_ug_m3":{"living":10,"bedroom":10},
            "temperature_c":{"living":24,"bedroom":24},
            "relative_humidity_pct":{"living":50,"bedroom":50},
        }

    def test_hold_is_first_class_candidate(self):
        hold=hold_candidate(self.origin,self.objective)
        self.assertEqual(hold["candidate_kind"],"hold")
        self.assertEqual(hold["label"],"HOLD")
        self.assertEqual(hold["deltas"]["mean_co2_ppm"],0)
        self.assertEqual(hold["outcome_vector"]["actuator_motion"],0)

    def test_co2_improvement_can_lose_when_pm25_cost_is_large(self):
        risky=evaluate_candidate_outcome(
            label="OPEN-LARGE",
            origin=self.origin,
            future={
                "co2_ppm":{"living":800,"bedroom":820},
                "pm25_ug_m3":{"living":80,"bedroom":70},
                "temperature_c":{"living":24,"bedroom":24},
                "relative_humidity_pct":{"living":50,"bedroom":50},
            },
            objective=self.objective,
            actuator_motion_pct=100,
        )
        hold=hold_candidate(self.origin,self.objective)
        ranked=rank_candidate_outcomes([risky,hold])
        self.assertEqual(ranked[0]["label"],"HOLD")
        self.assertLess(risky["deltas"]["mean_co2_ppm"],0)
        self.assertGreater(risky["deltas"]["mean_pm25_ug_m3"],0)

    def test_missing_pollutant_is_unavailable_not_zero(self):
        row=evaluate_candidate_outcome(
            label="CO2-ONLY",
            origin={"co2_ppm":{"living":1400}},
            future={"co2_ppm":{"living":900}},
            objective=self.objective,
        )
        self.assertIsNone(row["outcome_vector"]["pm25_excess"])
        self.assertIn("pm25_excess",row["unavailable_objectives"])
        self.assertNotIn("pm25_excess",row["available_objectives"])

    def test_safety_dominates_nominal_air_quality_gain(self):
        unsafe=evaluate_candidate_outcome(
            label="UNSAFE",
            origin=self.origin,
            future={
                "co2_ppm":{"living":700,"bedroom":700},
                "pm25_ug_m3":{"living":5,"bedroom":5},
                "temperature_c":{"living":24,"bedroom":24},
                "relative_humidity_pct":{"living":50,"bedroom":50},
            },
            objective=self.objective,
            safety_violation=True,
        )
        hold=hold_candidate(self.origin,self.objective)
        self.assertGreater(unsafe["score"],hold["score"])


if __name__=="__main__":
    unittest.main()
