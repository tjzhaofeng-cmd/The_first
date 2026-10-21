"""Privacy-minimised structured records; raw OCR lines are never persisted."""
from dataclasses import asdict, dataclass, field
import hashlib
from copy import deepcopy


@dataclass
class OCRLine:
    text: str
    confidence: float
    bbox: tuple[float, float, float, float]


@dataclass
class RatingDetection:
    bbox: tuple[int, int, int, int]
    rating: float | None
    confidence: float
    reason: str = ""


@dataclass
class Review:
    review_id: str
    rating: float | None
    review_date_raw: str
    review_date_normalized: str
    review_text: str
    source_images: list[str]
    ocr_confidence: float
    review_status: str
    collected_at: str
    flags: list[str] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    duplicate_of: str | None = None
    excluded: bool = False
    manual_verified: bool = False
    # Provisional fragments must not be counted as identified reviews.
    fragment: bool = False

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        return cls(**deepcopy(value))


def stable_id(image, bbox):
    return "r_" + hashlib.sha256(f"{image}:{tuple(bbox)}".encode()).hexdigest()[:16]


def set_status(review):
    review.flags = sorted(set(review.flags))
    if {"collapsed", "bottom_cut", "top_cut", "unjoined_fragment"} & set(review.flags):
        review.review_status = "incomplete"
    elif review.flags:
        review.review_status = "needs_review"
    else:
        review.review_status = "complete"
    return review
