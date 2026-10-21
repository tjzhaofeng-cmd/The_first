"""Atomic, resumable local screenshot storage. Never uploads screenshots."""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from filelock import FileLock


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def similarity(first, second):
    if first.size != second.size:
        return 0.0
    a, b = (image.convert("RGB").resize((128, 128)) for image in (first, second))
    return 1 - sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / (3 * 255)


class CaptureStore:
    def __init__(self, directory, region):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.directory / '.capture.lock'), timeout=0)
        self.lock.acquire()
        try:
            self._initialize(region)
        except BaseException:
            self.lock.release()
            raise

    def _initialize(self, region):
        self.path = self.directory / "manifest.json"
        self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {
            "schema_version": 1, "region": list(region), "screenshots": [], "batches": []}
        if self.data["region"] != list(region):
            raise ValueError("续采区域与原始区域不同，请恢复原窗口位置或使用新目录")
        known = {item["file"] for item in self.data["screenshots"]}
        missing = [name for name in known if not (self.directory / name).is_file()]
        if missing:
            raise ValueError("manifest 中的截图缺失，请先恢复文件：" + str(missing))
        for entry in self.data['screenshots']:
            if hashlib.sha256((self.directory / entry['file']).read_bytes()).hexdigest() != entry['sha256']:
                raise ValueError('截图校验和不一致，请检查：' + entry['file'])
        # A crash after PNG rename but before manifest save leaves an orphan.
        for image in sorted(self.directory.glob("capture_*.png")):
            if image.name not in known:
                with Image.open(image) as check:
                    check.verify()
                self.data["screenshots"].append({
                    "file": image.name, "sequence": len(self.data["screenshots"]) + 1,
                    "batch_id": "recovered", "collected_at": datetime.fromtimestamp(
                        image.stat().st_mtime, timezone.utc).isoformat(),
                    "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                    "recovered": True})
        self.batch = uuid.uuid4().hex[:12]
        self.data["batches"].append({"batch_id": self.batch, "started_at": now()})
        atomic_json(self.path, self.data)

    def save(self, image):
        sequence = len(self.data["screenshots"]) + 1
        filename = f"capture_{sequence:06d}_{self.batch}_{uuid.uuid4().hex[:8]}.png"
        target = self.directory / filename
        if not self.lock.is_locked:
            raise RuntimeError('会话未持有采集锁')
        temporary = target.with_suffix('.png.tmp')
        try:
            with temporary.open('xb') as file:
                image.save(file, format='PNG')
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        self.data["screenshots"].append({
            "file": filename, "sequence": sequence, "batch_id": self.batch,
            "collected_at": now(), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
        atomic_json(self.path, self.data)
        return target

    def finish(self, reason):
        try:
            self.data["batches"][-1].update(ended_at=now(), stop_reason=reason)
            atomic_json(self.path, self.data)
        finally:
            self.lock.release()
