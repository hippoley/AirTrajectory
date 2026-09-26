import json
import tempfile
import unittest
from airtrajectory.trajectory import Trajectory, TrajectoryStep, TransitionAction, RewardVector
from pathlib import Path

from airtrajectory import (
    ActuatorFeedback, BuildingTopology, FastFlowField, OpeningEdge, SemanticAction,
    SensorReading, ToyMultizoneEnvironment, TransitionAction, ZoneNode,
    TrajectoryStore, exhaustive_opening_search, fork_actions, fork_window_levels, rollout,
)


from airtrajectory.physical import DriverCapabilities, PhysicalWindowEnvironment, RulePolicy, SafetyResolver, record_physical_trajectory, validate_physical_tau0
from airtrajectory.drivers import FakePhysicalWindowDriver, WindowPilotHTTPDriver
from airtrajectory.api import fork_request
from airtrajectory.telemetry import DecisionTelemetry
from airtrajectory.dataset import transition_rows, counterfactual_rows
from airtrajectory.bc import TabularBC
from airtrajectory.offline_rl import OfflineQ


class CoreTests(unittest.TestCase):
    def test_windowpilot_bridge_is_explicitly_simulated_and_estimated_only(self):
        state={
            "thing_model":{
                "window":{"open_pct":40},
                "sensors":{"co2_ppm":1350,"rain":False,"temp_indoor":25.0,"humidity":55,"wind_speed":2.2},
            }
        }
        calls=[]
        def request(method,path,payload):
            calls.append((method,path,payload))
            return state
        driver=WindowPilotHTTPDriver(request_json=request)
        caps=driver.capabilities()
        self.assertTrue(caps.simulated)
        self.assertFalse(caps.measured_position)
        readings=driver.read_sensors()
        self.assertEqual({r.sensor_type for r in readings},{"co2","rain","temperature","humidity","wind_speed"})
        feedback=driver.set_position("w1",40)
        self.assertIsNone(feedback.measured_position_pct)
        self.assertEqual(feedback.estimated_position_pct,40)
        self.assertIn(("POST","/api/window/open",{"target_pct":40.0}),calls)

    def test_windowpilot_bridge_can_accept_verified_measured_feedback(self):
        now=1234.0
        state={
            "thing_model":{
                "window":{"open_pct":40},
                "sensors":{"co2_ppm":1350,"rain":False,"temp_indoor":25.0,"humidity":55,"wind_speed":2.2},
                "sensor_timestamps":{"co2_ppm":now,"rain":now,"temperature":now,"humidity":now,"wind_speed":now},
            }
        }
        caps={
            "execution":{"transport":"rs485-verified","simulated":False,"measured_position":True},
            "position_feedback":{"position_pct":40.5,"timestamp":now,"measured":True,"quality":"encoder-measured"},
        }
        def request(method,path,payload):
            if path=="/api/capabilities": return caps
            return state
        driver=WindowPilotHTTPDriver(request_json=request,clock_fn=lambda: now,sleep_fn=lambda _:None)
        dc=driver.capabilities()
        self.assertFalse(dc.simulated)
        self.assertTrue(dc.measured_position)
        feedback=driver.set_position("w1",40)
        self.assertEqual(feedback.measured_position_pct,40.5)
        self.assertIsNone(feedback.estimated_position_pct)
        self.assertEqual(feedback.timestamp,now)

    def test_windowpilot_rejects_pre_command_measured_feedback(self):
        clock={"now":100.0}
        state={
            "thing_model":{
                "window":{"open_pct":0},
                "sensors":{"co2_ppm":1350,"rain":False},
                "sensor_timestamps":{"co2_ppm":100.0,"rain":100.0},
            }
        }
        caps={
            "execution":{"transport":"verified","simulated":False,"measured_position":True},
            "position_feedback":{"position_pct":40.0,"timestamp":99.0,"measured":True,"quality":"stale"},
        }
        def request(method,path,payload):
            if path=="/api/capabilities": return caps
            return state
        def now():
            value=clock["now"]
            clock["now"]+=1.0
            return value
        driver=WindowPilotHTTPDriver(
            request_json=request,clock_fn=now,sleep_fn=lambda _:None,
            feedback_timeout_s=1.0,feedback_poll_interval_s=0,
        )
        with self.assertRaises(RuntimeError):
            driver.set_position("w1",40)

    def test_windowpilot_hardware_sensor_requires_source_timestamp(self):
        state={
            "thing_model":{
                "window":{"open_pct":40},
                "sensors":{"co2_ppm":1350,"rain":False},
            }
        }
        caps={"execution":{"transport":"rs485-verified","simulated":False,"measured_position":True}}
        def request(method,path,payload):
            if path=="/api/capabilities": return caps
            return state
        driver=WindowPilotHTTPDriver(request_json=request)
        with self.assertRaises(RuntimeError):
            driver.read_sensors()

    def test_windowpilot_bridge_cannot_claim_real_tau0(self):
        state={
            "thing_model":{
                "window":{"open_pct":50},
                "sensors":{"co2_ppm":1400,"rain":False},
            }
        }
        def request(method,path,payload): return state
        env=PhysicalWindowEnvironment(WindowPilotHTTPDriver(request_json=request),"w1")
        with tempfile.TemporaryDirectory() as d:
            trajectory=record_physical_trajectory(env,RulePolicy("w1"),SafetyResolver(),"windowpilot-bridge",TrajectoryStore(Path(d)/"tau.jsonl"))
        report=validate_physical_tau0(trajectory)
        self.assertFalse(report.valid_tau0)
        self.assertTrue(any("simulated" in reason for reason in report.reasons))


    def test_rollout_safety_gate_preserves_proposal_and_records_intervention(self):
        from airtrajectory.scenario import generate_chain_scenario
        from airtrajectory.environment import ScenarioMultizoneEnvironment
        scenario=generate_chain_scenario(4,rooms=2)
        scenario=type(scenario)(
            id=scenario.id,topology=scenario.topology,initial_co2=scenario.initial_co2,
            occupancy=scenario.occupancy,rain=True,outdoor_co2=scenario.outdoor_co2,
            outdoor_temp_c=scenario.outdoor_temp_c,
        )
        env=ScenarioMultizoneEnvironment(scenario,horizon_steps=1)
        exterior=[e.id for e in scenario.topology.openings.values() if e.source==scenario.topology.outside_id or e.target==scenario.topology.outside_id]
        def unsafe(_):
            return [TransitionAction(e,100) for e in exterior]
        trajectory=rollout(env,unsafe,scenario.id,"unsafe",max_steps=1,safety_resolver=SafetyResolver())
        step=trajectory.steps[0]
        self.assertTrue(any(a.target_pct==100 for a in step.proposed_actions))
        self.assertTrue(all(a.target_pct==0 for a in step.executed_actions))
        self.assertEqual(step.intervention,"RAIN_SAFE_CLOSE")
        self.assertTrue(step.info["safety_intervened"])


    def test_offline_q_never_selects_unseen_action(self):
        rows=[
          {"observation":{"co2":1400},"next_observation":{"co2":1300},"action":[{"opening_id":"W1","target_pct":50}],"reward":1.0,"terminated":False,"is_counterfactual":False},
          {"observation":{"co2":1450},"next_observation":{"co2":1350},"action":[{"opening_id":"W1","target_pct":50}],"reward":1.0,"terminated":True,"is_counterfactual":False},
          {"observation":{"co2":1400},"next_observation":{"co2":900},"action":[{"opening_id":"W1","target_pct":100}],"reward":99.0,"terminated":True,"is_counterfactual":True},
        ]
        q=OfflineQ(); self.assertEqual(q.fit(rows),2)
        self.assertEqual(q.predict({"co2":1420}),50)
        self.assertEqual(q.predict({"co2":700}),0)


    def test_bc_learns_executed_behavior_and_ignores_counterfactuals(self):
        rows=[
            {"observation":{"co2":1400,"rain":True},"action":[{"opening_id":"W1","target_pct":0}],"is_counterfactual":False},
            {"observation":{"co2":1450,"rain":True},"action":[{"opening_id":"W1","target_pct":0}],"is_counterfactual":False},
            {"observation":{"co2":1400,"rain":True},"action":[{"opening_id":"W1","target_pct":100}],"is_counterfactual":True},
        ]
        model=TabularBC(); self.assertEqual(model.fit(rows),2)
        self.assertEqual(model.predict({"co2":1420,"rain":True}),0)
        self.assertEqual(model.evaluate(rows)["accuracy"],1.0)

    def test_bc_fails_closed_outside_dataset_support(self):
        model=TabularBC()
        model.fit([{"observation":{"co2":1300},"action":[{"opening_id":"W1","target_pct":50}],"is_counterfactual":False}])
        self.assertEqual(model.predict({"co2":700}),0)

    def test_dataset_uses_executed_action_and_preserves_proposal(self):
        trajectory=Trajectory("demo","rule")
        trajectory.append(TrajectoryStep(0,{"co2":1400},[TransitionAction("W1",50)],[TransitionAction("W1",0)],{"co2":1390},RewardVector(safety=-1),intervention="RAIN_SAFE_CLOSE",info={"trace_id":"trace-1","provenance":"physical"}))
        row=list(transition_rows(trajectory))[0]
        self.assertEqual(row["proposed_actions"][0]["target_pct"],50)
        self.assertEqual(row["action"][0]["target_pct"],0)
        self.assertEqual(row["trace_id"],"trace-1")
        self.assertFalse(row["is_counterfactual"])

    def test_counterfactual_rows_are_not_behavior_samples(self):
        artifact={"request_id":"r1","trace_id":"t1","topology_id":"demo-3zone","backend":"toy","origin_kind":"post-action-snapshot","branches":[{"label":"VENT50","target_pct":50,"end_co2_ppm":900,"return":1.2,"provenance":"backend-generated"}]}
        row=list(counterfactual_rows(artifact))[0]
        self.assertTrue(row["is_counterfactual"])
        self.assertEqual(row["trace_id"],"t1")

    def topology(self):
        return BuildingTopology.from_parts(
            [ZoneNode("living", 45), ZoneNode("bedroom", 30)],
            [
                OpeningEdge("w1", "living", "OUTSIDE", "window", 1.2),
                OpeningEdge("door", "living", "bedroom", "door", 1.8),
                OpeningEdge("w2", "bedroom", "OUTSIDE", "window", 1.0),
            ],
        )

    def test_opening_reduces_co2(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 900})
        before, _ = env.reset()
        after, _, _, _, _ = env.step([TransitionAction("w1", 100)])
        self.assertLess(after["co2_ppm"]["living"], before["co2_ppm"]["living"])

    def test_toy_backend_respects_dt_minutes(self):
        fast = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 900}, dt_minutes=1)
        slow = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 900}, dt_minutes=5)
        fast.reset(); slow.reset()
        a=[TransitionAction("w1",100)]
        fast_after,_,_,_,_=fast.step(a)
        slow_after,_,_,_,_=slow.step(a)
        self.assertLess(slow_after["co2_ppm"]["living"], fast_after["co2_ppm"]["living"])

    def test_rollout_preserves_learning_fields(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 900}, horizon_steps=4)
        def policy(_):
            return [TransitionAction("w1", 50), TransitionAction("door", 100)]
        trajectory = rollout(env, policy, "two-room", "fixed", max_steps=10)
        self.assertEqual(len(trajectory.steps), 4)
        self.assertEqual(trajectory.steps[0].proposed_actions, trajectory.steps[0].executed_actions)
        self.assertIn("co2_ppm", trajectory.steps[-1].next_observation)

    def test_physical_trajectory_schema_preserves_semantic_and_feedback_layers(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 900}, horizon_steps=1)
        trajectory = rollout(env, lambda _: [TransitionAction("w1", 50)], "two-room", "rule-v1", max_steps=1)
        step = trajectory.steps[0]
        step.semantic_actions.append(SemanticAction("window_group", "living_windows", "VENT", 50))
        step.sensor_readings.append(SensorReading("co2-living", "co2", 1400, "ppm", 1.0, "good"))
        step.actuator_feedback.append(ActuatorFeedback("actuator-w1", 2.0, measured_position_pct=48))
        payload = trajectory.to_dict()
        self.assertEqual(payload["schema_version"], "0.2")
        self.assertEqual(payload["steps"][0]["semantic_actions"][0]["command"], "VENT")
        self.assertEqual(payload["steps"][0]["actuator_feedback"][0]["measured_position_pct"], 48)
        self.assertIsNone(payload["steps"][0]["actuator_feedback"][0]["estimated_position_pct"])

    def test_feedback_separates_measured_and_estimated_position(self):
        feedback = ActuatorFeedback("actuator-w1", 1.0, estimated_position_pct=50, quality="estimated")
        self.assertIsNone(feedback.measured_position_pct)
        self.assertEqual(feedback.estimated_position_pct, 50)

    def test_fake_physical_runtime_records_tau0_contract(self):
        driver=FakePhysicalWindowDriver(co2_ppm=1400,measured_feedback=True)
        env=PhysicalWindowEnvironment(driver,"w1")
        with tempfile.TemporaryDirectory() as d:
            store=TrajectoryStore(Path(d)/"tau0.jsonl")
            trajectory=record_physical_trajectory(env,RulePolicy("w1"),SafetyResolver(),"physical-demo",store)
            payload=json.loads((Path(d)/"tau0.jsonl").read_text().strip())
        self.assertEqual(trajectory.environment_kind,"synthetic")
        report=validate_physical_tau0(trajectory)
        self.assertFalse(report.valid_tau0)
        self.assertTrue(any("simulated" in r for r in report.reasons))
        self.assertEqual(payload["context"]["reset_info"]["driver"],"FakePhysicalWindowDriver")
        self.assertEqual(payload["steps"][0]["semantic_actions"][0]["command"],"VENT")
        self.assertEqual(payload["steps"][0]["executed_actions"][0]["target_pct"],50)
        self.assertEqual(payload["steps"][0]["actuator_feedback"][0]["measured_position_pct"],50)

    def test_missing_rain_evidence_fails_closed(self):
        class NoRain(FakePhysicalWindowDriver):
            def read_sensors(self):
                return [r for r in super().read_sensors() if r.sensor_type!="rain"]
        env=PhysicalWindowEnvironment(NoRain(co2_ppm=1500),"w1")
        observation,_=env.reset()
        decision=SafetyResolver().resolve(observation,RulePolicy("w1")(observation))
        self.assertEqual(decision.intervention,"RAIN_EVIDENCE_MISSING")
        self.assertEqual(decision.executed[0].target_pct,0)

    def test_hold_with_unknown_position_does_not_invent_close(self):
        actions=RulePolicy("w1")({"co2_ppm":1000,"rain":False,"opening_pct":None})
        self.assertEqual(actions,[])

    def test_stale_actuator_feedback_is_rejected(self):
        class StaleFeedback(FakePhysicalWindowDriver):
            def set_position(self,opening_id,target_pct):
                f=super().set_position(opening_id,target_pct)
                return ActuatorFeedback(f.actuator_id,1.0,measured_position_pct=f.measured_position_pct,estimated_position_pct=f.estimated_position_pct,quality=f.quality)
        env=PhysicalWindowEnvironment(StaleFeedback(),"w1",max_feedback_age_s=1)
        observation,_=env.reset()
        with self.assertRaisesRegex(RuntimeError,"stale actuator feedback"):
            env.step([TransitionAction("w1",50)])

    def test_tau0_audit_accepts_non_simulated_measured_contract(self):
        class ContractReal(FakePhysicalWindowDriver):
            def capabilities(self):
                return DriverCapabilities("external-test-contract",False,True,("co2","rain"))
        env=PhysicalWindowEnvironment(ContractReal(co2_ppm=1400,measured_feedback=True),"w1",require_measured_feedback=True)
        with tempfile.TemporaryDirectory() as d:
            trajectory=record_physical_trajectory(env,RulePolicy("w1"),SafetyResolver(),"physical-contract",TrajectoryStore(Path(d)/"tau0.jsonl"))
        report=validate_physical_tau0(trajectory)
        self.assertTrue(report.valid_tau0,report.reasons)

    def test_rain_safety_intervention_overrides_rule_policy(self):
        driver=FakePhysicalWindowDriver(co2_ppm=1400,rain=True)
        env=PhysicalWindowEnvironment(driver,"w1")
        with tempfile.TemporaryDirectory() as d:
            trajectory=record_physical_trajectory(env,RulePolicy("w1"),SafetyResolver(),"physical-demo",TrajectoryStore(Path(d)/"tau0.jsonl"))
        step=trajectory.steps[0]
        self.assertEqual(step.proposed_actions[0].target_pct,50)
        self.assertEqual(step.executed_actions[0].target_pct,0)
        self.assertEqual(step.intervention,"RAIN_SAFE_CLOSE")

    def test_stale_sensor_blocks_physical_control(self):
        env=PhysicalWindowEnvironment(FakePhysicalWindowDriver(sensor_age_s=30),"w1",max_sensor_age_s=5)
        with self.assertRaisesRegex(RuntimeError,"stale sensor"):
            env.reset()

    def test_measured_feedback_gate_rejects_estimate_only_driver(self):
        env=PhysicalWindowEnvironment(FakePhysicalWindowDriver(measured_feedback=False),"w1",require_measured_feedback=True)
        observation,_=env.reset()
        with self.assertRaisesRegex(RuntimeError,"measured actuator position required"):
            env.step(RulePolicy("w1")(observation))

    def test_invalid_topology_rejected(self):
        with self.assertRaises(ValueError):
            BuildingTopology.from_parts(
                [ZoneNode("living", 45)],
                [OpeningEdge("broken", "living", "missing", "door", 1.0)],
            )

    def test_forks_share_origin_and_restore_source(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 1100}, horizon_steps=20)
        env.reset()
        env.step([TransitionAction("door", 100)])
        origin = env.snapshot()
        branches = fork_actions(
            env,
            {
                "open25": [TransitionAction("w1", 25), TransitionAction("door", 100)],
                "open75": [TransitionAction("w1", 75), TransitionAction("door", 100)],
            },
            horizon_steps=5,
        )
        self.assertEqual(env.snapshot(), origin)
        self.assertLess(
            branches["open75"].observations[-1]["co2_ppm"]["living"],
            branches["open25"].observations[-1]["co2_ppm"]["living"],
        )

    def test_canonical_window_fork_has_five_branches_and_restores_origin(self):
        env=ToyMultizoneEnvironment(self.topology(),{"living":1400,"bedroom":900},horizon_steps=40)
        env.reset(); env.step([TransitionAction("door",100),TransitionAction("w1",50)])
        origin=env.snapshot()
        branches=fork_window_levels(env,"w1",horizon_steps=5)
        self.assertEqual(list(branches),["CLOSE","VENT25","VENT50","VENT75","OPEN100"])
        self.assertEqual(env.snapshot(),origin)
        self.assertLess(branches["OPEN100"].observations[-1]["co2_ppm"]["living"],branches["CLOSE"].observations[-1]["co2_ppm"]["living"])

    def test_fork_request_reconstructs_post_action_origin(self):
        response=fork_request({
            "request_id":"tau-01","topology_id":"demo-3zone","opening_id":"W1",
            "origin":{"co2_ppm":{"living":1400,"bedroom":980,"study":840},
                      "opening_pct":{"W1":50,"W2":0,"W3":0,"D1":100,"D2":100}},
            "horizon_minutes":5,
        })
        self.assertEqual(response["request_id"],"tau-01")
        self.assertEqual([b["label"] for b in response["branches"]],["CLOSE","VENT25","VENT50","VENT75","OPEN100"])
        self.assertLess(response["branches"][-1]["end_co2_ppm"],response["branches"][0]["end_co2_ppm"])
        self.assertTrue(all("backend-generated" in b["provenance"] for b in response["branches"]))

    def test_fork_request_writes_decision_trace(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"decisions.jsonl"
            telemetry=DecisionTelemetry(path)
            response=fork_request({"request_id":"tau-traced","topology_id":"demo-3zone","opening_id":"W1",
                "origin":{"co2_ppm":{"living":1400,"bedroom":980,"study":840},"opening_pct":{"W1":50,"W2":0,"W3":0,"D1":100,"D2":100}},
                "horizon_minutes":3},telemetry=telemetry)
            trace=json.loads(path.read_text().strip())
        self.assertEqual(response["request_id"],"tau-traced")
        self.assertEqual(trace["span_name"],"counterfactual.fork")
        self.assertEqual(trace["attributes"]["request_id"],"tau-traced")
        self.assertEqual(trace["attributes"]["branch.count"],5)
        self.assertEqual(len([e for e in trace["events"] if e["name"]=="branch.result"]),5)

    def test_fork_request_rejects_unknown_topology(self):
        with self.assertRaisesRegex(ValueError,"unsupported topology_id"):
            fork_request({"topology_id":"unknown","opening_id":"W1","origin":{"co2_ppm":1400,"opening_pct":50}})

    def test_fast_field_is_deterministic_and_opening_sensitive(self):
        field = FastFlowField(self.topology())
        points = [(10.0, 20.0), (30.0, 40.0)]
        closed = field.sample(points, {"w1": 0, "door": 0, "w2": 0}, 25, 2.8)
        opened = field.sample(points, {"w1": 75, "door": 100, "w2": 25}, 25, 2.8)
        repeated = field.sample(points, {"w1": 75, "door": 100, "w2": 25}, 25, 2.8)
        self.assertEqual(opened, repeated)
        self.assertNotEqual(closed.vectors, opened.vectors)
        self.assertEqual(opened.backend, "fast-field-v1")

    def test_exhaustive_search_ranks_and_restores(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 1100}, horizon_steps=20)
        env.reset()
        env.step([TransitionAction("door", 100)])
        origin = env.snapshot()
        results = exhaustive_opening_search(
            env,
            ("w1", "w2"),
            levels=(0, 50, 100),
            fixed_actions=(TransitionAction("door", 100),),
            horizon_steps=5,
            top_k=3,
        )
        self.assertEqual(len(results), 3)
        self.assertEqual(env.snapshot(), origin)
        self.assertGreaterEqual(results[0].branch.return_value, results[1].branch.return_value)
        self.assertGreaterEqual(results[1].branch.return_value, results[2].branch.return_value)
        self.assertTrue(all(result.label.startswith("SEARCH · ") for result in results))

    def test_exhaustive_search_rejects_empty_openings(self):
        env = ToyMultizoneEnvironment(self.topology())
        env.reset()
        with self.assertRaises(ValueError):
            exhaustive_opening_search(env, (), top_k=1)


if __name__ == "__main__":
    unittest.main()
