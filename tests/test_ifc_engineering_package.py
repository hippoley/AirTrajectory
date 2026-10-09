"""Source-bound engineering-to-CONTAM adapter: adversarial and integration tests."""
import copy
from dataclasses import replace
import unittest
from unittest.mock import patch
from pathlib import Path

from airtrajectory.layout import LayoutContract
from airtrajectory.ifc_engineering_package import (
    compile_ifc_engineering_package, validate_ifc_engineering_package,
)

ROOT=Path(__file__).resolve().parents[1]

class IFCEngineeringPackageTests(unittest.TestCase):
    def setUp(self):
        base=LayoutContract.from_file(ROOT/"web/data/home_topology.fixed.json")
        self.layout=replace(base,source_kind="imported-floorplan")
        self.sha="a"*64
        ids=[x.id for x in self.layout.openings]
        self.scope={"source_ifc_sha256":self.sha,"receipt_sha256":"b"*64,
                    "prj_compilation_authorized":False,
                    "candidate_openings":[{"opening_id":i} for i in ids[:-1]],
                    "excluded_openings":[{"opening_id":ids[-1]}],
                    "candidate_count":len(ids)-1,"excluded_count":1}
        self.readiness={"source":{"sha256":self.sha},"control_scope":{"mode":"ALL_OPENINGS"}}
        self.package={"schema_version":"airtrajectory-ifc-engineering-package-v0.1",
                      "source_ifc_sha256":self.sha,"topology_id":self.layout.topology_id,
                      "layout_sha256":self.layout.sha256(),
                      "scope_receipt_sha256":"b"*64,
                      "opening_treatments":{
                          i:{"disposition":"controllable" if n<len(ids)-1 else "excluded-modeled",
                             "approved":True,"engineering_reference":"review-123"}
                          for n,i in enumerate(ids)},
                      "approval":{"approved":True,"reviewer":"engineer","reviewer_role":"MEP",
                                  "reviewed_source_sha256":self.sha}}
        for key in ("metric_evidence","airflow_evidence","boundary_evidence",
                    "prj_profile","prj_review_evidence"):
            self.package[key]={"source_ifc_sha256":self.sha,"data":key}

    def test_package_calls_actual_compiler_interface_with_all_five_inputs(self):
        with patch("airtrajectory.ifc_engineering_package.build_engineering_contam_project",
                   return_value={"status":"ENGINEERING_INPUTS_READY"}) as compiler:
            result=compile_ifc_engineering_package(
                self.package,layout=self.layout,readiness=self.readiness,
                scope=self.scope,out_path="unused.prj")
            self.assertEqual(result["ifc_engineering_package"]["candidate_count"],4)
            self.assertFalse(result["runtime_verified"])
            self.assertIs(compiler.call_args.kwargs["metric_evidence"],self.package["metric_evidence"])
            self.assertEqual(compiler.call_args.kwargs["out_path"],"unused.prj")

    def test_nonapproved_mismatched_and_missing_openings_never_touch_compiler(self):
        for kind in ("source","approval","excluded","missing","bundle","scope"):
            package=copy.deepcopy(self.package)
            scope=copy.deepcopy(self.scope)
            if kind=="source": package["source_ifc_sha256"]="c"*64
            if kind=="approval": package["approval"]["approved"]=False
            if kind=="excluded":
                excluded=scope["excluded_openings"][0]["opening_id"]
                package["opening_treatments"][excluded]["disposition"]="controllable"
            if kind=="missing": package["opening_treatments"].pop(next(iter(package["opening_treatments"])))
            if kind=="bundle": package["airflow_evidence"]["source_ifc_sha256"]="d"*64
            if kind=="scope": scope["receipt_sha256"]="e"*64
            with self.subTest(kind=kind),patch(
                "airtrajectory.ifc_engineering_package.build_engineering_contam_project"
            ) as compiler:
                with self.assertRaises(ValueError):
                    compile_ifc_engineering_package(
                        package,layout=self.layout,readiness=self.readiness,
                        scope=scope,out_path="never-write.prj")
                compiler.assert_not_called()

if __name__=="__main__":
    unittest.main()
