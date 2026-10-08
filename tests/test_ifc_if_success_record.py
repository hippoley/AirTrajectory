import unittest

from airtrajectory.interop.ifc_if_success_record import render_if_success_record


class IfcIfSuccessRecordTests(unittest.TestCase):
    def test_blocked_receipt_renders_without_claiming_success(self):
        report={
            "status":"BLOCKED",
            "source":{"schema":"IFC2X3","path":"Duplex_A_20110907.ifc"},
            "space_count":21,
            "door_count":14,
            "window_count":24,
            "space_boundary_count":265,
            "opening_boundary_coverage":{
                "doors_total":14,"doors_mapped":14,
                "windows_total":24,"windows_mapped":14,
            },
            "control_scope":{
                "mode":"ALL_OPENINGS",
                "resolved_opening_ids":[],
            },
            "blockers":[
                {"entity_id":"W1","reason":"AMBIGUOUS_SPACE_ADJACENCY"}
            ],
        }
        md=render_if_success_record(
            report,
            test_title="Opening-to-space control readiness",
            tool_version="0.1",
        )
        self.assertIn("**BLOCKED**",md)
        self.assertIn("[x] Door-to-space",md)
        self.assertIn("[ ] Window-to-space",md)
        self.assertIn("AMBIGUOUS_SPACE_ADJACENCY",md)
        self.assertIn("not buildingSMART software certification",md)


if __name__=="__main__":
    unittest.main()
