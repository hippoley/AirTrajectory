"""Independent review queue from IFC-native host and geometric candidate evidence."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

def _digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def build_adjacency_review_queue(readiness):
    rows=(readiness.get("semantics") or {}).get("openings")
    if not isinstance(rows,list) or not isinstance(readiness.get("blockers"),list):
        raise ValueError("requires full IFC readiness receipt")
    if (readiness.get("control_scope") or {}).get("mode")!="ALL_OPENINGS":
        raise ValueError("review must start from full IFC inventory")
    source=(readiness.get("source") or {}).get("sha256")
    if not isinstance(source,str) or len(source)!=64:
        raise ValueError("missing source digest")
    blocked={b.get("entity_id") for b in readiness["blockers"]
             if b.get("reason")=="AMBIGUOUS_SPACE_ADJACENCY"}
    known={x["id"] for x in (readiness.get("semantics") or {}).get("spaces",[])}
    indexed={x["id"]:x for x in rows}
    if len(indexed)!=len(rows) or not blocked<=set(indexed):
        raise ValueError("missing or duplicate blocked opening evidence")
    queue=[]
    for opening_id in sorted(blocked):
        row=indexed[opening_id]
        direct=sorted(set(row.get("adjacent_spaces") or []))
        host=sorted(set(row.get("host_boundary_space_candidates") or []))
        geom=sorted(set(row.get("bbox_intersection_space_candidates") or []))
        if (set(direct)|set(host)|set(geom))-known:
            raise ValueError("candidate references a space not present in source IFC")
        suggested=sorted(set(host)&set(geom))
        queue.append({
            "opening_id":opening_id,"kind":row.get("kind"),
            "direct_boundary_spaces":direct,
            "ifc_host_element_ids":row.get("ifc_host_element_ids") or [],
            "host_boundary_candidates":host,
            "bbox_intersection_candidates":geom,
            "corroborated_candidates":suggested,
            "review_state":"HUMAN_REVIEW_REQUIRED",
            "adopted_adjacency":None,
            "evidence_limits":"host-space and 2D-bbox cues are not direct opening-side attribution; exterior status must be independently established",
        })
    result={
        "schema_version":"airtrajectory-ifc-adjacency-review-v0.1",
        "source_ifc_sha256":source,
        "status":"REVIEW_REQUIRED" if queue else "NO_AMBIGUOUS_ADJACENCY",
        "items":queue,
        "reviewed_count":0,
        "automatically_approved_count":0,
        "contam_prj_authorized":False,
    }
    return {**result,"receipt_sha256":_digest(result)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("readiness",type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    result=build_adjacency_review_queue(json.loads(a.readiness.read_text(encoding="utf8")))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps({"items":len(result["items"]),"status":result["status"]}))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
