import re
from datetime import date
from dataclasses import dataclass

DATE_PATTERN = re.compile(r"(?<!\d)(?:(\d{4})\s*[年./-]\s*)?(\d{1,2})\s*[月./-]\s*(\d{1,2})(?:日)?(?!\d)")


@dataclass
class ParsedDate:
    raw: str
    normalized: str
    valid: bool
    reason: str


def parse_date(text):
    match = DATE_PATTERN.search(text)
    if not match:
        return ParsedDate(text.strip(), "", False, "date_unrecognized")
    year, month, day = match.groups()
    try:
        value = date(int(year) if year else 2000, int(month), int(day))
    except ValueError:
        return ParsedDate(match.group(), "", False, "date_invalid")
    return ParsedDate(match.group(), value.isoformat() if year else "", True,
                      "" if year else "year_missing")
