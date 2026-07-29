import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "estate_curator", ROOT / "runtime/executor/estate_curator.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EstateCuratorTest(unittest.TestCase):
    def test_bounded_run_provenance_graph_review_receipt_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "repo"
            shutil.copytree(ROOT, fixture)
            source = fixture / "tests/fixtures/estate-curator-thread.txt"
            run_id = "estate-curator-test-001"
            now = "2026-07-27T09:00:00+00:00"

            initial_registry = json.loads((fixture / "runtime/registry/worker_state.json").read_text())
            initial_state = initial_registry["workers"][MODULE.WORKER_ID]["state"]
            initial_ledger_count = len(initial_registry["ledger"])
            expected_state = "ACTIVE" if initial_state == "ACTIVE" else "VERIFIED"

            first = MODULE.run(fixture, source, run_id, now)
            registry_path = fixture / "runtime/registry/worker_state.json"
            registry_before_replay = registry_path.read_bytes()
            replay = MODULE.run(fixture, source, run_id, "2099-01-01T00:00:00+00:00")

            objects = json.loads(
                (fixture / f"runtime/graph/runs/{run_id}/objects.json").read_text()
            )["objects"]
            relationships = json.loads(
                (fixture / f"runtime/graph/runs/{run_id}/relationships.json").read_text()
            )["relationships"]
            review_id = first["result"]["review_id"]
            review = json.loads(
                (fixture / f"governanceos/review-queue/{review_id}.json").read_text()
            )
            registry = json.loads(registry_path.read_text())
            worker = registry["workers"][MODULE.WORKER_ID]

            self.assertEqual("REAL", first["classification"])
            self.assertEqual(expected_state, worker["state"])
            self.assertEqual("PENDING", review["status"])
            self.assertEqual("HUMAN", review["review_policy"])
            self.assertEqual(len(objects), len(relationships))
            self.assertGreaterEqual(len(objects), 8)
            self.assertTrue(all(item["source"]["exact_text"] for item in objects))
            self.assertTrue(all(item["lifecycle_state"] == "CANDIDATE" for item in objects))
            self.assertEqual(first, replay)
            self.assertEqual(registry_before_replay, registry_path.read_bytes())
            self.assertEqual(initial_ledger_count + 1, len(registry["ledger"]))
            self.assertEqual(expected_state, first["result"]["worker_state_after"])

    def test_run_id_collision_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "repo"
            shutil.copytree(ROOT, fixture)
            source = fixture / "tests/fixtures/estate-curator-thread.txt"
            MODULE.run(fixture, source, "collision-test", "2026-07-27T09:00:00+00:00")
            source.write_text("different source")
            with self.assertRaisesRegex(ValueError, "idempotency collision"):
                MODULE.run(fixture, source, "collision-test")


if __name__ == "__main__":
    unittest.main()
