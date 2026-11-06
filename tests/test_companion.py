import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))

from detector import Detection, letterbox, nms, postprocess  # noqa: E402
from mavlink_link import VehicleState  # noqa: E402
from spraying import Sprayer, load_zones, point_in_polygon  # noqa: E402

FIELD = [(85.818, 20.295), (85.8195, 20.295), (85.8195, 20.2962), (85.818, 20.2962), (85.818, 20.295)]


def good_state(lat=20.2955, lon=85.8188):
    return VehicleState(lat=lat, lon=lon, alt_m=4.0, fix_type=3, hdop=0.9, satellites=14, armed=True, mode="AUTO")


def disease(conf=0.8):
    return [Detection(0, 0, 10, 10, conf, "disease")]


class Relay:
    def __init__(self):
        self.calls = []

    def __call__(self, on):
        self.calls.append(on)


def test_point_in_polygon():
    assert point_in_polygon(20.2955, 85.8188, FIELD)
    assert not point_in_polygon(20.2970, 85.8188, FIELD)


def test_example_zone_file_loads():
    zones = load_zones(Path(__file__).resolve().parents[1] / "companion" / "spray_zones.geojson")
    assert len(zones) == 1 and point_in_polygon(20.2955, 85.8188, zones[0])


def test_spray_only_for_confident_disease_inside_zone():
    s = Sprayer(Relay(), zones=[FIELD], min_conf=0.5)
    assert s.decide(disease(0.8), good_state())
    assert not s.decide(disease(0.3), good_state())                       # low confidence
    assert not s.decide([Detection(0, 0, 1, 1, 0.9, "healthy")], good_state())
    assert not s.decide(disease(), good_state(lat=20.30))                 # outside the field


def test_no_spray_with_poor_gps():
    s = Sprayer(Relay(), zones=[FIELD])
    st = good_state()
    st.hdop = 3.5
    assert not s.decide(disease(), st)
    st.hdop, st.fix_type = 0.9, 2
    assert not s.decide(disease(), st)


def test_pump_burst_and_extension():
    relay = Relay()
    s = Sprayer(relay, spray_s=1.5, zones=[FIELD])
    st = good_state()
    assert s.update(0.0, True, True, st) == "on"
    assert s.update(1.0, True, True, st) is None        # still disease: burst extended to 2.5 s
    assert s.update(2.0, False, True, st) is None
    assert s.update(2.6, False, True, st) == "off"
    assert relay.calls == [True, False]


def test_pump_off_when_link_or_gps_lost():
    relay = Relay()
    s = Sprayer(relay, zones=[FIELD])
    st = good_state()
    s.update(0.0, True, True, st)
    assert s.update(0.1, False, False, st) == "off"      # MAVLink heartbeat lost
    s.update(0.2, True, True, st)
    st.fix_type = 0
    assert s.update(0.3, False, True, st) == "off"       # GPS lost


def test_nms():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], np.float32)
    assert sorted(nms(boxes, np.array([0.9, 0.8, 0.7]), 0.5)) == [0, 2]


def test_postprocess_normalised_tflite_output():
    frame = np.zeros((1080, 1920, 3), np.uint8)
    _, r, dx, dy = letterbox(frame, 640)
    pred = np.zeros((6, 2), np.float32)                  # 4 box values + 2 classes, 2 candidates
    pred[:4, 0] = [0.5, 0.5, 0.1, 0.1]                   # centre of the input, normalised
    pred[5, 0] = 0.9                                     # class 1 = disease
    pred[4, 1] = 0.2                                     # below threshold
    out = postprocess(pred, ["healthy", "disease"], 640, r, dx, dy, 0.5, 0.5, frame.shape)
    assert len(out) == 1 and out[0].label == "disease"
    assert abs((out[0].x1 + out[0].x2) / 2 - 960) < 1 and abs((out[0].y1 + out[0].y2) / 2 - 540) < 1
