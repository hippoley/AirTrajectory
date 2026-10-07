import unittest
from dataclasses import dataclass

from airtrajectory.physical_terminal_snapshot import (
    capture_post_closeout_snapshot,
)


@dataclass
class Reading:
    sensor_id: str
    sensor_type: str
    value: float
    unit: str
    timestamp: float
    quality: str
    provenance: dict


class Driver:
    def __init__(self, rows):
        self.rows=list(rows)
        self.calls=0
    def read_sensors(self):
        row=self.rows[min(self.calls,len(self.rows)-1)]
        self.calls+=1
        return row


class PhysicalTerminalSnapshotTests(unittest.TestCase):
    def test_waits_until_both_required_sensors_are_newer_than_closeout(self):
        driver=Driver([
            [
                Reading("c","co2",1200,"ppm",10.0,"measured",{}),
                Reading("r","rain",0,"bool",10.0,"measured",{}),
            ],
            [
                Reading("c","co2",1180,"ppm",12.0,"measured",{}),
                Reading("r","rain",0,"bool",12.0,"measured",{}),
            ],
        ])
        clock={"v":0.0}
        def now():
            clock["v"]+=0.1
            return clock["v"]
        out=capture_post_closeout_snapshot(
            driver=driver,
            after_timestamp=11.0,
            timeout_s=2,
            poll_interval_s=0,
            sleep_fn=lambda _:None,
            clock_fn=now,
        )
        self.assertEqual(out["co2_ppm"],1180.0)
        self.assertFalse(out["rain"])
        self.assertEqual(out["co2_timestamp"],12.0)
        self.assertTrue(out["fresh_after_closeout"])
        self.assertEqual(len(out["snapshot_sha256"]),64)

    def test_times_out_when_co2_never_advances(self):
        driver=Driver([[
            Reading("c","co2",1200,"ppm",10.0,"measured",{}),
            Reading("r","rain",0,"bool",12.0,"measured",{}),
        ]])
        ticks=iter([0.0,0.1,0.2,0.3,0.4,0.5,1.0])
        with self.assertRaisesRegex(RuntimeError,"co2"):
            capture_post_closeout_snapshot(
                driver=driver,
                after_timestamp=11.0,
                timeout_s=0.25,
                poll_interval_s=0,
                sleep_fn=lambda _:None,
                clock_fn=lambda:next(ticks),
            )

    def test_rejects_missing_required_sensor(self):
        driver=Driver([[
            Reading("c","co2",1200,"ppm",12.0,"measured",{}),
        ]])
        ticks=iter([0.0,0.1,0.2,0.3,0.4,0.5,1.0])
        with self.assertRaisesRegex(RuntimeError,"CO2/rain"):
            capture_post_closeout_snapshot(
                driver=driver,
                after_timestamp=11.0,
                timeout_s=0.25,
                poll_interval_s=0,
                sleep_fn=lambda _:None,
                clock_fn=lambda:next(ticks),
            )


if __name__=="__main__":
    unittest.main()
