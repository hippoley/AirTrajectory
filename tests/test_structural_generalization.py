"""Independent adversarial checks for held-out structural topology evaluation."""
import unittest
from airtrajectory.scenario import generate_structured_scenario
from airtrajectory.benchmark import held_out_family_benchmark
from airtrajectory.dataset import transition_rows


def interior_pairs(scenario):
    return {frozenset((edge.source, edge.target))
            for edge in scenario.topology.openings.values()
            if edge.source != "OUTSIDE" and edge.target != "OUTSIDE"}


class StructuralGeneralizationTests(unittest.TestCase):
    def test_families_have_distinct_graph_structures(self):
        scenarios={name:generate_structured_scenario(7,5,name)
                   for name in ("hub","loop","branch")}
        self.assertEqual({name:len(interior_pairs(s)) for name,s in scenarios.items()},
                         {"hub":4,"loop":5,"branch":4})
        degrees={}
        for name,scenario in scenarios.items():
            d={room:0 for room in scenario.topology.zones}
            for pair in interior_pairs(scenario):
                for room in pair: d[room]+=1
            degrees[name]=sorted(d.values())
        self.assertEqual(degrees["hub"],[1,1,1,1,4])
        self.assertEqual(degrees["loop"],[2,2,2,2,2])
        self.assertEqual(degrees["branch"],[1,1,1,2,3])
        self.assertEqual(interior_pairs(generate_structured_scenario(7,5,"hub")),
                         interior_pairs(scenarios["hub"]))

    def test_held_out_contract_and_dataset_lineage(self):
        result=held_out_family_benchmark(train_count=3,test_count_per_family=2,
                                         horizon_steps=3,seed=7)
        contract=result["contract"]
        self.assertEqual(contract["train_families"],["chain"])
        self.assertEqual(contract["test_families"],["hub","loop","branch"])
        self.assertTrue(contract["held_out_topology_families"])
        self.assertEqual(contract["evidence_level"],"TOY_ONLY_NOT_CONTAM_OR_FIELD")
        self.assertFalse(set(contract["train_seeds"]) & set(contract["test_seeds"]))
        for family in contract["test_families"]:
            value=result["by_family"][family]
            self.assertEqual(set(value["paired_vs_rule"]),{"bc","offline_q"})
            for name in ("rule","bc","offline_q"):
                self.assertEqual(value["metrics"][name]["episodes"],2)
                episodes=value["trajectories"][name]
                self.assertEqual([t.context["scenario_seed"] for t in episodes],
                                 contract["test_seeds"])
                row=next(transition_rows(episodes[0]))
                self.assertEqual(row["topology_family"],family)
                self.assertEqual(row["benchmark_split_sha256"],contract["split_sha256"])

    def test_unknown_family_and_invalid_counts_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"unsupported topology family"):
            generate_structured_scenario(0,5,"chain")
        with self.assertRaises(ValueError):
            held_out_family_benchmark(train_count=0)
        with self.assertRaises(ValueError):
            held_out_family_benchmark(test_count_per_family=0)


if __name__=="__main__":
    unittest.main()
