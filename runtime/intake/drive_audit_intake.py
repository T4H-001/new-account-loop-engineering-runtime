#!/usr/bin/env python3
"""Validate a metadata-only Google Drive audit snapshot and emit governed intake evidence."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--manifest", required=True)
p.add_argument("--root", default=".")
p.add_argument("--run-id", required=True)
p.add_argument("--output-source", required=True)
args = p.parse_args()
root = Path(args.root)
manifest_path = Path(args.manifest)
manifest_bytes = manifest_path.read_bytes()
manifest = json.loads(manifest_bytes)
manifest_type = manifest.get("manifest_type")
folders = manifest.get("folders", [])
if manifest_type == "google_drive_audit_intake_snapshot":
    entries = [item for folder in folders for item in folder.get("direct_children", [])]
    governed_roots = [folder.get("id") for folder in folders]
    unreadable_folder_ids = []
    folders_at_limit = []
    completeness = "DIRECT_CHILDREN_ONLY"
elif manifest_type == "google_drive_audit_recursive_snapshot":
    entries = manifest.get("files", [])
    governed_roots = manifest.get("root_folder_ids", [])
    unreadable_folder_ids = manifest.get("unreadable_folder_ids", [])
    folders_at_limit = manifest.get("folders_at_connector_limit", [])
    completeness = manifest.get("completeness", "PARTIAL")
else:
    raise SystemExit("unexpected manifest type")

seen = set()
for item in entries:
    file_id = item.get("id")
    if not file_id or file_id in seen:
        raise SystemExit("missing or duplicate Drive file ID")
    seen.add(file_id)
if not entries:
    raise SystemExit("empty Drive inventory")
if not governed_roots:
    raise SystemExit("missing governed Drive roots")

manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
now = datetime.now(timezone.utc).isoformat()
seed = f"{args.run_id}|{manifest_sha}|{len(entries)}"
receipt_id = "rcpt-" + hashlib.sha256(seed.encode()).hexdigest()[:24]
event_id = "evt-" + hashlib.sha256((seed + "|event").encode()).hexdigest()[:24]
mime_counts = {}
for item in entries:
    mime = item.get("mime_type") or "unknown"
    mime_counts[mime] = mime_counts.get(mime, 0) + 1
inventory_bytes = sum(int(x.get("size_bytes") or 0) for x in entries)
source = [
    "# FY24/25 Google Drive Audit Evidence Intake",
    "",
    f"Owner: {manifest.get('accountable_owner')}",
    f"Manifest SHA-256: {manifest_sha}",
    f"Governed Drive roots: {len(governed_roots)}",
    f"Discovered folders: {len(folders)}",
    f"Unique inventory entries: {len(entries)}",
    f"Inventory bytes: {inventory_bytes}",
    f"Metadata completeness: {completeness}",
    "",
    "## Controls",
    "- Metadata-only intake; private document bytes are not committed.",
    "- Google Drive file ID is the source identity.",
    "- Content hashes remain pending until raw-byte ingestion.",
    "- Tax and legal classifications remain human-only.",
    "- Every candidate defaults to pending review.",
    "",
    "## Governed roots",
]
for folder_id in governed_roots:
    source.append(f"- {folder_id}")
source += ["", "## Exceptions"]
source.append(f"- Unreadable folders: {len(unreadable_folder_ids)}")
source.append(f"- Folders at connector child limit: {len(folders_at_limit)}")
source += ["", "## MIME inventory"]
for mime, count in sorted(mime_counts.items()):
    source.append(f"- {mime}: {count}")
out = Path(args.output_source)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(source) + "\n", encoding="utf-8")
receipt = {
    "schema_version": 2,
    "status": "succeeded",
    "classification": "REAL",
    "action": "GOOGLE_DRIVE_AUDIT_METADATA_INTAKE",
    "run_id": args.run_id,
    "principal_id": "principal:wk-estate-curator-001",
    "receipt_id": receipt_id,
    "event_id": event_id,
    "observed_at": now,
    "manifest_sha256": manifest_sha,
    "root_count": len(governed_roots),
    "folder_count": len(folders),
    "entry_count": len(entries),
    "inventory_bytes": inventory_bytes,
    "metadata_completeness": completeness,
    "unreadable_folder_ids": unreadable_folder_ids,
    "folders_at_connector_limit": folders_at_limit,
    "content_hash_status": "PENDING_RAW_BYTE_INGEST",
    "review_state": "PENDING_HUMAN_REVIEW",
}
receipt["receipt_hash"] = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
receipt_dir = root / "runtime/evidence/intake"
telemetry_dir = root / "runtime/evidence/telemetry"
receipt_dir.mkdir(parents=True, exist_ok=True)
telemetry_dir.mkdir(parents=True, exist_ok=True)
(receipt_dir / f"{args.run_id}.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
telemetry = {
    "event_id": event_id,
    "event_type": "estate.curator.drive.intake.completed",
    "observed_at": now,
    "run_id": args.run_id,
    "receipt_id": receipt_id,
    "receipt_hash": receipt["receipt_hash"],
    "entry_count": len(entries),
    "metadata_completeness": completeness,
    "worker_id": "wk-estate-curator-001",
}
(telemetry_dir / f"{args.run_id}-intake.json").write_text(json.dumps(telemetry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(receipt, sort_keys=True))
