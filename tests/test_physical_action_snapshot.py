import unittest

from airtrajectory.physical_action_snapshot import capture_post_action_snapshot
from airtrajectory.trajectory import SensorReading


class SnapshotDriver:
    def __init__(self, rows):
        self.rows=list(rows)
        self.index=0

    def read_sensors(self):
        row=self.rows[min(self.index,len(self.rows)-1)]
        self.index+=1
        return row


class ReplannedActionSnapshotTests(unittest.TestCase):
    def test_waits_for_both_co2_and_rain_after_feedback(self):
        clock={"now":0.0}
        def now():
            value=clock["now"]
            clock["now"]+=1.0
            return value
        driver=SnapshotDriver([
            [
                SensorReading("co2","co2",1300.0,"ppm",10.0,"measured",{}),
                SensorReading("rain","rain",0.0,"bool",12.0,"measured",{}),
            ],
            [
                SensorReading("co2","co2",1290.0,"ppm",12.0,"measured",{}),
                SensorReading("rain","rain",0.0,"bool",12.0,"measured",{}),
            ],
        ])
        out=capture_post_action_snapshot(
            driver=driver,
            after_timestamp=11.0,
            timeout_s=10,
            poll_interval_s=0,
            sleep_fn=lambda _:None,
            clock_fn=now,
        )
        self.assertEqual(out["co2_ppm"],1290.0)
        self.assertFalse(out["rain"])
        self.assertTrue(out["fresh_after_action"])
        self.assertEqual(len(out["snapshot_sha256"]),64)

    def test_times_out_when_co2_remains_stale(self):
        clock={"now":0.0}
        def now():
            value=clock["now"]
            clock["now"]+=1.0
            return value
        driver=SnapshotDriver([[
            SensorReading("co2","co2",1300.0,"ppm",10.0,"measured",{}),
            SensorReading("rain","rain",0.0,"bool",12.0,"measured",{}),
        ]])
        with self.assertRaisesRegex(RuntimeError,"post-action sensor timeout"):
            capture_post_action_snapshot(
                driver=driver,
                after_timestamp=11.0,
                timeout_s=2,
                poll_interval_s=0,
                sleep_fn=lambda _:None,
                clock_fn=now,
            )


if __name__=="__main__":
    unittest.main()
