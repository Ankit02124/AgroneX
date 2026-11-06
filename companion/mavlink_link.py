"""MAVLink connection between the Raspberry Pi and the Pixhawk (TELEM2, UART).

The Pi never changes flight parameters or flies the drone. It only reads the
vehicle state and switches the spray relay with MAV_CMD_DO_SET_RELAY, so a crash
of the Pi cannot affect flight control.
"""

import logging
import time
from dataclasses import dataclass

log = logging.getLogger("mavlink")


@dataclass
class VehicleState:
    lat: float = None
    lon: float = None
    alt_m: float = None
    fix_type: int = 0        # 3 = 3D fix
    hdop: float = 99.0
    satellites: int = 0
    armed: bool = False
    mode: str = ""
    last_heartbeat: float = 0.0


class MavlinkLink:
    def __init__(self, port="/dev/serial0", baud=57600, relay=0):
        from pymavlink import mavutil

        self.mavutil = mavutil
        self.master = mavutil.mavlink_connection(port, baud=baud)
        self.relay = relay
        self.state = VehicleState()

    def wait_heartbeat(self, timeout=30):
        msg = self.master.wait_heartbeat(timeout=timeout)
        if msg is None:
            raise TimeoutError("no heartbeat from the Pixhawk")
        self.state.last_heartbeat = time.monotonic()
        log.info("heartbeat from system %d", self.master.target_system)

    def update(self):
        """Read every waiting message and update the vehicle state."""
        while True:
            msg = self.master.recv_match(blocking=False)
            if msg is None:
                return self.state
            kind = msg.get_type()
            if kind == "HEARTBEAT" and msg.get_srcComponent() == 1:
                self.state.last_heartbeat = time.monotonic()
                self.state.armed = bool(msg.base_mode & self.mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                self.state.mode = self.mavutil.mode_string_v10(msg)
            elif kind == "GLOBAL_POSITION_INT":
                self.state.lat, self.state.lon = msg.lat / 1e7, msg.lon / 1e7
                self.state.alt_m = msg.relative_alt / 1000.0
            elif kind == "GPS_RAW_INT":
                self.state.fix_type = msg.fix_type
                self.state.satellites = msg.satellites_visible
                self.state.hdop = msg.eph / 100.0 if msg.eph != 65535 else 99.0

    def link_ok(self, timeout_s=3.0):
        return time.monotonic() - self.state.last_heartbeat < timeout_s

    def set_relay(self, on):
        self.master.mav.command_long_send(
            self.master.target_system, self.master.target_component,
            self.mavutil.mavlink.MAV_CMD_DO_SET_RELAY, 0,
            self.relay, 1 if on else 0, 0, 0, 0, 0, 0)
