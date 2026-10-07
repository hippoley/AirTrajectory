import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from airtrajectory.contam import ContamControl, ContamScalarControl
from airtrajectory.contam_fork import ContamForkProfile, contam_fork_request, contam_strategy_fork_request
from airtrajectory.topology import BuildingTopology, OpeningEdge, ZoneNode


class ForkCx:
    def __init__(self,prj_file_path,wp_mode=0,cb_option=False,*_):
        self.path=prj_file_path
        self.nZones=2
        self.nPaths=2
        self.nInputControls=2
        self.nOutputControls=0
        self.inputControls=[SimpleNamespace(name="W1_open"),SimpleNamespace(name="W2_open")]
        self.outputControls=[]
        self.controls={1:0.0,2:0.0}
        self.steps=0

    def setupSimulation(self,use_cosim=1): pass
    def getVersion(self): return "fake-contam-fork"
    def getSimTimeStep(self): return 60
    def setInputControlValue(self,n,v): self.controls[int(n)]=float(v)
    def doSimStep(self,n): self.steps+=int(n)
    def getZoneMF(self,z,c):
        opening=sum(self.controls.values())
        base={1:0.0015,2:0.0010}[int(z)]
        return max(0.0002,base-self.steps*0.00001-opening*0.00002)
    def getPathFlow(self,p): return 0.1+0.05*sum(self.controls.values())
    def endSimulation(self): pass


