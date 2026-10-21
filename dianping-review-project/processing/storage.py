import hashlib
import json
from pathlib import Path
from filelock import FileLock
from capture.screenshot_utils import atomic_json, now
from processing.date_parser import parse_date
from processing.models import Review, set_status


def fingerprint(review):
    payload = {key: value for key, value in review.to_dict().items()
               if key not in {'manual_verified', 'excluded'}}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def load_reviews(path):
    return [Review.from_dict(item) for item in json.loads(Path(path).read_text(encoding='utf-8'))]


def save_reviews(path, reviews):
    atomic_json(path, [review.to_dict() for review in reviews])


def validate_values(values):
    allowed = {'rating', 'review_date_raw', 'review_text', 'review_status', 'excluded',
               'duplicate_of', 'manual_verified', 'fragment', 'merge_ids'}
    if set(values) - allowed:
        raise ValueError('未知校对字段')
    if not isinstance(values.get('merge_ids', []), list) or any(not isinstance(item, str) for item in values.get('merge_ids', [])):
        raise ValueError('merge_ids 必须为编号列表')
    if len(values.get('merge_ids', [])) != len(set(values.get('merge_ids', []))):
        raise ValueError('合并列表存在重复编号')
    rating = values.get('rating')
    if rating is not None and (isinstance(rating, bool) or not isinstance(rating, (int, float))
                               or not 0 <= rating <= 5 or rating * 2 != int(rating * 2)):
        raise ValueError('评分必须为空或 0–5 的半星值')
    if values.get('review_status') not in {'complete', 'incomplete', 'needs_review'}:
        raise ValueError('无效状态')
    for key in ['review_text', 'review_date_raw']:
        if not isinstance(values.get(key), str):
            raise ValueError(key + ' 必须为字符串')
    for key in ['excluded', 'manual_verified', 'fragment']:
        if key in values and not isinstance(values[key], bool):
            raise ValueError(key + ' 必须为布尔值')
    if values.get('manual_verified') and values.get('review_status') == 'complete':
        if rating is None or not values['review_text'].strip() or not parse_date(values['review_date_raw']).valid:
            raise ValueError('确认完整前，请填写有效评分、日期和正文')
        if values.get('fragment', False):
            raise ValueError('未拼接片段不能确认完整；请先合并或标记为独立评论')


def save_correction(path, review, values, source_reviews=None):
    validate_values(values)
    sources = {item.review_id: item for item in (source_reviews or [])}
    merges = values.get('merge_ids', [])
    if any(identifier not in sources or identifier == review.review_id for identifier in merges):
        raise ValueError('人工合并必须提供有效的原始来源记录')
    merge_hashes = {identifier: fingerprint(sources[identifier]) for identifier in merges}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(path) + '.lock', timeout=0):
        _save_correction(path, review, values, merge_hashes)


def _save_correction(path, review, values, merge_hashes):
    store = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'items': {}, 'history': []}
    patch = {'base_hash': fingerprint(review), 'values': values, 'updated_at': now(),
             'merge_hashes': merge_hashes}
    store['history'].append({'review_id': review.review_id, 'previous': store['items'].get(review.review_id),
                             'new': patch})
    store['items'][review.review_id] = patch
    atomic_json(path, store)


def apply_corrections(reviews, path):
    if not Path(path).exists():
        return reviews
    patches = json.loads(Path(path).read_text(encoding='utf-8'))['items']
    ids = {review.review_id for review in reviews}
    original_hashes = {review.review_id: fingerprint(review) for review in reviews}
    for review in reviews:
        patch = patches.get(review.review_id)
        if not patch:
            continue
        merge_stale = any(patch.get('merge_hashes', {}).get(identifier) != original_hashes.get(identifier)
                          for identifier in patch['values'].get('merge_ids', []))
        if patch['base_hash'] != fingerprint(review) or merge_stale:
            review.flags.append('correction_stale')
            set_status(review)
            continue
        values = patch['values']
        validate_values(values)
        if values.get('duplicate_of') and (values['duplicate_of'] not in ids or
                                           values['duplicate_of'] == review.review_id):
            raise ValueError('重复目标不存在或指向自身')
        for key, value in values.items():
            if key != 'merge_ids':
                setattr(review, key, value)
        parsed = parse_date(review.review_date_raw)
        review.review_date_normalized = parsed.normalized if parsed.valid else ''
        if review.manual_verified:
            review.flags = ['manual_verified']
            # Keep explicit manual status. Missing year remains blank, never fabricated.
    by_id = {review.review_id: review for review in reviews}
    claimed = set()
    merges = {key: patch['values'].get('merge_ids', []) for key, patch in patches.items()
              if key in by_id and 'correction_stale' not in by_id[key].flags}
    for target_id, children in merges.items():
        target = by_id[target_id]
        for child_id in children:
            if child_id not in by_id or child_id == target_id or child_id in claimed or merges.get(child_id):
                raise ValueError('人工合并目标无效、重复使用或存在链式合并；请合并到同一主记录')
            claimed.add(child_id)
            child = by_id[child_id]
            target.source_images = list(dict.fromkeys(target.source_images + child.source_images))
            for evidence in child.evidence:
                if evidence not in target.evidence:
                    target.evidence.append(evidence)
            child.excluded = True
            child.duplicate_of = target_id
            child.flags.append('manually_merged')
    return reviews
