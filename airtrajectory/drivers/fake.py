import time
from . import __name__ as _drivers_package
from ..physical import DriverCapabilities, PhysicalWindowDriver
from ..trajectory import ActuatorFeedback, SensorReading


def _test_binding(sensor_type: str):
    if sensor_type=="co2":
        return {
            "product_model":"TEST-CO2",
            "product_key":"test-co2-key",
            "device_id":"test-co2-device",
            "property":"airSensor.co2",
            "source_sha256":"1"*64,
            "source_bundle_sha256":"2"*64,
            "registry_sha256":"3"*64,
            "contract_sha256":"4"*64,
            "site_id":"test.single-room",
            "site_instance_id":"living.air.primary",
            "site_manifest_sha256":"8"*64,
            "site_contract_sha256":"a"*64,
        }
    return {
        "product_model":"TEST-WINDOW",
        "product_key":"test-window-key",
        "device_id":"test-window-device",
        "property":"rainSensor.rainDetect",
        "source_sha256":"5"*64,
        "source_bundle_sha256":"2"*64,
        "registry_sha256":"3"*64,
        "contract_sha256":"6"*64,
        "site_id":"test.single-room",
        "site_instance_id":"living.window.primary",
        "site_manifest_sha256":"8"*64,
        "site_contract_sha256":"a"*64,
    }


class FakePhysicalWindowDriver(PhysicalWindowDriver):
    """Synthetic contract-test driver. It is not evidence of real hardware integration."""
    def __init__(
        self,
        co2_ppm=1400,
        rain=False,
        measured_feedback=True,
        sensor_age_s=0,
        thingmodel_provenance=False,
    ):
        self.co2_ppm=co2_ppm
        self.rain=rain
        self.position=0.0
        self.measured_feedback=measured_feedback
        self.sensor_age_s=sensor_age_s
        self.thingmodel_provenance=bool(thingmodel_provenance)

    def capabilities(self):
        return DriverCapabilities("in-memory",True,self.measured_feedback,("co2","rain"))

    def read_sensors(self):
        now=time.time()-self.sensor_age_s
        co2_prov=_test_binding("co2") if self.thingmodel_provenance else {}
        rain_prov=_test_binding("rain") if self.thingmodel_provenance else {}
        return [
            SensorReading(
                "fake-co2","co2",self.co2_ppm,"ppm",now,"synthetic",
                provenance=co2_prov,
            ),
            SensorReading(
                "fake-rain","rain",float(self.rain),"bool",now,"synthetic",
                provenance=rain_prov,
            ),
        ]

    def read_position_feedback(self,opening_id):
        now=time.time()
        if self.measured_feedback:
            return ActuatorFeedback(
                opening_id,now,
                measured_position_pct=self.position,
                quality="synthetic-measured",
            )
        return ActuatorFeedback(
            opening_id,now,
            estimated_position_pct=self.position,
            quality="synthetic-estimated",
        )

    def set_position(self,opening_id,target_pct):
        self.position=target_pct
        now=time.time()
        if self.measured_feedback:
            return ActuatorFeedback(
                opening_id,now,
                measured_position_pct=self.position,
                quality="synthetic-measured",
            )
        return ActuatorFeedback(
            opening_id,now,
            estimated_position_pct=self.position,
            quality="synthetic-estimated",
        )
