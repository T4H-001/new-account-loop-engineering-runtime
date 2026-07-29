import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "runtime/intake/archive_inventory.py"

class ArchiveInventoryTests(unittest.TestCase):
    def run_worker(self, archive_dir, evidence_root, run_id="test-archive"):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--input-dir", str(archive_dir),
             "--root", str(evidence_root), "--run-id", run_id],
            text=True, capture_output=True,
        )

    def test_hashes_members_duplicates_and_replays(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "source"
            source.mkdir()
            with zipfile.ZipFile(source / "one.zip", "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("statements/a.txt", b"same bytes")
                zf.writestr("statements/b.txt", b"different")
            with zipfile.ZipFile(source / "two.zip", "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("copy/a.txt", b"same bytes")
            first = self.run_worker(source, base)
            self.assertEqual(first.returncode, 0, first.stderr)
            receipt = json.loads(first.stdout)
            self.assertEqual(receipt["classification"], "REAL")
            self.assertEqual(receipt["archive_count"], 2)
            self.assertEqual(receipt["member_count"], 3)
            self.assertEqual(receipt["unique_member_hashes"], 2)
            self.assertEqual(receipt["duplicate_group_count"], 1)
            for suffix in [
                "runtime/evidence/archive/test-archive-inventory.json",
                "runtime/evidence/archive/test-archive-receipt.json",
                "runtime/evidence/telemetry/test-archive-archive.json",
                "runtime/evidence/ledger/test-archive-archive.json",
            ]:
                self.assertTrue((base / suffix).is_file(), suffix)
            second = self.run_worker(source, base)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(second.stdout), receipt)

    def test_path_traversal_fails_closed_without_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "source"
            source.mkdir()
            with zipfile.ZipFile(source / "unsafe.zip", "w") as zf:
                zf.writestr("../escape.txt", b"blocked")
            result = self.run_worker(source, base, "unsafe-run")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsafe archive path", result.stderr)
            self.assertFalse((base / "runtime/evidence/archive/unsafe-run-receipt.json").exists())

if __name__ == "__main__":
    unittest.main()
