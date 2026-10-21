"""PaddleOCR 3 CPU adapter. Imports/models are lazy and never needed for fixtures."""
from pathlib import Path
import numpy as np
from processing.models import OCRLine


class PaddleEngine:
    def __init__(self, config=None):
        try:
            from paddleocr import PaddleOCR
        except ImportError as error:
            raise RuntimeError("请先安装 requirements-ocr.txt；模型首次下载需网络") from error
        config = config or {}
        options = dict(text_detection_model_name='PP-OCRv5_mobile_det',
                       text_recognition_model_name='PP-OCRv5_mobile_rec',
                       device='cpu', cpu_threads=2, enable_mkldnn=False,
                       use_doc_orientation_classify=False, use_doc_unwarping=False,
                       use_textline_orientation=False)
        for key in ('text_detection_model_dir', 'text_recognition_model_dir'):
            if config.get(key):
                if not Path(config[key]).is_dir():
                    raise ValueError('本地模型目录不存在：' + config[key])
                options[key] = config[key]
        try:
            self.engine = PaddleOCR(**options)
        except Exception as error:
            raise RuntimeError('OCR 初始化失败。检查官方模型下载网络，或在 config.yaml 的 processing.ocr '
                               '设置本地检测/识别模型目录；不要关闭 TLS 校验。') from error

    def recognize(self, image):
        result = []
        for page in self.engine.predict(np.asarray(image.convert("RGB"))):
            texts, scores = page["rec_texts"], page["rec_scores"]
            boxes = page.get("rec_polys", page.get("dt_polys"))
            if boxes is None or len(boxes) != len(texts) or len(scores) != len(texts):
                raise RuntimeError("OCR 返回结构不兼容，请检查 PaddleOCR 版本")
            for text, confidence, polygon in zip(texts, scores, boxes):
                polygon = np.asarray(polygon)
                result.append(OCRLine(str(text), float(confidence), (
                    float(polygon[:, 0].min()), float(polygon[:, 1].min()),
                    float(polygon[:, 0].max()), float(polygon[:, 1].max()))))
        return result


class FixtureEngine:
    """Explicit synthetic/sanitised fixture backend, not evidence of OCR accuracy."""
    def __init__(self, fixture):
        self.fixture = fixture

    def recognize_file(self, filename):
        if filename not in self.fixture:
            raise ValueError("fixture 缺少截图：" + filename)
        return [OCRLine(line["text"], line["confidence"], tuple(line["bbox"]))
                for line in self.fixture[filename]]
