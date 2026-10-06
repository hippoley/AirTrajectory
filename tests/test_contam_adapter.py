import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from airtrajectory.contam import CONTAMEnvironment, ContamControl, ContamXSession, co2_mass_fraction_to_ppm
from airtrajectory.topology import BuildingTopology, OpeningEdge, ZoneNode
from airtrajectory.trajectory import TransitionAction

class FakeCx:
    def __init__(self,prj_file_path,wp_mode=0,cb_option=False,*_):
        self.path=prj_file_path; self.wp_mode=wp_mode; self.cb_option=cb_option
        self.nZones=2; self.nPaths=1; self.nInputControls=2; self.nOutputControls=0; self.controls={}; self.steps=0; self.ended=False
        self.inputControls=[SimpleNamespace(name="W2_open"),SimpleNamespace(name="W1_open")]; self.outputControls=[]
    def setupSimulation(self,use_cosim=1): self.use_cosim=use_cosim
    def getVersion(self): return "fake-contract"
    def getSimTimeStep(self): return 60
    def setInputControlValue(self,n,v): self.controls[n]=v
    def doSimStep(self,n): self.steps+=n
    def getZoneMF(self,z,c): return {1:0.0012,2:0.0008}[z]-(self.steps*0.00001)
    def getPathFlow(self,p): return 0.25+self.steps*0.01
    def endSimulation(self): self.ended=True



class AmbientInitCx(FakeCx):
    last_instance=None
    def __init__(self,prj_file_path,wp_mode=0,cb_option=False,init_callback=None,*_):
        super().__init__(prj_file_path,wp_mode,cb_option)
        self.ambient={}
        AmbientInitCx.last_instance=self
        if init_callback is not None:
            init_callback(self)
    def setAmbtPressure(self,v): self.ambient["pressure_pa"]=float(v)
    def setAmbtWindSpeed(self,v): self.ambient["wind_speed_m_s"]=float(v)
    def setAmbtWindDirection(self,v): self.ambient["wind_direction_deg"]=float(v)
    def setAmbtTemperature(self,v): self.ambient["temperature_k"]=float(v)
    def setAmbtMassFraction(self,n,v): self.ambient.setdefault("mass_fractions",{})[int(n)]=float(v)

