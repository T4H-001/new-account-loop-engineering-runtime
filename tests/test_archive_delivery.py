import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "runtime/intake/verify_archive_delivery.py"

class ArchiveDeliveryTests(unittest.TestCase):
    def write_manifest(self, base, expected_size):
        manifest = {
            "archive_count": 1,
            "archive_bytes": expected_size,
            "files": [{
                "id": "drive-1",
                "title": "evidence.zip",
                "mime_type": "application/zip",
                "size_bytes": expected_size,
                "parent_folder_id": "folder-1",
            }],
        }
        path = base / "manifest.json"
        path.write_text(json.dumps(manifest))
        return path

    def run_verifier(self, base, manifest, source):
        return subprocess.run([
            sys.executable, str(SCRIPT), "--manifest", str(manifest),
            "--input-dir", str(source), "--output", str(base / "delivery.json")
        ], text=True, capture_output=True)

    def test_exact_delivery_succeeds_with_hash(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "source"
            source.mkdir()
            payload = b"archive source bytes"
            (source / "evidence.zip").write_bytes(payload)
            result = self.run_verifier(base, self.write_manifest(base, len(payload)), source)
            self.assertEqual(result.returncode, 0, result.stderr)
            evidence = json.loads((base / "delivery.json").read_text())
            self.assertEqual(evidence["classification"], "REAL")
            self.assertEqual(evidence["archive_count"], 1)
            self.assertEqual(evidence["records"][0]["drive_file_id"], "drive-1")
            self.assertEqual(len(evidence["records"][0]["sha256"]), 64)

    def test_size_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "source"
            source.mkdir()
            (source / "evidence.zip").write_bytes(b"changed")
            result = self.run_verifier(base, self.write_manifest(base, 999), source)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("archive byte mismatch", result.stderr)
            self.assertFalse((base / "delivery.json").exists())

    def test_missing_archive_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "source"
            source.mkdir()
            result = self.run_verifier(base, self.write_manifest(base, 1), source)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("archive set mismatch", result.stderr)

if __name__ == "__main__":
    unittest.main()
