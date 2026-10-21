import json
import pytest
from processing.pipeline import process_session, read_manifest
from processing.ocr_engine import FixtureEngine
from processing.storage import load_reviews
from scripts.make_demo import make_demo
from export.export_excel import export_reviews


def test_end_to_end_resume_and_evidence(tmp_path, monkeypatch):
    session, fixture_path = make_demo(tmp_path / 'demo')
    fixture = json.loads(fixture_path.read_text())
    work = tmp_path / 'work'
    original = FixtureEngine.recognize_file
    calls = []
    def fail_second(self, name):
        calls.append(name)
        if len(calls) == 2:
            raise RuntimeError('模拟中断')
        return original(self, name)
    monkeypatch.setattr(FixtureEngine, 'recognize_file', fail_second)
    with pytest.raises(RuntimeError, match='模拟中断'):
        process_session(session, work, {}, fixture=fixture)
    assert len(json.loads((work/'checkpoint.json').read_text())['pages']) == 1
    monkeypatch.setattr(FixtureEngine, 'recognize_file', original)
    result = process_session(session, work, {}, fixture=fixture)
    assert result['recomputed_pages'] == 2
    assert result['screenshots'] == 3 and result['review_candidates'] == 3
    records = load_reviews(work/'reviews.json')
    assert any(len(record.source_images) >= 2 for record in records)
    assert all('模拟昵称' not in record.review_text for record in records)
    before = (work/'reviews.json').read_bytes()
    result = process_session(session, work, {}, fixture=fixture)
    assert result['recomputed_pages'] == 0
    assert (work/'reviews.json').read_bytes() == before
    exported = export_reviews(records, tmp_path/'output', demo=True)
    assert exported['records'] == 3
    # A calibration setting change invalidates the old parsed-page cache.
    changed = process_session(session, work, {'min_ocr_confidence':.99}, fixture=fixture)
    assert changed['recomputed_pages'] == 3


def test_bad_manifest_hash_and_path(tmp_path):
    session, _ = make_demo(tmp_path/'demo')
    manifest = json.loads((session/'manifest.json').read_text())
    manifest['screenshots'][0]['file'] = '../escape.png'
    (session/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='路径'):
        read_manifest(session)


def test_tampered_image_rejected(tmp_path):
    session,_=make_demo(tmp_path/'demo')
    image=next(session.glob('*.png'))
    image.write_bytes(image.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='校验和'):
        read_manifest(session)
