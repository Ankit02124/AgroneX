"""Spray decision and sprayer state.

A spray is requested when a 'disease' detection is above the confidence
threshold AND the drone is inside one of the spray zones AND the GPS is good
enough to trust the position. The pump runs for `spray_s` seconds per request,
and the Pi switches it off whenever the MAVLink link is lost or the GPS degrades.
"""

import json


def point_in_polygon(lat, lon, polygon):
    """Ray casting. polygon: list of (lon, lat) pairs, as in GeoJSON."""
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            x_cross = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < x_cross:
                inside = not inside
    return inside


def load_zones(path):
    """Polygons from a GeoJSON FeatureCollection (draw them in geojson.io or Mission Planner)."""
    data = json.load(open(path))
    zones = []
    for f in data.get("features", []):
        geom = f["geometry"]
        if geom["type"] == "Polygon":
            zones.append(geom["coordinates"][0])
        elif geom["type"] == "MultiPolygon":
            zones.extend(p[0] for p in geom["coordinates"])
    return zones


class Sprayer:
    def __init__(self, set_relay, spray_s=1.5, min_conf=0.5, max_hdop=2.0, zones=()):
        self.set_relay = set_relay
        self.spray_s, self.min_conf, self.max_hdop = spray_s, min_conf, max_hdop
        self.zones = list(zones)
        self.on = False
        self.off_at = 0.0

    def gps_ok(self, state):
        return state.fix_type >= 3 and state.hdop <= self.max_hdop and state.lat is not None

    def in_zone(self, state):
        return any(point_in_polygon(state.lat, state.lon, z) for z in self.zones)

    def decide(self, detections, state):
        """Returns the reason string if this frame should trigger a spray, else None."""
        disease = [d for d in detections if d.label == "disease" and d.conf >= self.min_conf]
        if not disease:
            return None
        if not self.gps_ok(state):
            return None
        if not self.in_zone(state):
            return None
        return f"disease x{len(disease)} (max {max(d.conf for d in disease):.2f})"

    def update(self, now, request, link_ok, state):
        """Call every loop. Returns 'on', 'off' or None when the relay changed."""
        if self.on and (not link_ok or not self.gps_ok(state)):
            return self._switch(False)                   # fail safe
        if request and link_ok:
            self.off_at = now + self.spray_s
            if not self.on:
                return self._switch(True)
        if self.on and now >= self.off_at:
            return self._switch(False)
        return None

    def _switch(self, on):
        self.on = on
        self.set_relay(on)
        return "on" if on else "off"
