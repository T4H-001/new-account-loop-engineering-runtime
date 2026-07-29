#!/usr/bin/env python3
"""Losslessly inventory ZIP archives and emit governed archive evidence."""
import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_RATIO = 1000.0

def sha256_stream(handle):
    h = hashlib.sha256()
    total = 0
    while True:
        chunk = handle.read(1024 * 1024)
        if not chunk:
            return h.hexdigest(), total
        h.update(chunk)
        total += len(chunk)

def safe_name(name):
    normalized = name.replace("\\", "/")
    p = PurePosixPath(normalized)
    return (
        bool(normalized)
        and not normalized.startswith("/")
        and not re.match(r"^[A-Za-z]:", normalized)
        and ".." not in p.parts
    )

def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    source_dir = Path(args.input_dir)
    root = Path(args.root)
    archives = sorted(source_dir.glob("*.zip"))
    if not archives:
        raise SystemExit("no ZIP archives found")

    members = []
    archive_records = []
    total_uncompressed = 0
    for archive in archives:
        with archive.open("rb") as fh:
            archive_sha, archive_bytes = sha256_stream(fh)
        with zipfile.ZipFile(archive) as zf:
            archive_member_count = 0
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if not safe_name(info.filename):
                    raise SystemExit(f"unsafe archive path: {archive.name}:{info.filename}")
                if info.flag_bits & 0x1:
                    raise SystemExit(f"encrypted member unsupported: {archive.name}:{info.filename}")
                if info.file_size > MAX_MEMBER_BYTES:
                    raise SystemExit(f"member exceeds size control: {archive.name}:{info.filename}")
                ratio = info.file_size / max(info.compress_size, 1)
                if ratio > MAX_RATIO:
                    raise SystemExit(f"compression ratio exceeds control: {archive.name}:{info.filename}")
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_TOTAL_BYTES:
                    raise SystemExit("aggregate uncompressed size exceeds control")
                with zf.open(info, "r") as member:
                    member_sha, actual_bytes = sha256_stream(member)
                if actual_bytes != info.file_size:
                    raise SystemExit(f"member byte-count mismatch: {archive.name}:{info.filename}")
                members.append({
                    "archive_name": archive.name,
                    "archive_sha256": archive_sha,
                    "member_path": info.filename,
                    "member_bytes": info.file_size,
                    "compressed_bytes": info.compress_size,
                    "crc32": f"{info.CRC:08x}",
                    "member_sha256": member_sha,
                })
                archive_member_count += 1
        archive_records.append({
            "archive_name": archive.name,
            "archive_bytes": archive_bytes,
            "archive_sha256": archive_sha,
            "member_count": archive_member_count,
        })

    hash_groups = {}
    for member in members:
        hash_groups.setdefault(member["member_sha256"], []).append(
            f'{member["archive_name"]}:{member["member_path"]}'
        )
    duplicate_groups = [
        {"member_sha256": digest, "occurrences": sorted(paths)}
        for digest, paths in sorted(hash_groups.items())
        if len(paths) > 1
    ]

    now = datetime.now(timezone.utc).isoformat()
    evidence = {
        "schema_version": 1,
        "run_id": args.run_id,
        "classification": "REAL",
        "archive_count": len(archive_records),
        "archive_bytes": sum(x["archive_bytes"] for x in archive_records),
        "member_count": len(members),
        "unique_member_hashes": len(hash_groups),
        "duplicate_group_count": len(duplicate_groups),
        "uncompressed_member_bytes": total_uncompressed,
        "archives": archive_records,
        "members": members,
        "duplicate_groups": duplicate_groups,
        "controls": {
            "path_traversal": "FAIL_CLOSED",
            "encrypted_members": "FAIL_CLOSED",
            "member_size_limit": MAX_MEMBER_BYTES,
            "aggregate_size_limit": MAX_TOTAL_BYTES,
            "compression_ratio_limit": MAX_RATIO,
            "source_mutation": "NONE",
        },
    }
    evidence_hash = hashlib.sha256(canonical_json(evidence)).hexdigest()
    seed = f"{args.run_id}|{evidence_hash}"
    receipt_id = "rcpt-" + hashlib.sha256(seed.encode()).hexdigest()[:24]
    event_id = "evt-" + hashlib.sha256((seed + "|event").encode()).hexdigest()[:24]
    receipt = {
        "schema_version": 1,
        "status": "succeeded",
        "classification": "REAL",
        "action": "ARCHIVE_MEMBER_LOSSLESS_INVENTORY",
        "run_id": args.run_id,
        "principal_id": "principal:wk-estate-curator-001",
        "worker_id": "wk-estate-curator-001",
        "receipt_id": receipt_id,
        "event_id": event_id,
        "observed_at": now,
        "evidence_hash": evidence_hash,
        "archive_count": evidence["archive_count"],
        "archive_bytes": evidence["archive_bytes"],
        "member_count": evidence["member_count"],
        "unique_member_hashes": evidence["unique_member_hashes"],
        "duplicate_group_count": evidence["duplicate_group_count"],
        "source_mutation": "NONE",
        "review_state": "PENDING_HUMAN_REVIEW",
    }
    receipt["receipt_hash"] = hashlib.sha256(canonical_json(receipt)).hexdigest()
    telemetry = {
        "event_id": event_id,
        "event_type": "estate.curator.archive.inventory.completed",
        "observed_at": now,
        "run_id": args.run_id,
        "worker_id": receipt["worker_id"],
        "receipt_id": receipt_id,
        "receipt_hash": receipt["receipt_hash"],
        "counts": {
            "archives": evidence["archive_count"],
            "members": evidence["member_count"],
            "unique_member_hashes": evidence["unique_member_hashes"],
            "duplicate_groups": evidence["duplicate_group_count"],
        },
    }
    ledger = {
        "event_id": event_id,
        "run_id": args.run_id,
        "worker_id": receipt["worker_id"],
        "action": receipt["action"],
        "receipt_id": receipt_id,
        "receipt_hash": receipt["receipt_hash"],
        "evidence_hash": evidence_hash,
        "classification": "REAL",
        "source_mutation": "NONE",
    }
    evidence_dir = root / "runtime/evidence/archive"
    telemetry_dir = root / "runtime/evidence/telemetry"
    ledger_dir = root / "runtime/evidence/ledger"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / f"{args.run_id}-inventory.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    (evidence_dir / f"{args.run_id}-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    (telemetry_dir / f"{args.run_id}-archive.json").write_text(json.dumps(telemetry, indent=2, sort_keys=True) + "\n")
    (ledger_dir / f"{args.run_id}-archive.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))

if __name__ == "__main__":
    main()
