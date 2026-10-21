from processing.models import Review
from processing.deduplicate import mark_duplicates


def record(identifier, text, date='6月28日'):
    return Review(identifier,4,date,'',text,[identifier+'.png'],.96,'needs_review','time')


def test_same_date_different_text_not_duplicate():
    a,b=record('a','这是第一位用户不同的完整正文'),record('b','这是第二位用户不同的完整正文')
    mark_duplicates([a,b])
    assert not a.flags and not b.flags


def test_duplicate_marked_but_not_deleted():
    records=[record('a','完全相同的较长合成评论内容'),record('b','完全相同的较长合成评论内容')]
    assert len(mark_duplicates(records))==2
    assert all('possible_duplicate' in item.flags for item in records)
    assert records[1].duplicate_of=='a' and not records[1].excluded


def test_very_short_text_not_identity():
    records=[record('a','不错'),record('b','不错')]
    mark_duplicates(records)
    assert not records[1].flags
