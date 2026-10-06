import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from airtrajectory.contam import ContamControl
from airtrajectory.contam_fork import ContamForkProfile, contam_fork_request
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

    def test_unknown_profile_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"unknown CONTAM profile_id"):
            contam_fork_request(
                {"profile_id":"missing","opening_id":"W1","origin":self.origin()},
                {},
                binding_factory=ForkCx,
            )


if __name__=="__main__":
    unittest.main()
