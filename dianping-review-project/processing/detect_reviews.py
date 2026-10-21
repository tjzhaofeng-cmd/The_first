"""Conservative layout heuristics; no username extraction or persistence."""
import re
import cv2
import numpy as np
from processing.date_parser import parse_date
from processing.models import Review, stable_id, set_status

UI_WORDS = re.compile(r"^(?:展开全文|全文|收起|赞(?:\s*\d+)?|回复(?:\s*\d+)?|商家回应|优质点评|VIP\d*|LV\d*|写点评|全部评价|有图|最新|默认排序)$", re.I)


def intersects(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def photo_regions(image):
    """Heuristic high-texture rectangular blocks; imperfect, so flag when used."""
    array = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(array, 60, 160)
    mask = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    width, height = image.size
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w < 60 or h < 60 or w * h > width * height * 0.65:
            continue
        density = np.count_nonzero(edges[y:y+h, x:x+w]) / (w * h)
        if density > 0.15 and 0.5 < w / h < 2.5:
            boxes.append((x, y, x+w, y+h))
    return boxes


def parse_reviews(lines, ratings, image, filename, collected_at, sequence, config=None):
    config = config or {}
    width, height = image.size
    lines = sorted(lines, key=lambda line: (line.bbox[1], line.bbox[0]))
    automatic_photos = photo_regions(image)
    explicit_photos = [(x, y, x+w, y+h) for x, y, w, h in config.get("photo_boxes", [])]
    photos = automatic_photos + explicit_photos
    # A date is a header only when its line is date-like and spatially near stars.
    dates = []
    for line in lines:
        parsed = parse_date(line.text)
        if parsed.valid and len(line.text.strip()) <= 24:
            dates.append((line, parsed))
        elif re.fullmatch(r"(?:今天|昨天|前天|\d+天前)(?:.*)?", line.text.strip()):
            dates.append((line, parsed))
    headers = []
    used = set()
    gap = config.get("header_gap", 100)
    for rating in ratings:
        near = [(abs((line.bbox[1]+line.bbox[3])/2 - (rating.bbox[1]+rating.bbox[3])/2), index)
                for index, (line, _) in enumerate(dates)
                if index not in used and abs(line.bbox[1] - rating.bbox[1]) <= gap]
        index = min(near)[1] if near else None
        if index is not None:
            used.add(index)
        headers.append((rating, dates[index] if index is not None else None))
    # Dates alone are not accepted as established comment boundaries.
    # Keep an unpaired date as an uncertain candidate, never claim it is complete.
    for index, entry in enumerate(dates):
        if index not in used:
            headers.append((None, entry))
    def bounds(header):
        rating, entry = header
        boxes = ([rating.bbox] if rating else []) + ([entry[0].bbox] if entry else [])
        return min(b[1] for b in boxes), max(b[3] for b in boxes)
    headers.sort(key=lambda header: bounds(header)[0])
    guard = config.get("header_guard", 64)
    regions = []
    if not headers:
        # Without any trustworthy header, arbitrary OCR may be a nickname/photo/UI.
        # Preserve only an evidence placeholder, never dump the screen into review_text.
        review = Review(stable_id(filename, [0, 0, width, height]), None, '', '', '',
                        [filename], 0.0, 'needs_review', collected_at,
                        ['layout_unrecognized', 'unjoined_fragment', 'rating_uncertain', 'date_unrecognized'],
                        [{'image': filename, 'bbox': [0, 0, width, height], 'sequence': sequence,
                          'body_boxes': [], 'screen_height': height}], fragment=True)
        return [set_status(review)]
    else:
        # The head area of the next card contains an avatar/nickname; leave a margin.
        first_top = bounds(headers[0])[0]
        prefix_lines = [line for line in lines if line.bbox[3] < first_top - guard]
        if prefix_lines:
            regions.append((None, 0, 0, first_top - guard, True))
        for index, header in enumerate(headers):
            top, body_top = bounds(header)
            bottom = bounds(headers[index+1])[0] - guard if index + 1 < len(headers) else height
            regions.append((header, max(0, top-45), body_top+3, max(body_top+4, bottom), False))
    result = []
    for header, top, body_top, bottom, fragment in regions:
        chosen, flags = [], ["unjoined_fragment", "top_cut"] if fragment else []
        if not config.get('layout_verified', False):
            flags.append('layout_uncalibrated')
        if not header:
            rating, entry = None, None
        else:
            rating, entry = header
        for line in lines:
            safe_bottom = min(bottom, height - guard) if bottom >= height - 20 else bottom
            if not (line.bbox[1] >= body_top and line.bbox[3] <= safe_bottom):
                continue
            if any(intersects(line.bbox, box) for box in photos):
                flags.append("photo_text_excluded")
                continue
            text = line.text.strip()
            if text.startswith(('商家回应', '商家回复')):
                flags.append('merchant_reply_excluded')
                break
            if any(word in text for word in ["展开全文", "展开更多"]):
                flags.append("collapsed")
                text = text.replace("展开全文", "").replace("展开更多", "").strip()
            if not text or UI_WORDS.fullmatch(text) or re.fullmatch(r'(?:评分|打分)?\s*[0-5](?:\.[05])?\s*(?:分|星)', text):
                continue
            if parse_date(text).valid and len(text) <= 24:
                continue
            chosen.append((line, text))
        if not chosen and fragment:
            continue
        if not chosen:
            flags.append("body_missing")
        elif len(chosen) < config.get('min_body_lines', 1):
            flags.append('body_weak')
        if not rating or rating.rating is None:
            flags.append("rating_uncertain")
        if not rating or not entry:
            flags.append("boundary_uncertain")
        parsed = entry[1] if entry else None
        if not parsed or not parsed.valid:
            flags.append("date_unrecognized")
        elif parsed.reason:
            flags.append(parsed.reason)
        # Last visible card may continue below the screenshot. Never assume completion.
        if bottom >= height - config.get("body_bottom_margin", 20):
            flags.append("bottom_cut")
        confidence_scores = [line.confidence for line, _ in chosen]
        if entry:
            confidence_scores.append(entry[0].confidence)
        confidence = min(confidence_scores, default=0.0)
        if confidence < config.get("min_ocr_confidence", 0.85):
            flags.append("low_ocr_confidence")
        bbox = [0, int(top), width, int(bottom)]
        evidence = {"image": filename, "bbox": bbox, "sequence": sequence,
                    "body_boxes": [list(line.bbox) for line, _ in chosen],
                    "date_bbox": list(entry[0].bbox) if entry else None,
                    "rating_bbox": list(rating.bbox) if rating else None,
                    "rating_confidence": float(rating.confidence) if rating else 0,
                    "rating_reason": rating.reason if rating else 'not_detected',
                    "screen_height": height}
        review = Review(stable_id(filename, bbox), rating.rating if rating else None,
                        parsed.raw if parsed else "", parsed.normalized if parsed else "",
                        "\n".join(text for _, text in chosen), [filename], confidence,
                        "needs_review", collected_at, flags, [evidence], fragment=fragment)
        result.append(set_status(review))
    return result