class GuardedInitialReadCx(FakeCx):
    def getZoneMF(self,z,c):
        if self.steps == 0:
            raise AssertionError("zone state read before first ContamX solve")
        return super().getZoneMF(z,c)
    def getPathFlow(self,p):
        if self.steps == 0:
            raise AssertionError("path flow read before first ContamX solve")
        return super().getPathFlow(p)

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
            self.assertEqual(s.engine.path,str(prj))
            self.assertEqual(s.engine.wp_mode,0)
            self.assertTrue(s.engine.cb_option)
            self.assertEqual(s.engine.use_cosim,1)
            self.assertEqual(meta["input_control_names"],["W2_open","W1_open"])
            self.assertEqual(s.input_control_index("W1_open"),2)
            s.set_input_control(7,.5); s.set_named_input_control("W1_open",.25); s.step()
            self.assertEqual(s.engine.controls[2],.25)
            self.assertAlmostEqual(s.zone_mass_fraction(1,1),.00119)
            self.assertAlmostEqual(s.path_flow(1),.26)
            engine=s.engine; s.close(); self.assertTrue(engine.ended)

    def test_session_initializes_explicit_ambient_boundary_before_setup(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"demo.prj"; prj.write_text("fixture")
            ambient={
                "pressure_pa":101325,
                "wind_speed_m_s":1.5,
                "wind_direction_deg":180,
                "temperature_k":298.15,
                "mass_fractions":{"1":0.00065},
            }
            s=ContamXSession(prj,binding_factory=AmbientInitCx,ambient=ambient)
            s.setup()
            self.assertEqual(
                AmbientInitCx.last_instance.ambient,
                {
                    "pressure_pa":101325.0,
                    "wind_speed_m_s":1.5,
                    "wind_direction_deg":180.0,
                    "temperature_k":298.15,
                    "mass_fractions":{1:0.00065},
                },
            )
            s.close()


    def test_session_initializes_input_controls_before_setup_and_validates_names(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"demo.prj"; prj.write_text("fixture")
            initial={
                1:{"name":"W2_open","value":0.35},
                2:{"name":"W1_open","value":0.65},
            }
            s=ContamXSession(
                prj,
                binding_factory=AmbientInitCx,
                initial_input_controls=initial,
            )
            s.setup()
            self.assertEqual(
                AmbientInitCx.last_instance.controls,
                {1:0.35,2:0.65},
            )
            s.close()

    def test_session_rejects_initial_control_name_index_drift(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"demo.prj"; prj.write_text("fixture")
            s=ContamXSession(
                prj,
                binding_factory=AmbientInitCx,
                initial_input_controls={
                    1:{"name":"W1_open","value":0.65},
                },
            )
            with self.assertRaisesRegex(RuntimeError,"mapping drift"):
                s.setup()


    def test_session_reduces_directional_path_flows_to_net_flow(self):
        class DirectionalCx(FakeCx):
            def getPathFlow(self,p): return [0.3,-0.1]
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"demo.prj"; prj.write_text("fixture")
            s=ContamXSession(prj,binding_factory=DirectionalCx)
            s.setup()
            self.assertAlmostEqual(s.path_flow(1),0.2)
            s.close()

    def test_environment_maps_window_percent_to_contam_control(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"demo.prj"; prj.write_text("fixture")
            env=CONTAMEnvironment(
                self.topology(),prj,{"living":1,"bedroom":2},
                {"W1":ContamControl(11),"W2":ContamControl(12)},
                path_numbers={"W1":1},max_steps=2,binding_factory=FakeCx,initial_co2_ppm={"living":1200,"bedroom":900}
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
            env=CONTAMEnvironment(self.topology(),prj,{"living":1,"bedroom":2},{"W1":ContamControl(1)},binding_factory=FakeCx,initial_co2_ppm={"living":1200,"bedroom":900})
            env.reset()
            with self.assertRaisesRegex(RuntimeError,"no CONTAM input-control mapping"):
                env.step([TransitionAction("W2",50)])
            env.close()

    def test_named_control_and_fixed_opening_share_contam_environment(self):
        topology=BuildingTopology.from_parts(
            [ZoneNode("living",45),ZoneNode("bedroom",30)],
            [
                OpeningEdge("W1","living","OUTSIDE","window",1.2),
                OpeningEdge("D1","living","bedroom","door",1.8),
            ],
        )
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"demo.prj"; prj.write_text("fixture")
            env=CONTAMEnvironment(
                topology,
                prj,
                {"living":1,"bedroom":2},
                {"W1":ContamControl(control_name="W1_open")},
                path_numbers={"W1":1,"D1":1},
                max_steps=2,
                binding_factory=FakeCx,
                fixed_openings={"D1":100},
                initial_openings={"W1":0,"D1":100},
                initial_co2_ppm={"living":1200,"bedroom":900},
            )
            obs,_=env.reset()
            self.assertEqual(obs["opening_pct"]["D1"],100)
            env.step([
                TransitionAction("W1",75),
                TransitionAction("D1",100),
            ])
            self.assertEqual(env.session.engine.controls[2],.75)
            with self.assertRaisesRegex(RuntimeError,"fixed CONTAM opening D1 cannot move"):
                env.step([TransitionAction("D1",50)])
            env.close()

    def test_reset_uses_explicit_initial_state_before_first_contam_solve(self):
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"demo.prj"; prj.write_text("fixture")
            env=CONTAMEnvironment(
                self.topology(),
                prj,
                {"living":1,"bedroom":2},
                {"W1":ContamControl(control_name="W1_open"),"W2":ContamControl(control_name="W2_open")},
                path_numbers={"W1":1},
                max_steps=2,
                binding_factory=GuardedInitialReadCx,
                initial_co2_ppm={"living":1400,"bedroom":900},
            )
            obs,info=env.reset()
            self.assertEqual(obs["state_source"],"prj-profile-initial")
            self.assertEqual(obs["co2_ppm"],{"living":1400.0,"bedroom":900.0})
            self.assertEqual(obs["path_flow_kg_s"],{})
            nxt,_,_,_,_=env.step([
                TransitionAction("W1",75),
                TransitionAction("W2",25),
            ])
            self.assertEqual(nxt["state_source"],"contam-solved")
            self.assertTrue(nxt["path_flow_kg_s"])
            env.close()


    def test_co2_mass_fraction_conversion(self):
        self.assertGreater(co2_mass_fraction_to_ppm(.001),600)

if __name__=="__main__":
    unittest.main()
