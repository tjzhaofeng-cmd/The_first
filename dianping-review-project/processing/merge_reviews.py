"""Merge only consecutive frames with proved visual overlap and textual support."""
from difflib import SequenceMatcher
import re
import cv2
import numpy as np
from processing.models import set_status


def compact(text):
    return re.sub(r"\s+", "", text)


def stitch_text(first, second):
    a, b = compact(first), compact(second)
    if not a or not b:
        return None
    if b in a:
        return first
    if a in b:
        return second
    for length in range(min(len(a), len(b)), 7, -1):
        if a[-length:] == b[:length]:
            # Keep second text's line breaks; remove overlap by non-space characters.
            consumed = 0
            for index, char in enumerate(second):
                if not char.isspace():
                    consumed += 1
                if consumed == length:
                    return first.rstrip() + second[index + 1:]
    return None


def estimate_shift(previous, current):
    if previous.size != current.size:
        return None
    a, b = (cv2.cvtColor(np.asarray(image.convert('RGB')), cv2.COLOR_RGB2GRAY)
            for image in (previous, current))
    h, w = a.shape
    if h < 120 or w < 80:
        return None
    x0, x1 = int(w * .05), int(w * .95)
    strip_height = max(40, min(120, h // 4))
    # Try several bands: the top may be blank or occupied by a sticky toolbar.
    for band_start in [0, h // 8, h // 4, h // 3]:
        band = b[band_start:band_start+strip_height, x0:x1]
        if np.std(band) < 8:
            continue
        scores = cv2.matchTemplate(a[:, x0:x1], band, cv2.TM_CCOEFF_NORMED)
        _, best, _, location = cv2.minMaxLoc(scores)
        delta = location[1] - band_start
        if best < .97 or delta < 0 or delta > h * .8:
            continue
        overlap_a = a[delta:, x0:x1].astype(float)
        overlap_b = b[:h-delta, x0:x1].astype(float)
        fraction_close = np.mean(np.abs(overlap_a - overlap_b) < 18)
        if fraction_close >= .95:
            return delta
    return None



def merge_frame(existing, incoming, previous_image_name, shift):
    if shift is None:
        return existing + incoming
    available = []
    for review in existing:
        for evidence in review.evidence:
            if evidence['image'] == previous_image_name:
                available.append((review, evidence))
    consumed = set()
    for current in incoming:
        evidence = current.evidence[0]
        b = evidence['bbox']
        mapped = [b[0], b[1] + shift, b[2], b[3] + shift]
        matches = []
        for earlier, prior in available:
            if earlier.review_id in consumed:
                continue
            a = prior['bbox']
            if current.fragment:
                overlap = max(0, min(a[3], mapped[3]) - max(a[1], mapped[1]))
                aligned = overlap >= .7 * max(1, b[3] - b[1])
            else:
                aligned = not earlier.fragment and abs(a[1] - mapped[1]) <= 12
            dates_agree = (not current.review_date_raw or not earlier.review_date_raw or
                           current.review_date_raw == earlier.review_date_raw)
            ratings_agree = (current.rating is None or earlier.rating is None or
                             current.rating == earlier.rating)
            if aligned and dates_agree and ratings_agree:
                matches.append(earlier)
        if len(matches) != 1:
            existing.append(current)
            continue
        earlier = matches[0]
        joined = stitch_text(earlier.review_text, current.review_text)
        if joined is None:
            earlier.flags.append('merge_uncertain')
            current.flags.append('merge_uncertain')
            set_status(earlier)
            existing.append(set_status(current))
            continue
        consumed.add(earlier.review_id)
        earlier.review_text = joined
        earlier.source_images = list(dict.fromkeys(earlier.source_images + current.source_images))
        earlier.evidence.extend(current.evidence)
        earlier.ocr_confidence = min(earlier.ocr_confidence, current.ocr_confidence)
        if earlier.rating is None:
            earlier.rating = current.rating
        if not earlier.review_date_raw:
            earlier.review_date_raw = current.review_date_raw
            earlier.review_date_normalized = current.review_date_normalized
        earlier.flags = list(set(earlier.flags + current.flags))
        if 'bottom_cut' not in current.flags:
            earlier.flags = [flag for flag in earlier.flags if flag != 'bottom_cut']
        if not earlier.fragment:
            earlier.flags = [flag for flag in earlier.flags if flag not in {'unjoined_fragment', 'top_cut'}]
        set_status(earlier)
    return existing
