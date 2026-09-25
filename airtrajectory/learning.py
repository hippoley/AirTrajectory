"""Topology-local policies that transfer across room/window IDs."""
from collections import defaultdict
from .bc import ACTION_LEVELS
from .trajectory import TransitionAction

def _bucket(v,w): return int(float(v)//w)

def local_features(observation,opening_id):
    zone=observation["opening_zone"][opening_id]
    return (
        _bucket(observation["co2_ppm"][zone],100),
        min(4,int(observation.get("occupancy",{}).get(zone,0))),
        bool(observation.get("rain",False)),
        _bucket(observation.get("outdoor_temp_c",20.0),5),
    )

def _action_map(row):
    return {a["opening_id"]:float(a["target_pct"]) for a in (row.get("action") or [])}

def _nearest_level(pct):
    return min(ACTION_LEVELS,key=lambda x:abs(x-pct))

class TopologyBCPolicy:
    def __init__(self): self.counts=defaultdict(lambda:defaultdict(int))
    def fit(self,rows):
        n=0
        for row in rows:
            if row.get("is_counterfactual"): continue
            obs=row["observation"]; amap=_action_map(row)
            for opening_id in obs.get("opening_zone",{}):
                if opening_id not in amap: continue
                self.counts[local_features(obs,opening_id)][_nearest_level(amap[opening_id])]+=1;n+=1
        if not n: raise ValueError("no exterior-window behavior samples")
        return n
    def _predict_level(self,obs,opening_id):
        counts=self.counts.get(local_features(obs,opening_id))
        if not counts: return 0
        return max(counts,key=lambda a:(counts[a],-a))
    def __call__(self,obs):
        actions=[TransitionAction(w,self._predict_level(obs,w)) for w in obs.get("opening_zone",{})]
        actions.extend(TransitionAction(o,100) for o in obs.get("interior_openings",[]))
        return actions

class TopologyOfflineQPolicy:
    def __init__(self,gamma=.95,iterations=20):
        self.gamma=gamma; self.iterations=iterations
        self.support=defaultdict(set); self.q=defaultdict(dict)
    def fit(self,rows):
        samples=[]
        for row in rows:
            if row.get("is_counterfactual"): continue
            obs=row["observation"]; nxt=row["next_observation"]; amap=_action_map(row)
            for opening_id in obs.get("opening_zone",{}):
                if opening_id not in amap or opening_id not in nxt.get("opening_zone",{}): continue
                s=local_features(obs,opening_id); ns=local_features(nxt,opening_id); a=_nearest_level(amap[opening_id])
                samples.append((s,a,float(row["reward"]),ns,bool(row.get("terminated"))))
                self.support[s].add(a)
        if not samples: raise ValueError("no exterior-window transitions")
        for _ in range(self.iterations):
            accum=defaultdict(lambda:defaultdict(list))
            for s,a,r,ns,done in samples:
                allowed=self.support.get(ns,set())
                future=max((self.q.get(ns,{}).get(na,0.0) for na in allowed),default=0.0)
                accum[s][a].append(r+(0.0 if done else self.gamma*future))
            nxtq=defaultdict(dict)
            for s,acts in accum.items():
                for a,vals in acts.items(): nxtq[s][a]=sum(vals)/len(vals)
            self.q=nxtq
        return len(samples)
    def _predict_level(self,obs,opening_id):
        s=local_features(obs,opening_id); allowed=self.support.get(s,set())
        if not allowed: return 0
        return max(allowed,key=lambda a:(self.q.get(s,{}).get(a,float("-inf")),-a))
    def __call__(self,obs):
        actions=[TransitionAction(w,self._predict_level(obs,w)) for w in obs.get("opening_zone",{})]
        actions.extend(TransitionAction(o,100) for o in obs.get("interior_openings",[]))
        return actions
