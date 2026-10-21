"""Initial five-star geometry/colour detector. Abstains on ambiguous fills."""
import cv2
import numpy as np
from processing.models import RatingDetection


def star_polygon(size=100):
    points = []
    for index in range(10):
        angle = -np.pi / 2 + index * np.pi / 5
        radius = size * (0.47 if index % 2 == 0 else 0.21)
        points.append([round(size / 2 + radius * np.cos(angle)),
                       round(size / 2 + radius * np.sin(angle))])
    return np.array(points, dtype=np.int32)


def score_fractions(fractions):
    if len(fractions) != 5:
        return None, 0.0, "not_five_stars"
    values, distances = [], []
    for fraction in fractions:
        candidates = [(abs(fraction - value), value) for value in (0.0, 0.5, 1.0)]
        distance, value = min(candidates)
        if distance > 0.16:
            return None, 0.0, "ambiguous_star_fill"
        values.append(value)
        distances.append(distance)
    if values != sorted(values, reverse=True) or values.count(0.5) > 1:
        return None, 0.0, "invalid_star_sequence"
    return sum(values), 1 - max(distances), ""


def detect_ratings(image, config=None):
    config = config or {}
    rgb = np.asarray(image.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    orange = cv2.inRange(hsv, (3, 100, 100), (32, 255, 255))
    gray = cv2.inRange(hsv, (0, 0, 100), (179, 65, 225))
    mask = cv2.bitwise_or(orange, gray)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    template = star_polygon()
    minimum, maximum = config.get("min_star_size", 8), config.get("max_star_size", 36)
    candidates = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if not (minimum <= w <= maximum and minimum <= h <= maximum and 0.65 <= w / h <= 1.5):
            continue
        shape_distance = cv2.matchShapes(contour, template, cv2.CONTOURS_MATCH_I1, 0)
        if shape_distance > config.get("shape_distance", 0.25):
            continue
        local = np.zeros(mask.shape[:2], np.uint8)
        cv2.drawContours(local, [contour], -1, 255, -1)
        area = np.count_nonzero(local)
        fraction = np.count_nonzero(cv2.bitwise_and(local, orange)) / max(area, 1)
        candidates.append((x, y, w, h, fraction))
    candidates.sort(key=lambda c: (c[1], c[0]))
    groups = []
    for candidate in candidates:
        for group in groups:
            if abs(candidate[1] - group[0][1]) <= max(3, group[0][3] * 0.3):
                group.append(candidate)
                break
        else:
            groups.append([candidate])
    detections = []
    for row in groups:
        row.sort()
        plausible = []
        for start in range(max(0, len(row) - 4)):
            group = row[start:start+5]
            if len(group) != 5:
                continue
            sizes = [c[2] for c in group]
            gaps = [group[i + 1][0] - group[i][0] for i in range(4)]
            if max(sizes) / min(sizes) > 1.5 or max(gaps) / max(min(gaps), 1) > 1.25:
                continue
            if min(gaps) < max(sizes) or max(gaps) > max(sizes) * 2.0:
                continue
            plausible.append(group)
        # Multiple possible five-star windows on one row are ambiguous.
        if len(plausible) != 1:
            continue
        group = plausible[0]
        rating, confidence, reason = score_fractions([c[4] for c in group])
        bbox = (min(c[0] for c in group), min(c[1] for c in group),
                max(c[0] + c[2] for c in group), max(c[1] + c[3] for c in group))
        detections.append(RatingDetection(bbox, rating, confidence, reason))
    return detections
