#!/usr/bin/env python3
"""Deterministic first vertical slice for wk-estate-curator-001."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path


WORKER_ID = "wk-estate-curator-001"
PRINCIPAL_ID = "principal:wk-estate-curator-001"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def classify(section: str, text: str) -> str:
    value = f"{section} {text}".lower()
    rules = [
        ("decision", r"\b(decision|approved|agreed|locked)\b"),
        ("unfinished_work", r"\b(still required|missing|not yet|next action|blocked)\b"),
        ("opportunity", r"\b(opportunity|commercial|revenue|pricing|customer|product)\b"),
        ("research", r"\b(research|hypothesis|evidence|experiment)\b"),
        ("human_insight", r"\b(human|culture|social impact|education|trust)\b"),
        ("runtime_defect", r"\b(defect|failure|broken|missing telemetry|wrong repository)\b"),
        ("capability", r"\b(capability|connector|worker|runtime|automation)\b"),
        ("pattern", r"\b(pattern|repeated|recurring|converged)\b"),
    ]
    for object_type, pattern in rules:
        if re.search(pattern, value):
            return object_type
    return "knowledge"


def extract(source_bytes: bytes, source_name: str) -> tuple[list[dict], list[dict]]:
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    text = source_bytes.decode("utf-8-sig")
    objects: list[dict] = []
    relationships: list[dict] = []
    section = "Unsectioned"
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        heading = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading:
            section = heading.group(1).strip()
        candidate = re.match(r"^(?:[*+-]|\d+\.)\s+(.+)$", line)
        explicit = re.search(
            r"\b(must|should|still required|not yet|next action|blocked|decision|"
            r"opportunity|pattern|receipt|telemetry|graph|register)\b",
            line,
            re.IGNORECASE,
        )
        if not line or (not heading and not candidate and not explicit):
            continue
        statement = (candidate.group(1) if candidate else heading.group(1) if heading else line).strip()
        object_type = "section" if heading else classify(section, statement)
        object_id = f"obj-{digest([source_hash, line_no, statement])[:24]}"
        obj = {
            "object_id": object_id,
            "object_type": object_type,
            "title": statement[:160],
            "text": statement,
            "lifecycle_state": "CANDIDATE",
            "owner": "T4H001",
            "created_by": WORKER_ID,
            "source": {
                "name": source_name,
                "sha256": source_hash,
                "line_start": line_no,
                "line_end": line_no,
                "exact_text": raw,
            },
            "evidence_state": "SOURCE_OCCURRENCE",
        }
        objects.append(obj)
        relationships.append(
            {
                "relationship_id": f"rel-{digest([source_hash, object_id, section])[:24]}",
                "subject_id": f"source-{source_hash[:24]}",
                "predicate": "contains_candidate",
                "object_id": object_id,
                "evidence": obj["source"],
                "lifecycle_state": "CANDIDATE",
                "created_by": WORKER_ID,
            }
        )
    return objects, relationships


def run(root: Path, input_path: Path, run_id: str, now: str | None = None) -> dict:
    root = root.resolve()
    input_path = input_path.resolve()
    source_bytes = input_path.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    receipt_path = root / f"runtime/evidence/receipts/{run_id}.json"
    if receipt_path.exists():
        prior = json.loads(receipt_path.read_text())
        if prior["input"]["source_sha256"] != source_hash:
            raise ValueError("idempotency collision: run_id reused for different input")
        return prior

    registry_path = root / "runtime/registry/worker_state.json"
    registry = json.loads(registry_path.read_text())
    worker = registry["workers"][WORKER_ID]
    checks = {
        "worker_registered": worker["state"] in {"REGISTERED", "VERIFIED", "ACTIVE"},
        "execution_allowed": worker["execution_allowed"] is True,
        "principal_bound": worker["principal_id"] == PRINCIPAL_ID,
        "source_nonempty": bool(source_bytes),
    }
    if not all(checks.values()):
        raise RuntimeError(f"preflight blocked: {checks}")

    observed_at = now or datetime.now(timezone.utc).isoformat()\n    state_after = "ACTIVE" if worker["state"] == "ACTIVE" else "VERIFIED"
    objects, relationships = extract(source_bytes, input_path.name)
    if not objects or len(objects) != len(relationships):
        raise RuntimeError("extraction produced an invalid graph candidate set")

    graph_dir = root / f"runtime/graph/runs/{run_id}"
    object_payload = {
        "schema_version": 1,
        "run_id": run_id,
        "source_sha256": source_hash,
        "objects": objects,
    }
    relationship_payload = {
        "schema_version": 1,
        "run_id": run_id,
        "source_sha256": source_hash,
        "relationships": relationships,
    }
    atomic_json(graph_dir / "objects.json", object_payload)
    atomic_json(graph_dir / "relationships.json", relationship_payload)

    review = {
        "review_id": f"rev-{digest([WORKER_ID, run_id, source_hash])[:24]}",
        "object_type": "curation_run",
        "requested_action": "REVIEW_FOR_PROMOTION",
        "review_policy": "HUMAN",
        "status": "PENDING",
        "submitted_by": WORKER_ID,
        "submitted_at": observed_at,
        "run_id": run_id,
        "source_sha256": source_hash,
        "candidate_object_count": len(objects),
        "candidate_relationship_count": len(relationships),
    }
    atomic_json(root / f"governanceos/review-queue/{review['review_id']}.json", review)

    evidence = {
        "checks": checks,
        "source_sha256": source_hash,
        "objects_sha256": digest(object_payload),
        "relationships_sha256": digest(relationship_payload),
        "review_sha256": digest(review),
    }
    receipt = {
        "schema_version": 1,
        "receipt_id": f"rcpt-{digest([WORKER_ID, run_id])[:24]}",
        "worker_id": WORKER_ID,
        "principal_id": PRINCIPAL_ID,
        "classification": "REAL",
        "status": "succeeded",
        "executed_at": observed_at,
        "input": {
            "run_id": run_id,
            "source_name": input_path.name,
            "source_sha256": source_hash,
        },
        "result": {
            "candidate_objects": len(objects),
            "candidate_relationships": len(relationships),
            "review_id": review["review_id"],
            "promotion_state": "PENDING_HUMAN_REVIEW",
            "worker_state_after": state_after,
        },
        "evidence": evidence,
    }
    receipt["evidence_hash"] = digest(evidence)
    receipt["receipt_hash"] = digest(receipt)
    telemetry = {
        "event_id": f"evt-{digest(receipt['receipt_id'])[:24]}",
        "event_type": "estate.curator.run.completed",
        "observed_at": observed_at,
        "worker_id": WORKER_ID,
        "run_id": run_id,
        "receipt_id": receipt["receipt_id"],
        "receipt_hash": receipt["receipt_hash"],
        "counts": {
            "objects": len(objects),
            "relationships": len(relationships),
            "review_submissions": 1,
        },
    }
    atomic_json(receipt_path, receipt)
    atomic_json(root / f"runtime/evidence/telemetry/{run_id}.json", telemetry)

    before = worker["state"]
    worker.update(
        {
            "state": state_after,
            "health": "passing",
            "last_verification": observed_at,
            "receipt_reference": receipt["receipt_id"],
            "successful_distinct_runs": sorted(
                set(worker.get("successful_distinct_runs", []) + [run_id])
            ),
        }
    )
    registry["ledger"].append(
        {
            "event_id": telemetry["event_id"],
            "worker_id": WORKER_ID,
            "from": before,
            "to": state_after,
            "receipt_id": receipt["receipt_id"],
            "receipt_hash": receipt["receipt_hash"],
        }
    )
    atomic_json(registry_path, registry)
    readback = json.loads(registry_path.read_text())["workers"][WORKER_ID]
    if readback["receipt_reference"] != receipt["receipt_id"]:
        raise RuntimeError("registry readback failed")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--now")
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.input, args.run_id, args.now), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
