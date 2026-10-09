# HouseZero / hzconvert compatibility note

AirTrajectory does not own the HouseZero dataset and does not redefine its
sensor vocabulary.

The public third-party project `slitvinov/hzconvert` converts HouseZero's
per-table Figshare release into a wide minute-resolution `data.csv` with
canonical names such as:

- `zone/Z31/co2`
- `zone/Z31/air_temperature`
- `zone/Z31/humidity`
- `zone/Z31/window_opening/south`
- `zone/Z31/window_opening/sky`
- `outdoor/weather/air_temperature`
- `outdoor/weather/wind_speed`
- `outdoor/weather/wind_direction`
- `outdoor/weather/rain`

AirTrajectory's `housezero_hzconvert` adapter projects those public canonical
headers into the Environmental State contract while keeping window positions as
separate measured opening observations.

## Evidence boundary

This adapter is a compatibility implementation against hzconvert's public
header contract. CI uses a small fixture with those exact canonical names; it
does not claim that the full HouseZero Figshare dataset was downloaded or
validated in AirTrajectory CI.

Missing values remain `unavailable`. Fahrenheit temperature columns are
explicitly converted to Celsius. No HouseZero room/opening topology is invented
from the time-series headers.

## Why this matters

This is the first AirTrajectory adapter aimed at a genuinely independent
building-data project rather than another repository under the same owner.

The next evidence step is stronger:

1. run the adapter against a real `hzconvert/data.csv` sample;
2. bind its zone/window vocabulary to an independently sourced HouseZero
   topology;
3. emit Environmental State + opening observations over a natural-ventilation
   period;
4. compute benchmark/calibration receipts without modifying hzconvert's data
   semantics.

Only after that evidence exists should AirTrajectory propose upstream
integration or compatibility changes to hzconvert.
