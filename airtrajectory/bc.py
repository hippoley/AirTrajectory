"""Dependency-light behavior cloning baseline for discrete window actions."""
from collections import defaultdict
import json
from pathlib import Path
ACTION_LEVELS=(0,25,50,75,100)
def _bucket(value,width=100.0): return int(float(value)//width)
def features(observation):
    co2=observation.get("co2_ppm",observation.get("co2"))
    if isinstance(co2,dict): co2=co2.get("living")
    if co2 is None: raise ValueError("BC requires CO2 observation")
    return (_bucket(co2),bool(observation.get("rain",False)))
def action_level(row):
    actions=row.get("action") or []
    if len(actions)!=1: raise ValueError("BC baseline requires exactly one executed action")
    pct=float(actions[0]["target_pct"])
    return min(ACTION_LEVELS,key=lambda x:abs(x-pct))
class TabularBC:
    """Empirical behavior policy; fail-closed outside demonstrated support."""
    def __init__(self): self.counts=defaultdict(lambda:defaultdict(int))
    def fit(self,rows):
        n=0
        for row in rows:
            if row.get("is_counterfactual"): continue
            self.counts[features(row["observation"])][action_level(row)]+=1;n+=1
        if not n: raise ValueError("no behavior samples")
        return n
    def predict(self,observation):
        counts=self.counts.get(features(observation))
        if not counts: return 0
        return max(counts,key=lambda a:(counts[a],-a))
    def evaluate(self,rows):
        rows=[r for r in rows if not r.get("is_counterfactual")]
        correct=sum(self.predict(r["observation"])==action_level(r) for r in rows)
        return {"samples":len(rows),"accuracy":correct/len(rows) if rows else 0.0}
    def to_dict(self):
        return {"schema_version":"0.1","action_levels":list(ACTION_LEVELS),"policy":{"|".join(map(str,k)):dict(v) for k,v in self.counts.items()}}
def load_jsonl(path):
    with Path(path).open(encoding="utf-8") as f: return [json.loads(x) for x in f if x.strip()]
