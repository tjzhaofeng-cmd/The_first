"""Local-only human review. Start from project root with python -m streamlit run."""
import json
import os
import sys
from pathlib import Path

# streamlit executes this file with its directory on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import streamlit as st
from PIL import Image, ImageDraw
from processing.pipeline import safe_image_path
from processing.storage import load_reviews, apply_corrections, save_correction
from export.export_excel import export_reviews

st.set_page_config(page_title='评论人工校对', layout='wide')
st.title('同济联合广场 · 评论人工校对')
st.caption('仅本地使用。原始截图可能含头像昵称，请勿公开分享；表单不提取这些字段。')
work = Path(st.sidebar.text_input('工作目录', os.environ.get('DIANPING_WORK', 'data/intermediate/session01')))
output = Path(st.sidebar.text_input('导出目录', 'data/output/session01'))
if not (work / 'reviews.json').exists() or not (work / 'run.json').exists():
    st.info('请先运行 OCR 处理；演示请执行 python -m scripts.make_demo。')
    st.stop()
try:
    run = json.loads((work / 'run.json').read_text(encoding='utf-8'))
    originals = load_reviews(work / 'reviews.json')
    records = apply_corrections(load_reviews(work / 'reviews.json'), work / 'corrections.json')
except (ValueError, KeyError, OSError) as error:
    st.error(str(error))
    st.stop()
if run['demo']:
    st.warning('当前为合成演示数据，不是真实评论，也不是 OCR 精度验证。')
patch_path = work / 'corrections.json'
if patch_path.exists():
    saved_ids = set(json.loads(patch_path.read_text(encoding='utf-8')).get('items', {}))
    unmatched = saved_ids - {item.review_id for item in originals}
    if unmatched:
        st.warning(f'有 {len(unmatched)} 条旧校对记录无法对应当前评论编号，未自动应用；请检查旧证据并重新校对。')
if not records:
    st.warning('没有识别到评论候选；请检查截图区域和布局，不能把 OCR 行数当评论数。')
    st.stop()
labels = {review.review_id: f'{review.review_id} | {review.review_status} | {review.review_text[:25]}'
          for review in records}
selected = st.selectbox('评论/片段', list(labels), format_func=labels.get)
review = next(item for item in records if item.review_id == selected)
original = next(item for item in originals if item.review_id == selected)
left, right = st.columns(2)
with left:
    st.subheader('来源证据')
    for evidence in review.evidence:
        try:
            image = Image.open(safe_image_path(run['session'], evidence['image'])).convert('RGB')
            draw = ImageDraw.Draw(image)
            draw.rectangle(evidence['bbox'], outline='red', width=3)
            for box in evidence.get('body_boxes', []):
                draw.rectangle(box, outline='blue', width=2)
            st.image(image, caption=evidence['image'])
        except (OSError, ValueError) as error:
            st.error(str(error))
with right:
    st.write('OCR 置信度', review.ocr_confidence)
    st.write('质量标记', ', '.join(review.flags) or '无')
    st.write('标准日期（无确定年份留空）', review.review_date_normalized)
    if 'correction_stale' in review.flags:
        st.warning('原始提取结果已变化，旧校对未自动应用，请重新检查并保存。')
    with st.form('edit_' + selected):
        options = [None] + [index / 2 for index in range(11)]
        rating = st.selectbox('评分', options, index=options.index(review.rating) if review.rating in options else 0,
                              format_func=lambda value: '不确定' if value is None else str(value))
        raw_date = st.text_input('原始日期（只有确认年份才填写年份）', review.review_date_raw)
        text = st.text_area('评论正文（核对并删除昵称/等级/图片文字）', review.review_text, height=260)
        statuses = ['complete', 'incomplete', 'needs_review']
        status = st.selectbox('完整性状态', statuses, index=statuses.index(review.review_status))
        fragment = st.checkbox('仍为未拼接片段', value=review.fragment)
        duplicate_options = [None] + [key for key in labels if key != selected]
        duplicate = st.selectbox('疑似/确认重复所对应的记录', duplicate_options,
                                 index=duplicate_options.index(review.duplicate_of) if review.duplicate_of in duplicate_options else 0,
                                 format_func=lambda value: '无' if value is None else value)
        excluded = st.checkbox('从正式导出排除（确认重复/无效项）', value=review.excluded)
        merge_options = [item.review_id for item in records if item.review_id != selected]
        patch_file = work / 'corrections.json'
        saved_merges = []
        if patch_file.exists():
            saved_merges = json.loads(patch_file.read_text(encoding='utf-8')).get('items', {}).get(
                selected, {}).get('values', {}).get('merge_ids', [])
        merge_ids = st.multiselect('人工并入以下片段（正文需在上方手动拼好；将保留全部来源）', merge_options,
                                  default=[key for key in saved_merges if key in merge_options])
        verified = st.checkbox('已逐项人工核对', value=review.manual_verified)
        submitted = st.form_submit_button('保存校对')
    if submitted:
        values = {'rating': rating, 'review_date_raw': raw_date, 'review_text': text,
                  'review_status': status, 'fragment': fragment, 'duplicate_of': duplicate,
                  'excluded': excluded, 'manual_verified': verified, 'merge_ids': merge_ids}
        try:
            save_correction(work / 'corrections.json', original, values, source_reviews=originals)
            st.success('已保存，可重新运行导出。历史修改保存在 corrections.json。')
        except (ValueError, OSError) as error:
            st.error(str(error))
if st.button('应用校对并导出 Excel / CSV / 待核对表'):
    try:
        corrected = apply_corrections(load_reviews(work / 'reviews.json'), work / 'corrections.json')
        result = export_reviews(corrected, output, demo=run['demo'])
        st.success(f"导出候选 {result['records']} 条；片段 {result['fragments']} 条另列质量表。")
        for filename in result['paths']:
            path = Path(filename)
            st.download_button('下载 ' + path.name, path.read_bytes(), file_name=path.name)
    except (ValueError, OSError) as error:
        st.error(str(error))
