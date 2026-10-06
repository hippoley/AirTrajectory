import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from airtrajectory.contam import ContamControl
from airtrajectory.contam_fork import ContamForkProfile
from airtrajectory.http_server import make_server
from airtrajectory.topology import BuildingTopology, OpeningEdge, ZoneNode


class HTTPForkCx:
    def __init__(self,prj_file_path,wp_mode=0,cb_option=False,*_):
        self.nZones=2
        self.nPaths=2
        self.nInputControls=2
        self.nOutputControls=0
        self.inputControls=[SimpleNamespace(name="W1_open"),SimpleNamespace(name="W2_open")]
        self.outputControls=[]
        self.controls={1:0.0,2:0.0}
        self.steps=0
    def setupSimulation(self,use_cosim=1): pass
    def getVersion(self): return "http-fake"
    def getSimTimeStep(self): return 60
    def setInputControlValue(self,n,v): self.controls[int(n)]=float(v)
    def doSimStep(self,n): self.steps+=int(n)
    def getZoneMF(self,z,c):
        base={1:0.0015,2:0.0010}[int(z)]
        return max(0.0002,base-self.steps*0.00001-sum(self.controls.values())*0.00002)
    def getPathFlow(self,p): return 0.1+0.05*sum(self.controls.values())
    def endSimulation(self): pass


class ContamHTTPTests(unittest.TestCase):
    def request(self,server,payload,path="/fork/contam"):
        body=json.dumps(payload).encode("utf-8")
        req=Request(
            f"http://127.0.0.1:{server.server_address[1]}{path}",
            data=body,method="POST",headers={"Content-Type":"application/json"},
        )
        try:
            with urlopen(req,timeout=3) as response:
                return response.status,json.loads(response.read())
        except HTTPError as exc:
            return exc.code,json.loads(exc.read())

    def start(self,**kwargs):
        server=make_server("127.0.0.1",0,**kwargs)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def profile(self,prj):
        topology=BuildingTopology.from_parts(
            [ZoneNode("living",45),ZoneNode("bedroom",30)],
            [
                OpeningEdge("W1","living","OUTSIDE","window",1.2),
                OpeningEdge("W2","bedroom","OUTSIDE","window",1.0),
            ],
        )
        return ContamForkProfile(
            "home-v1",topology,prj,
            {"living":1,"bedroom":2},
            {"W1":ContamControl(control_name="W1_open"),"W2":ContamControl(control_name="W2_open")},
            path_numbers={"W1":1,"W2":2},
            evidence_level="test-engineering-trusted",
            trusted_for_promotion=True,
        )

    def payload(self):
        return {
            "request_id":"http-contam",
            "profile_id":"home-v1",
            "opening_id":"W1",
            "origin":{
                "co2_ppm":{"living":1400,"bedroom":950},
                "opening_pct":{"W1":25,"W2":0},
            },
            "levels":[75],
            "horizon_steps":2,
        }

    def test_endpoint_fails_closed_without_profiles(self):
        server=self.start()
        status,payload=self.request(server,self.payload())
        self.assertEqual(status,503)
        self.assertEqual(payload["error"],"contam_profiles_unavailable")

    def test_strategy_endpoint_returns_multi_action_contam_branch(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"home.prj"
            prj.write_text("fixture")
            server=self.start(
                contam_profiles={"home-v1":self.profile(prj)},
                contam_binding_factory=HTTPForkCx,
            )
            payload={
                "request_id":"http-strategy",
                "profile_id":"home-v1",
                "origin":{
                    "co2_ppm":{"living":1400,"bedroom":950},
                    "opening_pct":{"W1":25,"W2":0},
                },
                "candidates":[{
                    "label":"cross-room",
                    "actions":[
                        {"opening_id":"W1","target_pct":75},
                        {"opening_id":"W2","target_pct":25},
                    ],
                }],
                "horizon_steps":2,
            }
            status,out=self.request(server,payload,"/fork/contam-strategy")
            self.assertEqual(status,200)
            self.assertEqual(out["schema_version"],"0.4")
            self.assertEqual(out["physics_fidelity"],"CONTAM")
            self.assertTrue(out["trusted_for_promotion"])
            self.assertEqual(out["branches"][0]["label"],"cross-room")
            self.assertEqual(len(out["branches"][0]["actions"]),2)

    def test_endpoint_returns_structured_contam_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"home.prj"
            prj.write_text("fixture")
            server=self.start(
                contam_profiles={"home-v1":self.profile(prj)},
                contam_binding_factory=HTTPForkCx,
            )
            status,payload=self.request(server,self.payload())
            self.assertEqual(status,200)
            self.assertEqual(payload["backend"],"contamxpy")
            self.assertEqual(payload["physics_fidelity"],"CONTAM")
            self.assertTrue(payload["trusted_for_promotion"])
            self.assertEqual(payload["branches"][0]["target_pct"],75.0)
            self.assertTrue(payload["branches"][0]["trusted_for_promotion"])


if __name__=="__main__":
    unittest.main()
