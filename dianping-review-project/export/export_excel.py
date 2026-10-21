"""Export review rows and a separate evidence/quality workbook."""
import json
import os
import tempfile
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook

FIELDS = ['review_id', 'rating', 'review_date_raw', 'review_date_normalized',
          'review_text', 'source_images', 'ocr_confidence', 'review_status', 'collected_at']
NAME = '同济联合广场'


def safe_cell(value):
    # Protect CSV consumers from spreadsheet formula injection without changing originals.
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def row_for(review):
    row = {key: getattr(review, key) for key in FIELDS}
    row['source_images'] = json.dumps(review.source_images, ensure_ascii=False)
    return row


def write_excel(frame, path):
    frame.to_excel(path, index=False, engine='openpyxl')
    workbook = load_workbook(path)
    sheet = workbook.active
    sheet.freeze_panes = 'A2'
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = 24
        for cell in column:
            # Excel strings are strings even when starting with '='; preserve text value.
            if isinstance(cell.value, str):
                cell.data_type = 's'
    workbook.save(path)


def export_reviews(reviews, directory, demo=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    prefix = '演示_非真实数据_' if demo else ''
    stem = prefix + NAME
    active = [review for review in reviews if not review.excluded and not review.fragment]
    frame = pd.DataFrame([row_for(review) for review in active], columns=FIELDS)
    quality = []
    for review in reviews:
        if review.review_status != 'complete' or (set(review.flags) - {'manual_verified'}) or review.excluded or review.fragment:
            quality.append({**row_for(review), 'quality_flags': ';'.join(review.flags),
                            'duplicate_of': review.duplicate_of, 'excluded': review.excluded,
                            'is_fragment': review.fragment, 'evidence': json.dumps(review.evidence, ensure_ascii=False)})
    quality_frame = pd.DataFrame(quality, columns=FIELDS + ['quality_flags', 'duplicate_of', 'excluded', 'is_fragment', 'evidence'])
    paths = [directory / (stem + '_大众点评评论.csv'), directory / (stem + '_大众点评评论.xlsx'),
             directory / (stem + '_待人工核对.xlsx')]
    # Build all workbooks in a temporary directory before replacing current exports.
    with tempfile.TemporaryDirectory(dir=directory) as staging:
        temp = Path(staging)
        csv_frame = frame.map(safe_cell)
        csv_frame.to_csv(temp / paths[0].name, index=False, encoding='utf-8-sig')
        write_excel(frame, temp / paths[1].name)
        write_excel(quality_frame, temp / paths[2].name)
        for path in paths:
            os.replace(temp / path.name, path)
    return {'records': len(active), 'fragments': sum(review.fragment for review in reviews),
            'quality_rows': len(quality), 'excluded': sum(review.excluded for review in reviews),
            'paths': [str(path) for path in paths]}
