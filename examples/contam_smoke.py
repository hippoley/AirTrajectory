"""Run a real contamxpy smoke test against a supplied CONTAM PRJ.

This command fails if contamxpy/native ContamX support or the PRJ is unavailable.
That failure is intentional: mocked bindings do not count as CONTAM execution.
"""
import argparse, json
from airtrajectory.contam import ContamXSession, co2_mass_fraction_to_ppm

def main():
    p=argparse.ArgumentParser()
    p.add_argument("prj")
    p.add_argument("--zone",type=int,default=1)
    p.add_argument("--contaminant",type=int,default=1)
    p.add_argument("--path",type=int)
    p.add_argument("--steps",type=int,default=2)
    a=p.parse_args()
    with ContamXSession(a.prj,verbosity=1) as session:
        before=session.zone_mass_fraction(a.zone,a.contaminant)
        samples=[]
        for i in range(a.steps):
            session.step()
            mf=session.zone_mass_fraction(a.zone,a.contaminant)
            row={"step":i+1,"mass_fraction":mf,"co2_ppm":co2_mass_fraction_to_ppm(mf)}
            if a.path is not None: row["path_flow"]=session.path_flow(a.path)
            samples.append(row)
        print(json.dumps({"status":"CONTAM_EXECUTED","before_mass_fraction":before,"samples":samples},indent=2))

if __name__=="__main__":
    main()
