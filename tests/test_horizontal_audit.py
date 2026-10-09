import unittest
from airtrajectory.horizontal_audit import (
    DIMENSIONS,DEPENDENCIES,validate_horizontal_matrix,impacted_stories,
)


def matrix():
    return {str(i):{
        "status":"PARTIAL",
        "dimensions":{name:{"status":"MISSING","evidence":"Not demonstrated"}
                      for name in DIMENSIONS},
        "vertical_evidence":None,"independent_evidence":None,
    } for i in DEPENDENCIES}


class HorizontalAuditTests(unittest.TestCase):
    def test_unverified_matrix_is_valid_record_but_not_closed(self):
        result=validate_horizontal_matrix(matrix())
        self.assertEqual(result["status"],"PASS")
        self.assertEqual(result["verified_closed"],0)

    def test_reject_false_closure(self):
        data=matrix()
        data["1"]["status"]="VERIFIED_CLOSED"
        result=validate_horizontal_matrix(data)
        self.assertEqual(result["status"],"FAIL")
        self.assertIn("1",result["failures"])

    def test_dependency_cannot_be_skipped(self):
        data=matrix()
        data["2"]["status"]="VERIFIED_CLOSED"
        data["2"]["vertical_evidence"]="commit"
        data["2"]["independent_evidence"]="independent trace"
        data["2"]["dimensions"]={name:{"status":"VERIFIED","evidence":"trace"}
                                 for name in DIMENSIONS}
        result=validate_horizontal_matrix(data)
        self.assertIn("dependency story 1 not closed",result["failures"]["2"])

    def test_na_needs_rationale(self):
        data=matrix()
        data["1"]["dimensions"]["performance"]={
            "status":"NOT_APPLICABLE","evidence":"not used",
        }
        with self.assertRaisesRegex(ValueError,"requires rationale"):
            validate_horizontal_matrix(data)

    def test_changed_import_story_cascades_to_downstream_stories(self):
        self.assertEqual(impacted_stories({1}),list(range(1,16)))

    def test_local_change_does_not_mark_unrelated_upstream_stories(self):
        affected=impacted_stories({14})
        self.assertEqual(affected,[14])

    def test_unknown_story_change_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"unknown story IDs"):
            impacted_stories({0})

    def test_missing_dimension_is_rejected(self):
        data=matrix()
        del data["1"]["dimensions"]["state"]
        with self.assertRaisesRegex(ValueError,"horizontal dimensions"):
            validate_horizontal_matrix(data)


if __name__=="__main__":
    unittest.main()
