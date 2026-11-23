#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "actors" / "cj" / "[CS] Carl Johnson.zip"
OUT = ROOT / "build" / "cs-cj-dynos"
EXTRACTED = OUT / "extracted"
OUT.mkdir(parents=True, exist_ok=True)

if not SOURCE.is_file():
    raise SystemExit(f"Missing source archive: {SOURCE}")

if EXTRACTED.exists():
    shutil.rmtree(EXTRACTED)
EXTRACTED.mkdir(parents=True)

with zipfile.ZipFile(SOURCE) as zf:
    bad = zf.testzip()
    if bad:
        raise SystemExit(f"Corrupt entry in source archive: {bad}")
    entries = [i for i in zf.infolist() if not i.is_dir()]
    zf.extractall(EXTRACTED)

def rel(p: Path) -> str:
    return p.relative_to(EXTRACTED).as_posix()

files = sorted(p for p in EXTRACTED.rglob("*") if p.is_file())
dynos_bins = [p for p in files if p.suffix.lower() == ".bin"]
model_sources = [p for p in files if p.name.lower() in {
    "model.inc.c", "geo.inc.c", "geo_header.h", "model.h"
} or p.suffix.lower() in {".inc.c", ".geo.c"}]
textures = [p for p in files if p.suffix.lower() in {
    ".png", ".jpg", ".jpeg", ".bmp", ".tga"
}]

rows = [
    "# CJ Character Select DynOS extraction",
    "",
    f"Original archive: {SOURCE.name}",
    f"Archive entries: {len(entries)}",
    f"Extracted files: {len(files)}",
    f"DynOS .bin files: {len(dynos_bins)}",
    f"Source/include files: {len(model_sources)}",
    f"Image files: {len(textures)}",
    "",
    "## DynOS binaries",
]
rows += [f"- {rel(p)} ({p.stat().st_size} bytes)" for p in dynos_bins] or ["- None found"]
rows += ["", "## Model source files"]
rows += [f"- {rel(p)} ({p.stat().st_size} bytes)" for p in model_sources] or ["- None found"]
rows += ["", "## Image files"]
rows += [f"- {rel(p)} ({p.stat().st_size} bytes)" for p in textures] or ["- None found"]
rows += ["", "## Complete archive listing"]
rows += [f"- {rel(p)} ({p.stat().st_size} bytes)" for p in files]
(OUT / "MANIFEST.md").write_text("\n".join(rows) + "\n", encoding="utf-8")

# Keep the original folder layout intact for DynOS include and texture paths.
package = ROOT / "build" / "CS-CJ-Dynos-Extracted.zip"
if package.exists():
    package.unlink()
with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for p in files:
        zf.write(p, Path("CS-CJ-Dynos") / p.relative_to(EXTRACTED))

summary = {
    "source_archive": SOURCE.name,
    "archive_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    "extracted_files": len(files),
    "dynos_bins": [rel(p) for p in dynos_bins],
    "model_sources": [rel(p) for p in model_sources],
    "textures": len(textures),
    "package": str(package.relative_to(ROOT)),
    "package_bytes": package.stat().st_size,
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
