#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--receipt", required=True)
parser.add_argument("--telemetry", required=True)
parser.add_argument("--objects", required=True)
parser.add_argument("--relationships", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

receipt = load(args.receipt)
telemetry = load(args.telemetry)
objects = load(args.objects)
relationships = load(args.relationships)
checks = {
    "classification_real": receipt.get("classification") == "REAL",
    "status_succeeded": receipt.get("status") == "succeeded",
    "promotion_pending": receipt.get("result", {}).get("promotion_state") == "PENDING_HUMAN_REVIEW",
    "receipt_telemetry_bound": telemetry.get("receipt_id") == receipt.get("receipt_id"),
    "objects_nonempty": len(objects) > 0,
    "relationships_nonempty": len(relationships) > 0,
    "object_count_matches": len(objects) == receipt.get("result", {}).get("candidate_objects"),
    "relationship_count_matches": len(relationships) == receipt.get("result", {}).get("candidate_relationships"),
}
passed = all(checks.values())
review = {
    "schema_version": 1,
    "review_type": "independent_unseen_thread",
    "reviewer_principal": "principal:estate-curator-independent-reviewer",
    "reviewed_at": datetime.now(timezone.utc).isoformat(),
    "source_sha256": receipt.get("input", {}).get("source_sha256"),
    "receipt_id": receipt.get("receipt_id"),
    "receipt_hash": receipt.get("receipt_hash"),
    "telemetry_event_id": telemetry.get("event_id"),
    "checks": checks,
    "outcome": "PASS" if passed else "FAIL",
    "promotion_effect": "NONE",
}
canonical = json.dumps(review, sort_keys=True, separators=(",", ":")).encode()
review["review_hash"] = hashlib.sha256(canonical).hexdigest()
Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if not passed:
    raise SystemExit(1)
print(json.dumps(review, sort_keys=True))
