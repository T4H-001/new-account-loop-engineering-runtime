#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--root", default=".")
parser.add_argument("--run-id", required=True)
parser.add_argument("--approved-by", required=True)
args = parser.parse_args()
root = Path(args.root)

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

receipt_files = sorted(root.glob("estate-curator-receipt-*.json"))
if len(receipt_files) != 3:
    raise SystemExit("promotion requires exactly three qualification receipts")
receipts = [load(p) for p in receipt_files]
source_hashes = {r["input"]["source_sha256"] for r in receipts}
if len(source_hashes) != 3 or not all(r.get("classification") == "REAL" for r in receipts):
    raise SystemExit("three distinct REAL source receipts required")

benchmark = load(root / "runtime/qualification/known-benchmark/summary.json")
unseen = load(root / "runtime/qualification/unseen-review.json")
if benchmark.get("status") != "PASS" or benchmark.get("passed") != 10:
    raise SystemExit("known-thread benchmark gate failed")
if unseen.get("outcome") != "PASS":
    raise SystemExit("unseen-thread review gate failed")

registry_path = root / "runtime/registry/worker_state.json"
registry = load(registry_path)
worker = registry["workers"]["wk-estate-curator-001"]
if worker.get("state") not in {"VERIFIED", "ACTIVE"}:
    raise SystemExit("worker must be VERIFIED or ACTIVE")
from_state = worker["state"]

now = datetime.now(timezone.utc).isoformat()
seed = f"{args.run_id}|{args.approved_by}|{unseen['review_hash']}|{benchmark['passed']}"
event_id = "evt-" + hashlib.sha256(seed.encode()).hexdigest()[:24]
receipt_id = "rcpt-" + hashlib.sha256((seed + "|promotion").encode()).hexdigest()[:24]
evidence = {
    "qualification_receipt_hashes": [r["receipt_hash"] for r in receipts],
    "distinct_source_sha256": sorted(source_hashes),
    "benchmark": benchmark,
    "unseen_review_hash": unseen["review_hash"],
    "approved_by": args.approved_by,
}
evidence_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
promotion = {
    "schema_version": 1,
    "status": "succeeded",
    "classification": "REAL",
    "action": "PROMOTE_WORKER_ACTIVE",
    "run_id": args.run_id,
    "worker_id": "wk-estate-curator-001",
    "principal_id": "principal:estate-curator-promoter",
    "approved_by": args.approved_by,
    "executed_at": now,
    "from_state": from_state,
    "to_state": "ACTIVE",
    "receipt_id": receipt_id,
    "event_id": event_id,
    "evidence": evidence,
    "evidence_hash": evidence_hash,
}
promotion["receipt_hash"] = hashlib.sha256(json.dumps(promotion, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
worker["state"] = "ACTIVE"
worker["health"] = "passing"
worker["last_promotion"] = now
worker["promotion_receipt_reference"] = receipt_id
registry.setdefault("ledger", []).append({
    "event_id": event_id,
    "worker_id": "wk-estate-curator-001",
    "from": from_state,
    "to": "ACTIVE",
    "receipt_id": receipt_id,
    "receipt_hash": promotion["receipt_hash"],
    "approved_by": args.approved_by,
})
registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
receipt_path = root / "runtime/evidence/promotions" / f"{args.run_id}.json"
telemetry_path = root / "runtime/evidence/telemetry" / f"{args.run_id}-promotion.json"
receipt_path.parent.mkdir(parents=True, exist_ok=True)
telemetry_path.parent.mkdir(parents=True, exist_ok=True)
receipt_path.write_text(json.dumps(promotion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
telemetry = {
    "event_id": event_id,
    "event_type": "estate.curator.promoted.active",
    "observed_at": now,
    "run_id": args.run_id,
    "worker_id": "wk-estate-curator-001",
    "receipt_id": receipt_id,
    "receipt_hash": promotion["receipt_hash"],
    "state": "ACTIVE",
}
telemetry_path.write_text(json.dumps(telemetry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(promotion, sort_keys=True))
