"""Resumable offline processing. No collection or review API requests."""
import argparse
import hashlib
import json
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError
from filelock import FileLock
from PIL import Image
import yaml
from capture.screenshot_utils import atomic_json
from processing.models import Review
from processing.ocr_engine import PaddleEngine, FixtureEngine
from processing.detect_rating import detect_ratings
from processing.detect_reviews import parse_reviews
from processing.merge_reviews import estimate_shift, merge_frame
from processing.deduplicate import mark_duplicates
from processing.storage import save_reviews, load_reviews, apply_corrections
from export.export_excel import export_reviews

PIPELINE_VERSION = '1.0'


def safe_image_path(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if path.parent != root or not path.is_file():
        raise ValueError('截图路径无效或超出会话目录：' + str(name))
    return path


def read_manifest(session):
    path = Path(session) / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    entries = manifest['screenshots']
    if not entries:
        raise ValueError('manifest 没有截图，不会生成空的成功报告')
    sequences = [entry['sequence'] for entry in entries]
    if len(sequences) != len(set(sequences)) or sequences != sorted(sequences):
        raise ValueError('截图顺序重复或乱序')
    names = [entry['file'] for entry in entries]
    if len(names) != len(set(names)):
        raise ValueError('manifest 文件名重复')
    for entry in entries:
        path = safe_image_path(session, entry['file'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('截图校验和不匹配：' + entry['file'])
    return entries


def process_session(session, work, config, engine=None, fixture=None):
    Path(work).mkdir(parents=True, exist_ok=True)
    with FileLock(str(Path(work) / '.processing.lock'), timeout=0):
        return _process_session(session, work, config, engine, fixture)


def _process_session(session, work, config, engine=None, fixture=None):
    session, work = Path(session), Path(work)
    work.mkdir(parents=True, exist_ok=True)
    entries = read_manifest(session)
    if fixture is not None:
        engine = FixtureEngine(fixture)
    cache_path = work / 'checkpoint.json'
    cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {'pages': {}}
    code_hash = hashlib.sha256(b''.join(path.read_bytes() for path in sorted(Path(__file__).parent.glob('*.py')))).hexdigest()
    try:
        backend_version = version('paddleocr')
    except PackageNotFoundError:
        backend_version = 'not-installed'
    local_models = {}
    for key, value in config.get('ocr', {}).items():
        if value:
            directory = Path(value)
            if not directory.is_dir():
                raise ValueError('本地模型目录不存在：' + str(directory))
            local_models[key] = {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in sorted(directory.rglob('*')) if path.is_file()}
    settings = json.dumps({'version': PIPELINE_VERSION, 'code_hash': code_hash,
                           'backend_version': backend_version, 'local_models': local_models,
                           'config': config, 'fixture': fixture,
                           'engine': 'fixture' if fixture is not None else 'PaddleOCR3-CPU'},
                          ensure_ascii=False, sort_keys=True)
    pages, previous, previous_name, reviews = [], None, None, []
    recomputed = 0
    for entry in entries:
        filename = entry['file']
        signature = hashlib.sha256((settings + json.dumps(entry, sort_keys=True)).encode()).hexdigest()
        image_path = safe_image_path(session, filename)
        with Image.open(image_path) as opened:
            image = opened.convert('RGB')
        cached = cache['pages'].get(filename)
        if cached and cached['signature'] == signature:
            page = [Review.from_dict(item) for item in cached['reviews']]
        else:
            if engine is None:
                engine = PaddleEngine(config.get('ocr'))
            lines = engine.recognize_file(filename) if fixture is not None else engine.recognize(image)
            ratings = detect_ratings(image, config.get('rating'))
            page = parse_reviews(lines, ratings, image, filename, entry['collected_at'], entry['sequence'], config)
            cache['pages'][filename] = {'signature': signature, 'reviews': [review.to_dict() for review in page]}
            # Only selected body/date/rating records are persisted, never raw OCR headers.
            atomic_json(cache_path, cache)
            recomputed += 1
        shift = estimate_shift(previous, image) if previous is not None else None
        reviews = merge_frame(reviews, page, previous_name, shift)
        pages.append({'image': filename, 'visual_shift': shift, 'parsed_candidates': len(page)})
        previous, previous_name = image, filename
        print(f"[{len(pages)}/{len(entries)}] {filename}，候选 {len(page)}，位移 {shift}", flush=True)
    mark_duplicates(reviews)
    save_reviews(work / 'reviews.json', reviews)
    stats = {'demo': fixture is not None, 'pipeline_version': PIPELINE_VERSION,
             'session': str(session.resolve()), 'screenshots': len(entries),
             'review_candidates': sum(not review.fragment for review in reviews),
             'unjoined_fragments': sum(review.fragment for review in reviews),
             'recomputed_pages': recomputed, 'pages': pages,
             'status_counts': {status: sum(review.review_status == status for review in reviews)
                               for status in ['complete', 'incomplete', 'needs_review']}}
    atomic_json(work / 'run.json', stats)
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    process = commands.add_parser('process')
    process.add_argument('--session', required=True)
    process.add_argument('--work', default='data/intermediate/session01')
    process.add_argument('--config', default='config.yaml')
    process.add_argument('--fixture', help='仅用于明确标记的模拟/测试 OCR 输入；输出自动标记演示')
    export = commands.add_parser('export')
    export.add_argument('--work', default='data/intermediate/session01')
    export.add_argument('--output', default='data/output/session01')
    args = parser.parse_args()
    if args.command == 'process':
        settings = yaml.safe_load(Path(args.config).read_text(encoding='utf-8'))['processing']
        fixture = json.loads(Path(args.fixture).read_text(encoding='utf-8')) if args.fixture else None
        print(json.dumps(process_session(args.session, args.work, settings, fixture=fixture), ensure_ascii=False, indent=2))
    else:
        work = Path(args.work)
        run = json.loads((work / 'run.json').read_text(encoding='utf-8'))
        reviews = apply_corrections(load_reviews(work / 'reviews.json'), work / 'corrections.json')
        print(json.dumps(export_reviews(reviews, args.output, demo=run['demo']), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
