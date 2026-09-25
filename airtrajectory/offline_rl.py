"""Conservative tabular offline-Q baseline for discrete ventilation actions."""
from collections import defaultdict
from .bc import ACTION_LEVELS, features, action_level

class OfflineQ:
    """Batch fitted-Q on logged transitions; unseen actions remain unavailable."""
    def __init__(self,gamma=0.95,iterations=20):
        self.gamma=gamma; self.iterations=iterations; self.q=defaultdict(dict); self.support=defaultdict(set)
    def fit(self,rows):
        data=[r for r in rows if not r.get("is_counterfactual")]
        if not data: raise ValueError("no behavior samples")
        for r in data: self.support[features(r["observation"])].add(action_level(r))
        for _ in range(self.iterations):
            nxt=defaultdict(dict)
            accum=defaultdict(lambda:defaultdict(list))
            for r in data:
                s=features(r["observation"]); a=action_level(r); ns=features(r["next_observation"])
                allowed=self.support.get(ns,set())
                future=max((self.q.get(ns,{}).get(na,0.0) for na in allowed),default=0.0)
                target=float(r["reward"])+(0.0 if r.get("terminated") else self.gamma*future)
                accum[s][a].append(target)
            for s,acts in accum.items():
                for a,vals in acts.items(): nxt[s][a]=sum(vals)/len(vals)
            self.q=nxt
        return len(data)
    def predict(self,observation):
        s=features(observation); allowed=self.support.get(s,set())
        if not allowed: return 0
        return max(allowed,key=lambda a:(self.q.get(s,{}).get(a,float("-inf")),-a))
