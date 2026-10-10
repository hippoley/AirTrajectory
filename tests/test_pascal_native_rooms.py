import importlib.util,json,sys,unittest
from pathlib import Path
script=Path(__file__).resolve().parents[1]/"scripts"/"convert_reviewed_rooms_to_pascal.py"
spec=importlib.util.spec_from_file_location("native_rooms",script)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class NativeRoomsTest(unittest.TestCase):
 def fixture(self): return {"rooms":[{"name":"living","polygon_outer_ring_m":[[0,0],[4,0],[4,5],[0,5]],"hole_count":0},{"name":"bed","polygon_outer_ring_m":[[4,0],[7,0],[7,3],[4,3]],"hole_count":0}]}
 def test_native_shape(self):
  graph=mod.convert(self.fixture())
  self.assertEqual(len(graph["nodes"]),5)
  self.assertEqual(graph["rootNodeIds"],["site_private"])
  self.assertEqual(graph["nodes"]["level_0"]["children"],["zone_private_00","zone_private_01"])
  self.assertEqual(graph["nodes"]["zone_private_00"]["type"],"zone")
  self.assertFalse(any(v["type"] in ("wall","door","window") for v in graph["nodes"].values()))
 def test_rejects_bad_inputs(self):
  for bad in ({"rooms":[]},{"rooms":[self.fixture()["rooms"][0]]*2},{"rooms":[{"name":"bad","polygon_outer_ring_m":[[0,0],[0,0],[0,0]]}]},{"rooms":[{"name":"hole","hole_count":1,"polygon_outer_ring_m":[[0,0],[1,0],[1,1]]}]}):
   with self.assertRaises(ValueError):mod.convert(bad)
if __name__=="__main__":unittest.main()
