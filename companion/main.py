"""AgroneX companion computer loop (Raspberry Pi 4).

camera -> YOLOv8n -> disease above threshold? -> inside spray zone with a good
GPS fix? -> MAV_CMD_DO_SET_RELAY to the Pixhawk -> pump on for a short burst.

Run:  python3 main.py --config config.yaml
"""

import argparse
import csv
import logging
import time
from pathlib import Path

import cv2
import yaml

from detector import DiseaseDetector
from mavlink_link import MavlinkLink
from spraying import Sprayer, load_zones

log = logging.getLogger("agronex")


def open_camera(cfg):
    cam = cv2.VideoCapture(cfg["device"])
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, cfg["width"])
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg["height"])
    if not cam.isOpened():
        raise RuntimeError(f"camera {cfg['device']} not found")
    return cam


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    m = cfg["model"]
    detector = DiseaseDetector(m["path"], m["names"], m["backend"], m["imgsz"], m["conf"], m["iou"])
    link = MavlinkLink(cfg["mavlink"]["port"], cfg["mavlink"]["baud"], cfg["spray"]["relay"])
    link.wait_heartbeat()
    s = cfg["spray"]
    sprayer = Sprayer(link.set_relay, s["duration_s"], m["conf"], s["max_hdop"], load_zones(s["zones"]))
    link.set_relay(False)
    camera = open_camera(cfg["camera"])

    logdir = Path(cfg["log_dir"])
    logdir.mkdir(parents=True, exist_ok=True)
    logfile = open(logdir / time.strftime("flight_%Y%m%d_%H%M%S.csv"), "w", newline="")
    writer = csv.writer(logfile)
    writer.writerow(["time", "lat", "lon", "alt_m", "hdop", "mode", "detections", "max_conf", "event"])

    active_modes = set(cfg["active_modes"])
    try:
        while True:
            state = link.update()
            now = time.monotonic()
            ok = link.link_ok()
            request, event, dets = None, "", []

            if ok and state.armed and state.mode in active_modes:
                grabbed, frame = camera.read()
                if grabbed:
                    t0 = time.perf_counter()
                    dets = detector.detect(frame)
                    infer_ms = (time.perf_counter() - t0) * 1000
                    request = sprayer.decide(dets, state)
                    if request:
                        event = request
                        cv2.imwrite(str(logdir / f"spray_{int(time.time())}.jpg"), frame)
                    log.debug("%d detections in %.0f ms", len(dets), infer_ms)

            change = sprayer.update(now, bool(request), ok, state)
            if change:
                event = f"{event} pump {change}".strip()
                log.info("pump %s at %.6f, %.6f", change, state.lat or 0, state.lon or 0)
            if dets or event:
                writer.writerow([time.strftime("%H:%M:%S"), state.lat, state.lon, state.alt_m, state.hdop, state.mode,
                                 len(dets), max((d.conf for d in dets), default=""), event])
                logfile.flush()
            if not ok:
                time.sleep(0.2)          # link lost: pump already forced off, wait for heartbeats
    finally:
        link.set_relay(False)
        camera.release()
        logfile.close()


if __name__ == "__main__":
    main()
