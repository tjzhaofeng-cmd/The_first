"""Controller tests with mocked desktop only; not Windows/WeChat acceptance tests."""
import json
import sys
import types
from PIL import Image
from capture import capture_windows


def test_manual_controller_batch_and_stop(tmp_path, monkeypatch):
    class FailSafe(Exception):
        pass
    gui=types.SimpleNamespace(FailSafeException=FailSafe, onScreen=lambda *args:True,
                              screenshot=lambda **kwargs:Image.new('RGB',(100,100),'white'))
    monkeypatch.setitem(sys.modules,'pyautogui',gui)
    monkeypatch.setattr(sys,'platform','win32')
    monkeypatch.setattr(capture_windows,'select_region',lambda gui:[0,0,100,100])
    config=tmp_path/'config.yaml'
    config.write_text('capture:\n  max_screenshots: 10\n  delay_seconds: 5\n  scroll_clicks: -2\n  unchanged_limit: 1\n  unchanged_similarity: 0.997\n')
    directory=tmp_path/'session'
    monkeypatch.setattr(sys,'argv',['capture','--directory',str(directory),'--config',str(config)])
    answers=iter(['START','',''])
    monkeypatch.setattr('builtins.input',lambda prompt='':next(answers))
    capture_windows.main()
    manifest=json.loads((directory/'manifest.json').read_text())
    assert len(manifest['screenshots'])==2
    assert manifest['batches'][-1]['stop_reason']=='unchanged'


def test_region_selection_uses_mouse_coordinates(monkeypatch):
    answers=iter([(10,20),(210,320)])
    gui=types.SimpleNamespace(position=lambda:next(answers))
    monkeypatch.setattr('builtins.input',lambda prompt='':'')
    assert capture_windows.select_region(gui)==[10,20,200,300]
