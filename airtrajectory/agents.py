"""Topology-aware reference agents."""
from .trajectory import TransitionAction

class MultiWindowRuleAgent:
    """Rule baseline that acts over arbitrary zone/window IDs instead of fixed W1/W2 vectors."""
    def __init__(self,topology,open_threshold=1200.0,close_threshold=800.0):
        self.topology=topology; self.open_threshold=open_threshold; self.close_threshold=close_threshold

    def __call__(self,obs):
        co2=obs["co2_ppm"]; openings=obs["opening_pct"]; rain=bool(obs.get("rain",False))
        actions=[]
        for edge in self.topology.openings.values():
            if not edge.controllable: continue
            exterior=edge.source==self.topology.outside_id or edge.target==self.topology.outside_id
            if not exterior:
                actions.append(TransitionAction(edge.id,100))
                continue
            zone=edge.target if edge.source==self.topology.outside_id else edge.source
            if rain: target=0
            elif co2[zone] >= self.open_threshold: target=75
            elif co2[zone] <= self.close_threshold: target=0
            else: target=openings.get(edge.id,25)
            actions.append(TransitionAction(edge.id,target))
        return actions
