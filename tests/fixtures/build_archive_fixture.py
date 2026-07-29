#!/usr/bin/env python3
import argparse
import zipfile
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--output", required=True)
args = ap.parse_args()
out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(out / "bank-a.zip", "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("FY2425/statement-01.txt", b"fixture statement one\n")
    zf.writestr("FY2425/shared.txt", b"fixture duplicate\n")
with zipfile.ZipFile(out / "bank-b.zip", "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("FY2425/statement-02.txt", b"fixture statement two\n")
    zf.writestr("FY2425/shared-copy.txt", b"fixture duplicate\n")
