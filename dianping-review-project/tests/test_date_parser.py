import pytest
from processing.date_parser import parse_date


@pytest.mark.parametrize('text,normalized', [('6月28日',''),('2024年2月29日','2024-02-29'),
                                            ('2025-05-19','2025-05-19'),('2月29日','')])
def test_dates(text, normalized):
    result = parse_date(text)
    assert result.valid and result.normalized == normalized


@pytest.mark.parametrize('text', ['昨天','2025年2月29日','13月9日','6月31日','没有日期'])
def test_invalid(text):
    assert not parse_date(text).valid
