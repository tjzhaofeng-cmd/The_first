import numpy as np
import pytest
import cv2
from PIL import Image
from processing.detect_rating import detect_ratings, score_fractions, star_polygon


def draw_stars(values, size=24):
    array = np.full((90, 220, 3), 255, np.uint8)
    for index, value in enumerate(values):
        x, y = 10 + index * 36, 30
        polygon = star_polygon(size) + [x, y]
        mask = np.zeros(array.shape[:2], np.uint8)
        cv2.fillPoly(mask, [polygon], 255)
        array[mask > 0] = [185, 185, 185]
        mask[:, x + round(size * value):] = 0
        array[mask > 0] = [255, 140, 0]
    return Image.fromarray(array)


@pytest.mark.parametrize('rating', [0, 0.5, 1, 2.5, 3, 4.5, 5])
def test_image_stars(rating):
    fractions = [min(1, max(0, rating - index)) for index in range(5)]
    detections = detect_ratings(draw_stars(fractions))
    assert len(detections) == 1
    assert detections[0].rating == rating


@pytest.mark.parametrize('fractions', [[1,1,0.3,0,0],[1,0,1,0,0],[1,0.5,0.5,0,0],[1,1]])
def test_abstains(fractions):
    assert score_fractions(fractions)[0] is None
