"""Import user-saved PNG/JPG images, ordered by explicit filename; never modifies originals."""
import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image
from capture.screenshot_utils import CaptureStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='仅包含截图的文件夹；先将文件命名为 001.png、002.png 等')
    parser.add_argument('--session', required=True, help='目标采集会话目录')
    args = parser.parse_args()
    source, target = Path(args.source).resolve(), Path(args.session).resolve()
    if source == target:
        parser.error('源与目标目录必须不同')
    files = sorted(path for path in source.iterdir() if path.suffix.lower() in {'.png', '.jpg', '.jpeg'})
    if not files:
        parser.error('没有可导入的图片')
    with Image.open(files[0]) as image:
        region = [0, 0, *image.size]
    store = CaptureStore(target, region)
    imported = {item.get('import_sha256') for item in store.data['screenshots']}
    try:
        for path in files:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in imported:
                print('已导入，跳过：', path.name)
                continue
            with Image.open(path) as image:
                if list(image.size) != region[2:]:
                    raise ValueError('截图尺寸不一致，请先按相同区域裁剪：' + path.name)
                store.save(image.convert('RGB'))
            entry = store.data['screenshots'][-1]
            entry.update(import_sha256=digest, collected_at=datetime.fromtimestamp(
                path.stat().st_mtime, timezone.utc).isoformat(), time_source='filesystem_mtime')
            from capture.screenshot_utils import atomic_json
            atomic_json(store.path, store.data)
            imported.add(digest)
        store.finish('import_complete')
    except Exception:
        store.finish('import_error')
        raise
    print('已导入；mtime 仅为文件时间，不保证是真实采集时间。', store.path)


if __name__ == '__main__':
    main()
