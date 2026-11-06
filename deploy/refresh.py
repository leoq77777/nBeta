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
from deploy.feed import ingest
from deploy.player_stats import build_player_stats
from deploy.trace import update_trace


def publish(root: Path, sims: int = 100_000) -> str:
    snapshots = root / 'snapshots'
    snapshots.mkdir(parents=True, exist_ok=True)
    version = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    staging = Path(tempfile.mkdtemp(prefix='.building-', dir=snapshots))
    pointer = root / ('.current-' + uuid.uuid4().hex)
    try:
        previous_seed = root / 'current' / 'data' / 'seed'
        shutil.copytree(previous_seed if previous_seed.is_dir() else APP / 'data' / 'seed', staging / 'data' / 'seed')
        feed = ingest(staging / 'data' / 'seed', staging / 'evidence')
        build_all(staging, n_sims=sims)
        try:
            player_stats = build_player_stats(staging / "data" / "seed", root / "player-box-cache")
            (staging / "data" / "player_stats.json").write_text(json.dumps(player_stats))
        except Exception as exc:
            print(f"Player statistics unavailable: {exc}", file=sys.stderr)
            previous = root / "current" / "data" / "player_stats.json"
            if previous.is_file():
                shutil.copy2(previous, staging / "data" / "player_stats.json")
        run_path = staging / 'data' / 'run.json'
        run = json.loads(run_path.read_text())
        run[0].update(snapshot_id=version, score_source=feed['source'], score_checked_at=feed['checked_at'], score_pending_games=len(feed['pending_game_ids']), score_unresolved_games=len(feed['unresolved_past_game_ids']))
        run_path.write_text(json.dumps(run, indent=2))
        csv_path = staging / 'data' / 'run.csv'
        with csv_path.open(newline='') as f:
            reader = csv.DictReader(f)
            records, fields = list(reader), list(reader.fieldnames)
        fields.extend(['snapshot_id', 'score_source', 'score_checked_at', 'score_pending_games', 'score_unresolved_games'])
        for record in records:
            record.update(snapshot_id=version, score_source=feed['source'], score_checked_at=feed['checked_at'], score_pending_games=len(feed['pending_game_ids']), score_unresolved_games=len(feed['unresolved_past_game_ids']))
        with csv_path.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)
        staging.chmod(0o755)
        staging.rename(snapshots / version)
        update_trace(root, snapshots / version, version, APP)
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
