#!/usr/bin/env python3
"""Verify that a private archive delivery matches the canonical Drive metadata manifest."""
import argparse
import hashlib
import json
from pathlib import Path

SUPPORTED = (".zip", ".tar.gz", ".tgz")

def sha256_file(path):
    h = hashlib.sha256()
    total = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                return h.hexdigest(), total
            h.update(chunk)
            total += len(chunk)

def is_archive(name, mime):
    lower = name.lower()
    return lower.endswith(SUPPORTED) or mime in {
        "application/zip", "application/x-gzip",
        "application/x-7z-compressed", "application/x-rar-compressed",
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    manifest = json.loads(Path(args.manifest).read_text())
    source_dir = Path(args.input_dir)
    if not source_dir.is_dir():
        raise SystemExit("archive input directory does not exist")
    expected = {
        item["title"]: {
            "drive_file_id": item["id"],
            "expected_bytes": int(item.get("size_bytes") or 0),
            "parent_folder_id": item.get("parent_folder_id"),
        }
        for item in manifest.get("files", [])
        if is_archive(item.get("title") or "", item.get("mime_type"))
    }
    delivered_paths = [
        path for path in source_dir.iterdir()
        if path.is_file() and path.name.lower().endswith(SUPPORTED)
    ]
    delivered_names = {path.name for path in delivered_paths}
    missing = sorted(set(expected) - delivered_names)
    unexpected = sorted(delivered_names - set(expected))
    if missing or unexpected:
        raise SystemExit(f"archive set mismatch: missing={missing}, unexpected={unexpected}")
    records = []
    for path in sorted(delivered_paths):
        digest, actual_bytes = sha256_file(path)
        source = expected[path.name]
        if actual_bytes != source["expected_bytes"]:
            raise SystemExit(
                f"archive byte mismatch: {path.name}: expected={source['expected_bytes']} actual={actual_bytes}"
            )
        records.append({
            **source,
            "file_name": path.name,
            "actual_bytes": actual_bytes,
            "sha256": digest,
        })
    result = {
        "schema_version": 1,
        "status": "succeeded",
        "classification": "REAL",
        "action": "VERIFY_PRIVATE_ARCHIVE_DELIVERY",
        "manifest_sha256": hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest(),
        "archive_count": len(records),
        "archive_bytes": sum(x["actual_bytes"] for x in records),
        "records": records,
        "source_mutation": "NONE",
    }
    if result["archive_count"] != int(manifest.get("archive_count") or 0):
        raise SystemExit("manifest archive count does not reconcile")
    if result["archive_bytes"] != int(manifest.get("archive_bytes") or 0):
        raise SystemExit("manifest archive bytes do not reconcile")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
