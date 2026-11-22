#!/usr/bin/env python3
"""Normalize CJ DynOS texture filenames and rebuild the install ZIP.

SM64CoopDX's DynOS source tokenizer removes whitespace inside tokens. Any
texture path containing spaces therefore becomes a different filename at
runtime. This post-export step replaces spaces in PNG filenames and updates
model.inc.c include references before packaging.
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: fix_cj_dynos_texture_paths.py <mod_root> <output_dir>")

    mod_root = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve()
    actor_dir = mod_root / "actors" / "cj"
    model_file = actor_dir / "model.inc.c"
    report_file = output_dir / "cj_model_test_report.json"

    require(mod_root.is_dir(), f"Mod folder not found: {mod_root}")
    require(actor_dir.is_dir(), f"CJ actor folder not found: {actor_dir}")
    require(model_file.is_file(), f"Missing {model_file}")
    require(report_file.is_file(), f"Missing {report_file}")

    # Rename PNGs with whitespace. The texture payload itself is unchanged.
    renamed: dict[str, str] = {}
    for path in sorted(actor_dir.glob("*.png")):
        safe_name = re.sub(r"\\s+", "_", path.name)
        if safe_name == path.name:
            continue
        target = path.with_name(safe_name)
        require(not target.exists(), f"Refusing to overwrite {target}")
        path.rename(target)
        renamed[path.name] = target.name

    # Update DynOS include paths but preserve C symbol names.
    source = model_file.read_text(encoding="utf-8")
    include_pattern = re.compile(r'(?m)(#include\\s+")([^"\\r\\n]+)(\\.inc\\.c")')
    includes: list[str] = []

    def rewrite(match: re.Match[str]) -> str:
        normalized_path = re.sub(r"\\s+", "_", match.group(2))
        includes.append(normalized_path)
        return match.group(1) + normalized_path + match.group(3)

    updated_source = include_pattern.sub(rewrite, source)
    require(includes, "No DynOS texture include paths found in model.inc.c")
    model_file.write_text(updated_source, encoding="utf-8")

    # DynOS resolves each #include by appending .png to the path before .inc.c.
    checked: list[str] = []
    for include in includes:
        require(not any(ch.isspace() for ch in include), f"Whitespace remains in include: {include}")
        require(include.startswith("actors/"), f"Unexpected actor texture path: {include}")
        png_path = mod_root / (include + ".png")
        require(png_path.is_file(), f"DynOS cannot resolve texture PNG: {png_path}")
        checked.append(str(png_path.relative_to(mod_root)))

    # Refresh the report so it describes the final archive, not the pre-fix export.
    report = json.loads(report_file.read_text(encoding="utf-8"))
    report["status"] = "EXPORTED_TEXTURE_PATHS_NORMALIZED_NOT_TESTED_IN_GAME"
    report["renamed_texture_files"] = renamed
    report["dynos_texture_includes"] = checked
    report["actor_files"] = [
        {"path": str(path.relative_to(mod_root)), "size": path.stat().st_size}
        for path in sorted(actor_dir.rglob("*"))
        if path.is_file()
    ]
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    archive = output_dir / "CJ64-Model-Test.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=8) as zf:
        for path in sorted(mod_root.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(mod_root.parent))

    # Verify the actual ZIP entries and every PNG lookup after packaging.
    with zipfile.ZipFile(archive, "r") as zf:
        members = set(zf.namelist())
        for include in includes:
            expected = f"CJ64-Model-Test/{include}.png"
            require(expected in members, f"ZIP is missing DynOS texture: {expected}")
        required = (
            "CJ64-Model-Test/actors/cj/model.inc.c",
            "CJ64-Model-Test/actors/cj/geo.inc.c",
            "CJ64-Model-Test/character.lua",
        )
        for entry in required:
            require(entry in members, f"ZIP is missing required file: {entry}")

    print(json.dumps({
        "archive": str(archive),
        "renamed": renamed,
        "texture_includes_verified": checked,
        "archive_bytes": archive.stat().st_size,
        "status": report["status"],
    }, indent=2))


if __name__ == "__main__":
    main()
