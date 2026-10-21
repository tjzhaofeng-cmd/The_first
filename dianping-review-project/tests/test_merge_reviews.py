import numpy as np
from PIL import Image
from processing.models import Review
from processing.merge_reviews import estimate_shift, merge_frame, stitch_text


def make(identifier, image, bbox, text, flags=None, fragment=False):
    return Review(identifier,4,'6月28日','',text,[image],.95,'incomplete','time',flags or [],
                  [{'image':image,'bbox':bbox,'sequence':1,'screen_height':500}],fragment=fragment)


def test_visual_alignment_and_reject_unrelated():
    random=np.random.default_rng(42)
    canvas=random.integers(0,256,(900,200,3),dtype=np.uint8)
    assert estimate_shift(Image.fromarray(canvas[:500]),Image.fromarray(canvas[200:700]))==200
    assert estimate_shift(Image.fromarray(canvas[:500]),Image.fromarray(canvas[400:900])) is None
    assert estimate_shift(Image.new('RGB',(200,500),'white'),Image.new('RGB',(200,500),'white')) is None


def test_continuation_preserves_sources():
    text='合成评论的第一部分，足够长的重叠测试文字'
    a=make('a','a.png',[0,200,500,500],text,['bottom_cut','year_missing'])
    b=make('b','b.png',[0,0,500,180],'足够长的重叠测试文字，以及跨屏后的新增内容',
           ['top_cut','unjoined_fragment','year_missing'],True)
    result=merge_frame([a],[b],'a.png',300)
    assert len(result)==1
    assert result[0].source_images==['a.png','b.png'] and len(result[0].evidence)==2
    assert '新增内容' in result[0].review_text
    assert 'bottom_cut' not in result[0].flags and not result[0].fragment


def test_no_visual_proof_no_auto_merge():
    a=make('a','a.png',[0,0,500,400],'同一天也可能有不同的人评价')
    b=make('b','b.png',[0,0,500,400],'同一天也可能有不同的人评价')
    assert len(merge_frame([a],[b],'a.png',None))==2


def test_conflicting_text_requires_review():
    a=make('a','a.png',[0,150,500,500],'完全不同的第一段正文文字',['bottom_cut'])
    b=make('b','b.png',[0,50,500,400],'完全不同的第二段文字无法推断')
    result=merge_frame([a],[b],'a.png',100)
    assert len(result)==2 and all('merge_uncertain' in item.flags for item in result)
    assert stitch_text('短语','短句') is None
