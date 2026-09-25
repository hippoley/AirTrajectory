"""Reward/Judge used by simulation trajectories."""
from .trajectory import RewardVector

class VentilationJudge:
    def __init__(self,iaq_target_ppm=800.0):
        self.iaq_target_ppm=iaq_target_ppm

    def score(self,observation,next_observation,actions,previous_openings):
        co2=next_observation["co2_ppm"]
        iaq=-sum(max(0.0,v-self.iaq_target_ppm)/400.0 for v in co2.values())
        rain=bool(next_observation.get("rain",False))
        outdoor_temp=float(next_observation.get("outdoor_temp_c",20.0))
        exterior_ids=set(next_observation.get("exterior_openings",[]))
        open_exterior=sum(a.target_pct/100.0 for a in actions if a.opening_id in exterior_ids)
        safety=-10.0*open_exterior if rain else 0.0
        temp_gap=max(0.0,abs(outdoor_temp-22.0)-5.0)
        comfort=-(temp_gap/10.0)*open_exterior
        energy=-(temp_gap/15.0)*open_exterior
        wear=-sum(abs(a.target_pct-float(previous_openings.get(a.opening_id,0)))/100.0 for a in actions)
        return RewardVector(iaq=iaq,comfort=comfort,energy=energy,safety=safety,actuator_wear=wear)
