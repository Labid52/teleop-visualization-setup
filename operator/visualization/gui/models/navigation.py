"""Display-only GNSS course estimation; never consumes IMU headings."""

import math


def distance_and_bearing(start, end):
    lat1, lon1, lat2, lon2 = map(math.radians, (*start, *end))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    distance = 6371000 * 2 * math.asin(min(1.0, math.sqrt(a)))
    bearing = math.degrees(math.atan2(math.sin(dlon) * math.cos(lat2),
        math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon))) % 360
    return distance, bearing


class CourseEstimator:
    def __init__(self):
        self.anchor = None
        self.heading = None
        self.source = "UNAVAILABLE"

    def update(self, gps):
        position = (gps.latitude, gps.longitude)
        if not gps.fix_valid or None in position:
            return self.heading
        if self.anchor is None:
            self.anchor = position
        # Retain a known course at rest. Do not turn the marker on GNSS noise.
        if gps.speed_mps is not None and gps.speed_mps < 0.6:
            return self.heading
        source = gps.heading_source.upper()
        if gps.heading_deg is not None and any(token in source for token in ("GNSS", "COG", "GPS")) and not any(token in source for token in ("IMU", "XSENS")):
            self.heading, self.source = gps.heading_deg % 360, "GNSS COURSE"
            self.anchor = position
        else:
            distance, bearing = distance_and_bearing(self.anchor, position)
            threshold = max(3.0, 2 * (gps.horizontal_accuracy_m or 0.0))
            if distance >= threshold:
                self.heading, self.source = bearing, "POSITION COURSE"
                self.anchor = position
        return self.heading
