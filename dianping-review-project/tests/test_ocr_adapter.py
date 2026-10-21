import sys
import types
import numpy as np
from PIL import Image
from processing.ocr_engine import PaddleEngine


def test_paddle3_adapter_contract(monkeypatch):
    # Adapter contract test only; not a real model accuracy test.
    class FakePaddle:
        def __init__(self, **options):
            assert options['device']=='cpu'
            assert not options['use_doc_unwarping']
        def predict(self, image):
            assert isinstance(image,np.ndarray)
            return [{'rec_texts':['合成正文'], 'rec_scores':[.93],
                     'rec_polys':np.array([[[10,20],[80,20],[80,40],[10,40]]])}]
    monkeypatch.setitem(sys.modules,'paddleocr',types.SimpleNamespace(PaddleOCR=FakePaddle))
    lines=PaddleEngine().recognize(Image.new('RGB',(100,100),'white'))
    assert len(lines)==1 and lines[0].text=='合成正文'
    assert lines[0].bbox==(10,20,80,40) and lines[0].confidence==.93
