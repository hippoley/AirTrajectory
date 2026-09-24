import time
from . import __name__ as _drivers_package
from ..physical import PhysicalWindowDriver
from ..trajectory import ActuatorFeedback, SensorReading

class FakePhysicalWindowDriver(PhysicalWindowDriver):
    """Synthetic contract-test driver. It is not evidence of real hardware integration."""
    def __init__(self,co2_ppm=1400,rain=False,measured_feedback=True,sensor_age_s=0):
        self.co2_ppm,self.rain,self.position,self.measured_feedback,self.sensor_age_s=co2_ppm,rain,0.0,measured_feedback,sensor_age_s
    def read_sensors(self):
        now=time.time()-self.sensor_age_s
        return [SensorReading("fake-co2","co2",self.co2_ppm,"ppm",now,"synthetic"),SensorReading("fake-rain","rain",float(self.rain),"bool",now,"synthetic")]
    def set_position(self,opening_id,target_pct):
        self.position=target_pct;now=time.time()
        if self.measured_feedback:return ActuatorFeedback(opening_id,now,measured_position_pct=self.position,quality="synthetic-measured")
        return ActuatorFeedback(opening_id,now,estimated_position_pct=self.position,quality="synthetic-estimated")
