import json
import pytest
from processing.models import Review
from processing.storage import save_correction, apply_corrections


def record(identifier='a'):
    return Review(identifier,None,'6月28日','','旧的合成文字',['a.png'],.8,'needs_review','time',['rating_uncertain'])


def values(**kwargs):
    return {'rating':4.5,'review_date_raw':'6月28日','review_text':'人工核对过的合成文字',
            'review_status':'complete','excluded':False,'manual_verified':True,'fragment':False,**kwargs}


def test_roundtrip_no_invented_year_and_audit(tmp_path):
    path=tmp_path/'corrections.json'
    save_correction(path,record(),values())
    save_correction(path,record(),values(review_text='第二次修改'))
    result=apply_corrections([record()],path)[0]
    assert result.review_text=='第二次修改' and result.rating==4.5
    assert result.review_date_normalized=='' and result.manual_verified
    assert len(json.loads(path.read_text())['history'])==2


def test_stale_correction_not_applied(tmp_path):
    path=tmp_path/'corrections.json'
    save_correction(path,record(),values())
    changed=record()
    changed.review_text='重新 OCR 得到了不同的文本'
    result=apply_corrections([changed],path)[0]
    assert result.review_text==changed.review_text and 'correction_stale' in result.flags


@pytest.mark.parametrize('patch',[{'rating':5.5},{'rating':.3},{'review_date_raw':'昨天'},
                                  {'review_text':''},{'fragment':True}])
def test_invalid_manual_confirmation(tmp_path,patch):
    with pytest.raises(ValueError):
        save_correction(tmp_path/'x.json',record(),values(**patch))


def test_manual_merge_keeps_evidence(tmp_path):
    path=tmp_path/'corrections.json'
    a,b=record('a'),record('b')
    b.source_images=['b.png']
    b.fragment=True
    save_correction(path,a,values(merge_ids=['b']),source_reviews=[a,b])
    result=apply_corrections([a,b],path)
    assert result[0].source_images==['a.png','b.png']
    assert result[1].excluded and result[1].duplicate_of=='a'


def test_changed_merge_evidence_invalidates_manual_patch(tmp_path):
    path=tmp_path/'corrections.json'
    a,b=record('a'),record('b')
    save_correction(path,a,values(merge_ids=['b']),source_reviews=[a,b])
    b.review_text='子片段重新识别后发生变化'
    result=apply_corrections([a,b],path)
    assert 'correction_stale' in result[0].flags
    assert not result[1].excluded


def test_unknown_manual_merge_rejected(tmp_path):
    with pytest.raises(ValueError,match='来源'):
        save_correction(tmp_path/'x.json',record(),values(merge_ids=['missing']))


def test_repeated_manual_merge_rejected(tmp_path):
    with pytest.raises(ValueError,match='重复'):
        save_correction(tmp_path/'x.json',record(),values(merge_ids=['b','b']))
