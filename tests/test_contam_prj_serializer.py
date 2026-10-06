import copy
import unittest

from airtrajectory.contam_prj_serializer import render_minimal_prj, write_minimal_prj


def manifest():
    return {
        "compiler": "contam-prj-profiled-manifest",
        "topology_id": "demo",
        "layout_contract_sha256": "a"*64,
        "mapping_sha256": "b"*64,
        "airflow_binding_sha256": "c"*64,
        "boundary_binding_sha256": "d"*64,
        "zone_numbers": {"zone:living":1,"zone:bedroom":2,"zone:study":3},
        "zones": [
            {"key":"zone:living","layout_zone_id":"living","volume_m3":75.0,"contam_zone_number":1,"level_number":1,"relative_height_m":0.0,"initial_temperature_k":298.15,"initial_pressure_pa":0.0},
            {"key":"zone:bedroom","layout_zone_id":"bedroom","volume_m3":37.5,"contam_zone_number":2,"level_number":1,"relative_height_m":0.0,"initial_temperature_k":298.15,"initial_pressure_pa":0.0},
            {"key":"zone:study","layout_zone_id":"study","volume_m3":40.0,"contam_zone_number":3,"level_number":1,"relative_height_m":0.0,"initial_temperature_k":298.15,"initial_pressure_pa":0.0},
        ],
        "airflow_elements": [
            {"key":f"element:{oid}","layout_opening_id":oid,"contam_element_number":i,"flow_exponent":0.5,"flow_area_m2":1.0,"hydraulic_diameter_m":1.0,"discharge_coefficient":0.6,"laminar_flow_coefficient":0.001,"turbulent_flow_coefficient":0.1,"transition_reynolds_number":30.0}
            for i,oid in enumerate(["W1","W2","W3","D1","D2"],1)
        ],
        "flow_paths": [],
        "contaminants": [{
            "key":"co2","name":"CO2","contam_contaminant_number":1,
            "initial_zone_mass_fraction":{"zone:living":0.002,"zone:bedroom":0.0015,"zone:study":0.0012}
        }],
        "species_definitions": [{"key":"co2","name":"CO2","contam_contaminant_number":1,"molecular_weight_g_mol":44.0095}],
        "level_records": [{"level_number":1,"name":"Ground","reference_height_m":0.0}],
        "project_controls": {"mode":"steady"},
        "weather": {"outdoor_temperature_c":25.0,"barometric_pressure_pa":101325.0,"wind_speed_m_s":1.5,"wind_direction_deg":180.0},
        "species_definitions": [{"key":"co2","name":"CO2","contam_contaminant_number":1,"molecular_weight_g_mol":44.0095}],
    }


def add_path(m,key,num,kind,boundary,source,target,element,azimuth,x,y,h):
    m["flow_paths"].append({
        "key":key,"contam_path_number":num,"kind":kind,"boundary_kind":boundary,
        "from":source,"to":target,
        "airflow_element":{"contam_element_number":element},
        "prj_flags":0,"filter_number":0,"wind_profile_number":0,"ahs_number":0,
        "schedule_number":0,"level_number":1,"x_m":x,"y_m":y,
        "relative_height_m":h,"element_multiplier":1.0,
        "constant_wind_pressure_pa":0.0,"wind_speed_modifier":1.0,
        "wall_azimuth_deg":azimuth
    })


def ready_manifest():
    m=manifest()
    add_path(m,"path:W1",1,"window","exterior","zone:living","ambient:OUTSIDE",1,270,0,1.8,0.9)
    add_path(m,"path:W2",2,"window","exterior","zone:bedroom","ambient:OUTSIDE",2,90,5,1.7,0.9)
    add_path(m,"path:W3",3,"window","exterior","zone:study","ambient:OUTSIDE",3,180,3.8,5,0.9)
    add_path(m,"path:D1",4,"door","internal","zone:living","zone:bedroom",4,90,5,2.8,0.0)
    add_path(m,"path:D2",5,"door","internal","zone:living","zone:study",5,180,2.5,5,0.0)
    m["project_controls"]={"mode":"steady"}
    m["species_definitions"]=[{"key":"co2","name":"CO2","contam_contaminant_number":1,"molecular_weight_g_mol":44.0095}]
    return m


class ContamPrjSerializerTests(unittest.TestCase):
    def test_render_contains_three_zones_and_five_paths(self):
        text=render_minimal_prj(ready_manifest())
        self.assertIn("3 ! zones:",text)
        self.assertIn("5 ! flow paths:",text)
        self.assertIn("1 ! species:",text)
        self.assertIn("* end project file.",text)

    def test_exterior_and_internal_zone_numbers_are_rendered(self):
        text=render_minimal_prj(ready_manifest())
        self.assertIn("-1    1",text)
        self.assertIn("1    2",text)

    def test_not_ready_manifest_is_rejected(self):
        m=ready_manifest()
        del m["flow_paths"][0]["x_m"]
        with self.assertRaisesRegex(ValueError,"not ready"):
            render_minimal_prj(m)

    def test_render_is_deterministic_under_source_order_changes(self):
        m=ready_manifest()
        a=render_minimal_prj(m)
        shuffled=copy.deepcopy(m)
        shuffled["zones"].reverse()
        shuffled["flow_paths"].reverse()
        shuffled["airflow_elements"].reverse()
        b=render_minimal_prj(shuffled)
        self.assertEqual(a,b)


if __name__ == "__main__":
    unittest.main()
