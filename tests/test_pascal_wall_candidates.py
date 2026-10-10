import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('mod',Path(__file__).resolve().parents[1]/'scripts/assemble_pascal_wall_candidates.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class TestWalls(unittest.TestCase):
 def test_real_native_shapes(self):
  source={'nodes':{'level_0':{'id':'level_0','type':'level','children':['z']},'z':{'id':'z','type':'zone','parentId':'level_0','polygon':[[0,0],[3,0],[3,2],[0,2]]}},'rootNodeIds':[]}
  chains={'chains':[{'candidate_id':'c','polyline_m':[[0,0],[3,0],[3,2]]},{'candidate_id':'dup','polyline_m':[[3,0],[0,0]]}]}
  out,report=mod.build(source,chains)
  self.assertEqual(report['new_wall_candidates'],2)
  self.assertEqual(len(out['nodes']),4)
  self.assertEqual(source['nodes']['level_0']['children'],['z'])
  self.assertFalse(report['physics_authorized'])
  for item in (out['nodes']['cad_wall_candidate_000'],out['nodes']['cad_wall_candidate_001']):
   self.assertEqual(item['type'],'wall')
   self.assertEqual(item['parentId'],'level_0')
   self.assertEqual(item['metadata']['airtrajectory_status'],'cad-unreviewed-wall-candidate')
 def test_reject_no_perimeter(self):
  with self.assertRaises(ValueError):
   mod.build({'nodes':{'level_0':{'type':'level'},'z':{'type':'zone','polygon':[[0,0],[2,0],[2,2],[0,2]]}}},{'chains':[{'candidate_id':'far','polyline_m':[[20,20],[21,20]]}]})
if __name__=='__main__':unittest.main()
