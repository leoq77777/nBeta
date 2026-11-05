"""Build an immutable model snapshot and atomically switch the published pointer."""
from __future__ import annotations
import csv
import json
import os
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from pipeline.build_daily import build_all


def publish(root: Path, sims: int = 100_000) -> str:
    snapshots = root / 'snapshots'
    snapshots.mkdir(parents=True, exist_ok=True)
    version = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    staging = Path(tempfile.mkdtemp(prefix='.building-', dir=snapshots))
    pointer = root / ('.current-' + uuid.uuid4().hex)
    try:
        shutil.copytree(APP / 'data' / 'seed', staging / 'data' / 'seed')
        build_all(staging, n_sims=sims)
        run_path = staging / 'data' / 'run.json'
        run = json.loads(run_path.read_text())
        run[0]['snapshot_id'] = version
        run_path.write_text(json.dumps(run, indent=2))
        csv_path = staging / 'data' / 'run.csv'
        with csv_path.open(newline='') as f:
            reader = csv.DictReader(f)
            records, fields = list(reader), list(reader.fieldnames)
        fields.append('snapshot_id')
        for record in records:
            record['snapshot_id'] = version
        with csv_path.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)
        staging.chmod(0o755)
        staging.rename(snapshots / version)
        pointer.symlink_to(Path('snapshots') / version)
        os.replace(pointer, root / 'current')
        return version
    finally:
        if pointer.is_symlink():
            pointer.unlink()
        if staging.exists():
            shutil.rmtree(staging)


if __name__ == '__main__':
    root = Path(os.environ.get('NBETA_ROOT', str(Path.home() / 'projects' / 'nbeta')))
    print('Published snapshot:', publish(root))
