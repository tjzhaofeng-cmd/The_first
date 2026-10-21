from difflib import SequenceMatcher
from processing.merge_reviews import compact
from processing.models import set_status


def mark_duplicates(reviews):
    """Conservative candidate detection. Never delete by text/date alone."""
    for index, current in enumerate(reviews):
        a = compact(current.review_text)
        if len(a) < 8 or current.fragment:
            continue
        for previous in reviews[:index]:
            b = compact(previous.review_text)
            if previous.fragment or current.review_date_raw != previous.review_date_raw:
                continue
            if current.rating != previous.rating:
                continue
            if a == b or (min(len(a), len(b)) >= 20 and SequenceMatcher(None, a, b).ratio() >= .93):
                for item in (current, previous):
                    item.flags.append('possible_duplicate')
                    set_status(item)
                # A candidate reference is not an exclusion instruction.
                current.duplicate_of = previous.review_id
                break
    return reviews
