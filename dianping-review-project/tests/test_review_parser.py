from PIL import Image
from processing.models import OCRLine, RatingDetection
from processing.detect_reviews import parse_reviews


def line(text, y, x=20, score=.97):
    return OCRLine(text, score, (x, y, x+180, y+20))


def test_same_date_two_reviews_and_exclude_headers_photo():
    lines = [line('不应提取的昵称甲', 35), line('6月28日', 80, 300), line('第一条正文内容。', 120),
             line('图片中的广告文字', 175), line('不应提取的昵称乙', 285),
             line('6月28日', 330, 300), line('第二条正文内容。展开全文', 370), line('赞 3', 410)]
    ratings = [RatingDetection((20,80,180,100),4.5,.98),RatingDetection((20,330,180,350),3,.98)]
    image = Image.new('RGB',(500,600),'white')
    records = parse_reviews(lines,ratings,image,'one.png','2026-10-21T00:00:00+00:00',1,
                            {'photo_boxes':[[0,165,240,45]]})
    assert len(records)==2
    assert records[0].review_text=='第一条正文内容。'
    assert records[0].review_date_normalized==''
    assert records[1].review_text=='第二条正文内容。'
    assert 'collapsed' in records[1].flags and records[1].review_status=='incomplete'
    assert all('昵称' not in record.review_text for record in records)
    assert records[0].evidence[0]['body_boxes']


def test_dates_alone_are_uncertain_not_verified_boundaries():
    records=parse_reviews([line('6月28日',80),line('未确定布局的正文',130)],[],
                          Image.new('RGB',(500,400),'white'),'x.png','time',1)
    assert records[0].rating is None
    assert 'boundary_uncertain' in records[0].flags
    assert records[0].review_status!='complete'


def test_unknown_screen_does_not_leak_names():
    records=parse_reviews([line('昵称或图片广告，不可当作评论',100)],[],
                          Image.new('RGB',(500,400),'white'),'x.png','time',1)
    assert records[0].review_text=='' and records[0].fragment
    assert 'layout_unrecognized' in records[0].flags