class ContamForkTests(unittest.TestCase):
    def topology(self):
        return BuildingTopology.from_parts(
            [ZoneNode("living",45),ZoneNode("bedroom",30)],
            [
                OpeningEdge("W1","living","OUTSIDE","window",1.2),
                OpeningEdge("W2","bedroom","OUTSIDE","window",1.0),
            ],
        )

    def profile(self,prj):
        return ContamForkProfile(
            "home-v1",
            self.topology(),
            prj,
            {"living":1,"bedroom":2},
            {
                "W1":ContamControl(control_name="W1_open"),
                "W2":ContamControl(control_name="W2_open"),
            },
            path_numbers={"W1":1,"W2":2},
            evaluation_zone="living",
            evidence_level="test-engineering-trusted",
            trusted_for_promotion=True,
            prj_initial_co2_ppm={"living":1400,"bedroom":950},
            origin_state_mode="prj-initial-only",
        )

    def origin(self):
        return {
            "co2_ppm":{"living":1400,"bedroom":950},
            "opening_pct":{"W1":25,"W2":0},
        }

    def test_real_contam_contract_forks_fresh_sessions(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"home.prj"
            prj.write_text("fixture")
            out=contam_fork_request(
                {
                    "request_id":"cf-1",
                    "profile_id":"home-v1",
                    "opening_id":"W1",
                    "origin":self.origin(),
                    "levels":[25,75],
                    "horizon_steps":2,
                },
                {"home-v1":self.profile(prj)},
                binding_factory=ForkCx,
            )
            self.assertEqual(out["schema_version"],"0.2")
            self.assertEqual(out["backend"],"contamxpy")
            self.assertEqual(out["physics_fidelity"],"CONTAM")
            self.assertTrue(out["trusted_for_promotion"])
            self.assertEqual([x["target_pct"] for x in out["branches"]],[25.0,75.0])
            self.assertTrue(all(x["trusted_for_promotion"] for x in out["branches"]))
            self.assertTrue(all(x["provenance"].startswith("backend-generated · CONTAM") for x in out["branches"]))
            self.assertNotEqual(out["branches"][0]["end_co2_ppm"],out["branches"][1]["end_co2_ppm"])
            self.assertTrue(out["branches"][0]["series"])
            self.assertTrue(out["branches"][0]["path_flow_kg_s"])

    def test_profile_trust_defaults_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"home.prj"; prj.write_text("fixture")
            profile=ContamForkProfile(
                "simulation-only",
                self.topology(),
                prj,
                {"living":1,"bedroom":2},
                {
                    "W1":ContamControl(control_name="W1_open"),
                    "W2":ContamControl(control_name="W2_open"),
                },
                path_numbers={"W1":1,"W2":2},
            )
            out=contam_strategy_fork_request(
                {
                    "profile_id":"simulation-only",
                    "origin":self.origin(),
                    "candidates":[{"label":"x","actions":[{"opening_id":"W1","target_pct":75}]}],
                    "horizon_steps":1,
                },
                {"simulation-only":profile},
                binding_factory=ForkCx,
            )
            self.assertFalse(out["trusted_for_promotion"])
            self.assertEqual(out["evidence_level"],"simulation")
            self.assertFalse(out["branches"][0]["trusted_for_promotion"])
            self.assertIn("simulation-only",out["branches"][0]["provenance"])

    def test_origin_co2_must_match_prj_initial_state_when_declared(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"home.prj"; prj.write_text("fixture")
            origin=self.origin(); origin["co2_ppm"]["living"]=1300
            with self.assertRaisesRegex(ValueError,"must match PRJ initial state"):
                contam_strategy_fork_request(
                    {
                        "profile_id":"home-v1",
                        "origin":origin,
                        "candidates":[{"label":"x","actions":[{"opening_id":"W1","target_pct":75}]}],
                    },
                    {"home-v1":self.profile(prj)},
                    binding_factory=ForkCx,
                )


    def test_verified_prj_reseed_allows_new_co2_origin_and_emits_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"home.prj"
            prj.write_text(
                "ContamW 3.4.0.4 0\n"
                "home.prj\n"
                "2 ! initial zone concentrations:\n"
                "! Z#      CO2\n"
                "   1 2.12713004e-03\n"
                "   2 1.44341039e-03\n"
                "-999\n"
                "* end project file.\n"
            )
            base=self.profile(prj)
            profile=ContamForkProfile(
                base.profile_id,
                base.topology,
                base.prj_path,
                base.zone_numbers,
                base.opening_controls,
                path_numbers=base.path_numbers,
                evaluation_zone=base.evaluation_zone,
                evidence_level=base.evidence_level,
                trusted_for_promotion=base.trusted_for_promotion,
                prj_initial_co2_ppm=base.prj_initial_co2_ppm,
                origin_state_mode=base.origin_state_mode,
                prj_reseed_continuation_verified=True,
            )
            origin=self.origin()
            origin["co2_ppm"]={"living":900.0,"bedroom":700.0}
            out=contam_strategy_fork_request(
                {
                    "profile_id":"home-v1",
                    "origin":origin,
                    "candidates":[
                        {
                            "label":"reseeded",
                            "actions":[{"opening_id":"W1","target_pct":75}],
                        }
                    ],
                    "horizon_steps":1,
                },
                {"home-v1":profile},
                binding_factory=ForkCx,
            )
            self.assertEqual(out["origin_kind"],"prj-reseed-verified")
            self.assertTrue(out["prj_reseed_continuation_verified"])
            self.assertEqual(out["prj_reseed_receipt"]["zone_count"],2)
            self.assertEqual(len(out["prj_reseed_receipt"]["reseeded_prj_sha256"]),64)

    def test_origin_opening_controls_are_applied_before_candidate_solve(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"home.prj"; prj.write_text("fixture")
            origin=self.origin(); origin["opening_pct"]["W2"]=80
            out=contam_strategy_fork_request(
                {
                    "profile_id":"home-v1",
                    "origin":origin,
                    "candidates":[{"label":"x","actions":[{"opening_id":"W1","target_pct":75}]}],
                    "horizon_steps":1,
                },
                {"home-v1":self.profile(prj)},
                binding_factory=ForkCx,
            )
            self.assertTrue(out["origin_opening_controls_applied"])

    def test_origin_must_exactly_cover_profile(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"home.prj"
            prj.write_text("fixture")
            with self.assertRaisesRegex(ValueError,"exactly cover profile zones"):
                contam_fork_request(
                    {
                        "profile_id":"home-v1",
                        "opening_id":"W1",
                        "origin":{"co2_ppm":{"living":1400},"opening_pct":{"W1":25,"W2":0}},
                    },
                    {"home-v1":self.profile(prj)},
                    binding_factory=ForkCx,
                )

    def test_multi_action_strategy_fork(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"home.prj"
            prj.write_text("fixture")
            out=contam_strategy_fork_request(
                {
                    "request_id":"strategy-1",
                    "profile_id":"home-v1",
                    "origin":self.origin(),
                    "candidates":[
                        {
                            "label":"balanced",
                            "actions":[
                                {"opening_id":"W1","target_pct":75},
                                {"opening_id":"W2","target_pct":25},
                            ],
                        },
                        {
                            "label":"quiet",
                            "actions":[
                                {"opening_id":"W1","target_pct":50},
                                {"opening_id":"W2","target_pct":50},
                            ],
                        },
                    ],
                    "horizon_steps":2,
                },
                {"home-v1":self.profile(prj)},
                binding_factory=ForkCx,
            )
            self.assertEqual(out["schema_version"],"0.4")
            self.assertEqual(out["backend"],"contamxpy")
            self.assertEqual(out["physics_fidelity"],"CONTAM")
            self.assertTrue(out["trusted_for_promotion"])
            self.assertEqual([x["label"] for x in out["branches"]],["balanced","quiet"])
            self.assertEqual(
                out["branches"][0]["actions"],
                [
                    {"kind":"opening","opening_id":"W1","target_pct":75.0},
                    {"kind":"opening","opening_id":"W2","target_pct":25.0},
                ],
            )
            self.assertTrue(all(x["trusted_for_promotion"] for x in out["branches"]))

    def test_strategy_supports_opening_and_scalar_actuator(self):
        class MechanicalCx(ForkCx):
            def __init__(self,*args,**kwargs):
                super().__init__(*args,**kwargs)
                self.nInputControls=3
                self.inputControls=[SimpleNamespace(name="W1_open"),SimpleNamespace(name="W2_open"),SimpleNamespace(name="FAN_level")]
                self.controls={1:0.0,2:0.0,3:0.0}
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"home.prj"; prj.write_text("fixture")
            profile=self.profile(prj)
            profile=ContamForkProfile(
                profile.profile_id,profile.topology,profile.prj_path,profile.zone_numbers,profile.opening_controls,
                path_numbers=profile.path_numbers,
                scalar_controls={"FAN1":ContamScalarControl(control_name="FAN_level",command_min=0,command_max=3)}
            )
            origin=self.origin(); origin["scalar_values"]={"FAN1":1}
            out=contam_strategy_fork_request({
                "profile_id":"home-v1","origin":origin,
                "candidates":[{"label":"quiet","actions":[
                    {"opening_id":"W1","target_pct":55},
                    {"actuator_id":"FAN1","target_value":2}
                ]}],
                "horizon_steps":2
            },{"home-v1":profile},binding_factory=MechanicalCx)
            self.assertEqual(out["schema_version"],"0.4")
            self.assertEqual(out["branches"][0]["actions"],[
                {"kind":"opening","opening_id":"W1","target_pct":55.0},
                {"kind":"scalar","actuator_id":"FAN1","target_value":2.0},
            ])
            self.assertEqual(out["branches"][0]["end_scalar_values"],{"FAN1":2.0})

    def test_multi_action_rejects_duplicate_opening(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"home.prj"
            prj.write_text("fixture")
            with self.assertRaisesRegex(ValueError,"duplicate opening_id"):
                contam_strategy_fork_request(
                    {
                        "profile_id":"home-v1",
                        "origin":self.origin(),
                        "candidates":[{
                            "label":"bad",
                            "actions":[
                                {"opening_id":"W1","target_pct":50},
                                {"opening_id":"W1","target_pct":75},
                            ],
                        }],
                    },
                    {"home-v1":self.profile(prj)},
                    binding_factory=ForkCx,
                )

    def test_unknown_profile_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"unknown CONTAM profile_id"):
            contam_fork_request(
                {"profile_id":"missing","opening_id":"W1","origin":self.origin()},
                {},
                binding_factory=ForkCx,
            )


if __name__=="__main__":
    unittest.main()
