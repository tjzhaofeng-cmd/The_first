import json
from PIL import Image
import pytest
from capture.screenshot_utils import CaptureStore, similarity


def test_resume_no_overwrite(tmp_path):
    region = [10, 20, 300, 400]
    first = CaptureStore(tmp_path, region)
    one = first.save(Image.new('RGB', (300, 400), 'white'))
    first.finish('batch_limit')
    original = one.read_bytes()
    second = CaptureStore(tmp_path, region)
    two = second.save(Image.new('RGB', (300, 400), 'black'))
    second.finish('user_stop')
    manifest = json.loads((tmp_path / 'manifest.json').read_text())
    assert one != two and one.read_bytes() == original
    assert [item['sequence'] for item in manifest['screenshots']] == [1, 2]
    assert len(manifest['batches']) == 2
    with pytest.raises(ValueError, match='区域'):
        CaptureStore(tmp_path, [0, 0, 300, 400])


def test_recovers_orphan_and_detects_missing(tmp_path):
    store = CaptureStore(tmp_path, [0, 0, 20, 20])
    store.finish('test')
    Image.new('RGB', (20, 20)).save(tmp_path / 'capture_000001_orphan.png')
    recovered = CaptureStore(tmp_path, [0, 0, 20, 20])
    assert recovered.data['screenshots'][0]['recovered']
    recovered.finish('test')
    (tmp_path / 'capture_000001_orphan.png').unlink()
    with pytest.raises(ValueError, match='缺失'):
        CaptureStore(tmp_path, [0, 0, 20, 20])


def test_unchanged():
    image = Image.new('RGB', (100, 100), 'white')
    assert similarity(image, image) == 1
    assert similarity(image, Image.new('RGB', (100, 100), 'black')) == 0


def test_concurrent_capture_rejected_and_lock_released(tmp_path):
    from filelock import Timeout
    store=CaptureStore(tmp_path,[0,0,10,10])
    with pytest.raises(Timeout):
        CaptureStore(tmp_path,[0,0,10,10])
    store.finish('test')
    resumed=CaptureStore(tmp_path,[0,0,10,10])
    resumed.finish('test')
