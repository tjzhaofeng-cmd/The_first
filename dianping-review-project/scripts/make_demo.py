"""Create visibly labelled SYNTHETIC images and fixture OCR; never real review data."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2
from capture.screenshot_utils import CaptureStore, atomic_json
from processing.detect_rating import star_polygon


def make_demo(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    session = root / 'screenshots'
    if (session / 'manifest.json').exists():
        raise ValueError('演示目录已有 manifest，请使用新的目录避免覆盖')
    paths = ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
             'C:/Windows/Fonts/msyh.ttc']
    font_path = next((path for path in paths if Path(path).exists()), None)
    font = ImageFont.truetype(font_path, 18) if font_path else ImageFont.load_default()
    image = Image.new('RGB', (500, 1100), 'white')
    draw = ImageDraw.Draw(image)
    source_lines = []
    def add(text, x, y, confidence=.98):
        draw.text((x, y), text, font=font, fill='black')
        source_lines.append({'text': text, 'confidence': confidence, 'bbox': [x, y, min(490,x+len(text)*18), y+22]})
    add('合成样例 · 非真实评论 · 禁止用于研究统计', 15, 12)
    for top, rating, date, texts in [
        (100, 4.5, '6月28日', ['这是合成样例正文甲，专门测试数据流程。', '这段话不代表任何真实用户的评价。']),
        (410, 3.0, '5月19日', ['这是合成样例正文乙，用于测试跨屏拼接。', '前后画面需要保留足够多的重叠区域。',
                               '前后画面需要保留足够多的重叠区域。续接部分。', '合成评论仍然需要人工核对其完整性。']),
        (800, 5.0, '2024年3月2日', ['第三段合成样例含折叠提示。展开全文'])]:
        add('模拟昵称（应排除）', 20, top-42)
        add(date, 290, top)
        array = np.array(image)
        for index in range(5):
            polygon = star_polygon(22) + [20+index*31,top]
            mask = np.zeros(array.shape[:2],np.uint8)
            cv2.fillPoly(mask,[polygon],255)
            array[mask>0]=[185,185,185]
            value=min(1,max(0,rating-index))
            mask[:,20+index*31+round(22*value):]=0
            array[mask>0]=[255,140,0]
        image = Image.fromarray(array)
        draw = ImageDraw.Draw(image)
        for index,text in enumerate(texts):
            add(text,20,top+45+index*40)
        draw.line((10,top+260,490,top+260),fill=(230,230,230),width=2)
    store = CaptureStore(session,[0,0,500,550])
    fixture = {}
    for offset in [0, 250, 500]:
        frame = image.crop((0,offset,500,offset+550))
        filename = store.save(frame).name
        fixture[filename] = [{**line,'bbox':[line['bbox'][0],line['bbox'][1]-offset,
                              line['bbox'][2],line['bbox'][3]-offset]} for line in source_lines
                             if line['bbox'][1]>=offset and line['bbox'][3]<=offset+550]
    store.finish('synthetic_demo')
    atomic_json(root/'ocr_fixture.json',fixture)
    atomic_json(root/'NOTICE.json',{'synthetic':True,'purpose':'软件流程测试，非真实评论，非 OCR 准确率测试'})
    return session, root/'ocr_fixture.json'


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', default='data/demo')
    args=parser.parse_args()
    session,fixture=make_demo(args.directory)
    print('仅合成数据：',session,fixture)


if __name__=='__main__':
    main()
