import json
from pathlib import Path
import pytest
from processing.pipeline import process_session
from processing.storage import load_reviews
from scripts.make_demo import make_demo


def test_local_review_save_and_export(tmp_path, monkeypatch):
    pytest.importorskip('streamlit')
    from streamlit.testing.v1 import AppTest
    session, fixture_path=make_demo(tmp_path/'demo')
    work=tmp_path/'work'
    process_session(session,work,{},fixture=json.loads(fixture_path.read_text()))
    records=load_reviews(work/'reviews.json')
    selected=next(item for item in records if not item.fragment)
    monkeypatch.setenv('DIANPING_WORK',str(work))
    app=AppTest.from_file(str(Path('review_ui/app.py').resolve()),default_timeout=15).run()
    assert not app.exception
    app.selectbox[0].set_value(selected.review_id).run()
    assert not app.exception
    next(item for item in app.text_area if item.label.startswith('评论正文')).set_value('人工核对的合成样例内容')
    next(item for item in app.checkbox if item.label=='已逐项人工核对').set_value(True)
    next(item for item in app.button if item.label=='保存校对').click().run()
    assert not app.exception
    assert (work/'corrections.json').exists()
    next(item for item in app.text_input if item.label=='导出目录').set_value(str(tmp_path/'output'))
    next(item for item in app.button if item.label.startswith('应用校对')).click().run()
    assert not app.exception
    assert len(list((tmp_path/'output').glob('*.xlsx')))==2
    assert len(list((tmp_path/'output').glob('*.csv')))==1
