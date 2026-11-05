import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from deploy.refresh import publish

class DeploymentTests(unittest.TestCase):
    def test_publish_switches_only_after_complete_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'snapshots' / 'old').mkdir(parents=True)
            (root / 'current').symlink_to('snapshots/old')
            def fail(*args, **kwargs):
                raise RuntimeError('build failed')
            with patch('deploy.refresh.build_all', fail):
                with self.assertRaises(RuntimeError):
                    publish(root, 1)
            self.assertEqual((root / 'current').resolve(), (root / 'snapshots' / 'old').resolve())
            def build(staging, **kwargs):
                data = staging / 'data'
                (data / 'run.json').write_text(json.dumps([{'as_of':'test'}]))
                (data / 'run.csv').write_text('as_of\ntest\n')
            with patch('deploy.refresh.build_all', build):
                version = publish(root, 1)
            self.assertEqual((root / 'current').resolve(), (root / 'snapshots' / version).resolve())
            self.assertEqual((root / 'snapshots' / version).stat().st_mode & 0o777, 0o755)
            self.assertEqual(json.loads((root / 'current/data/run.json').read_text())[0]['snapshot_id'], version)
            self.assertIn(version, (root / 'current/data/run.csv').read_text())

if __name__ == '__main__':
    unittest.main()
