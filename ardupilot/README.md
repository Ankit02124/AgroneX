# ArduCopter setup

Set in Mission Planner (Config -> Full Parameter List). Values are for a Pixhawk 2.4.8 with ArduCopter 4.x; check the ArduPilot docs for your firmware version.

## Frame and outputs

| parameter | value | meaning |
|---|---|---|
| `FRAME_CLASS` | 2 | hexacopter |
| `FRAME_TYPE` | 1 | X |
| `MOT_PWM_TYPE` | 6 | DShot600 |
| `SERVO9_FUNCTION` | -1 | AUX OUT 1 used as a GPIO for the pump relay |
| `RELAY1_PIN` (`RELAY_PIN` on older firmware) | 50 | relay 0 in MAVLink = AUX OUT 1 |

## Serial ports

| parameter | value | meaning |
|---|---|---|
| `SERIAL1_PROTOCOL` / `SERIAL1_BAUD` | 2 / 57 | TELEM1: SiK radio to Mission Planner, MAVLink2 at 57600 |
| `SERIAL2_PROTOCOL` / `SERIAL2_BAUD` | 2 / 57 | TELEM2: Raspberry Pi, MAVLink2 at 57600 (same as `companion/config.yaml`) |

## Battery and failsafes

| parameter | value | meaning |
|---|---|---|
| `BATT_MONITOR` | 4 | analog voltage + current from the power module |
| `BATT_LOW_VOLT` | 14.0 | 3.5 V per cell |
| `BATT_FS_LOW_ACT` | 2 | return to launch on low battery |
| `BATT_CRT_VOLT` | 13.2 | 3.3 V per cell |
| `BATT_FS_CRT_ACT` | 1 | land immediately on critical battery |
| `FS_THR_ENABLE` | 1 | return to launch when the RC signal is lost |
| `COMPASS_EXTERNAL` | 1 | use the compass on the GPS mast |
| `FENCE_ENABLE` | 1 | optional altitude and radius fence |

Calibrate the accelerometer, compass (outdoors, away from metal), radio and power module (with a multimeter) before the first flight. PIDs: start from the defaults, then run AutoTune in calm weather.

## Before every flight

1. Weather, site and airspace checked. Spray area clear of people.
2. Frame, arms, props, wiring, GPS mast and payload mounts checked by hand.
3. Transmitter on first, then the flight battery.
4. Wait for a 3D GPS fix (12+ satellites) and check the home position in Mission Planner.
5. Clear every pre-arm error. Never bypass the arming checks.
6. With props off: arm, check the controls and mode switches, switch the transmitter off to see RTL trigger, disarm.
7. Check the Pi is logging heartbeats and the pump answers a manual relay command.
8. Take off, hover for 10 s, then start the mission.

After landing: disarm, flight battery off before the transmitter, LiPo to storage charge (3.80-3.85 V per cell), flush the sprayer with clean water, download the Pixhawk and Pi logs.

LiPo: balance charger only, never unattended, never below 3.0 V per cell under load, puffed packs go to recycling.
