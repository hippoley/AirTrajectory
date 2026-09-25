import tempfile
import unittest
from pathlib import Path

from airtrajectory.contam import CONTAMEnvironment, ContamControl, ContamXSession, co2_mass_fraction_to_ppm
from airtrajectory.topology import BuildingTopology, OpeningEdge, ZoneNode
from airtrajectory.trajectory import TransitionAction

class FakeCx:
    def __init__(self,*_):
        self.nZones=2; self.nPaths=1; self.controls={}; self.steps=0; self.ended=False
    def setupSimulation(self,path,use_cosim): self.path=path; self.use_cosim=use_cosim
    def getVersion(self): return "fake-contract"
    def getSimTimeStep(self): return 60
    def setInputControlValue(self,n,v): self.controls[n]=v
    def doSimStep(self,n): self.steps+=n
    def getZoneMF(self,z,c): return {1:0.0012,2:0.0008}[z]-(self.steps*0.00001)
    def getPathFlow(self,p): return 0.25+self.steps*0.01
    def endSimulation(self): self.ended=True

class ContamAdapterTests(unittest.TestCase):
    def topology(self):
        return BuildingTopology.from_parts(
            [ZoneNode("living",45),ZoneNode("bedroom",30)],
            [OpeningEdge("W1","living","OUTSIDE","window",1.2),OpeningEdge("W2","bedroom","OUTSIDE","window",1.0)]
        )

    def test_session_calls_real_binding_lifecycle_contract(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"demo.prj"; prj.write_text("fixture")
            s=ContamXSession(prj,binding_factory=FakeCx)
            meta=s.setup(); self.assertEqual(meta["time_step_s"],60)
            s.set_input_control(7,.5); s.step()
            self.assertAlmostEqual(s.zone_mass_fraction(1,1),.00119)
            self.assertAlmostEqual(s.path_flow(1),.26)
            engine=s.engine; s.close(); self.assertTrue(engine.ended)

    def test_environment_maps_window_percent_to_contam_control(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"demo.prj"; prj.write_text("fixture")
            env=CONTAMEnvironment(
                self.topology(),prj,{"living":1,"bedroom":2},
                {"W1":ContamControl(11),"W2":ContamControl(12)},
                path_numbers={"W1":1},max_steps=2,binding_factory=FakeCx
            )
            obs,info=env.reset()
            self.assertEqual(info["physics_fidelity"],"CONTAM")
            nxt,_,done,_,_=env.step([TransitionAction("W1",50),TransitionAction("W2",0)])
            self.assertEqual(env.session.engine.controls[11],.5)
            self.assertIn("path_flow_kg_s",nxt)
            self.assertFalse(done)
            env.close()

    def test_missing_control_mapping_fails_instead_of_faking_actuation(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"demo.prj"; prj.write_text("fixture")
            env=CONTAMEnvironment(self.topology(),prj,{"living":1,"bedroom":2},{"W1":ContamControl(1)},binding_factory=FakeCx)
            env.reset()
            with self.assertRaisesRegex(RuntimeError,"no CONTAM input-control mapping"):
                env.step([TransitionAction("W2",50)])
            env.close()

    def test_co2_mass_fraction_conversion(self):
        self.assertGreater(co2_mass_fraction_to_ppm(.001),600)

if __name__=="__main__":
    unittest.main()
