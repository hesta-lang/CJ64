#!/usr/bin/env python3
"""Normalize and preflight a CJ DynOS actor before building its install ZIP.

SM64CoopDX parses the exported C sources and generates the actor .bin when
the mod is refreshed. This script therefore validates those C sources and
their texture paths; it does not attempt to synthesize a DynOS binary.
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
    if len(sys.argv) not in (3, 5):
        raise SystemExit(
            "usage: fix_cj_dynos_texture_paths.py <mod_root> <output_dir> "
            "[archive_name report_name]"
        )

    mod_root = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve()
    archive_name = sys.argv[3] if len(sys.argv) == 5 else "CJ64-Model-Test.zip"
    report_name = sys.argv[4] if len(sys.argv) == 5 else "cj_model_test_report.json"
    package_root = mod_root.name
    actor_dir = mod_root / "actors" / "cj"
    model_file = actor_dir / "model.inc.c"
    geo_file = actor_dir / "geo.inc.c"
    header_file = actor_dir / "geo_header.h"
    report_file = output_dir / report_name
    expected_geo_name = "cj64_cj_geo"

    require(mod_root.is_dir(), f"Mod folder not found: {mod_root}")
    require(actor_dir.is_dir(), f"CJ actor folder not found: {actor_dir}")
    for path in (model_file, geo_file, header_file, report_file):
        require(path.is_file(), f"Missing required file: {path}")

    # Normalize image names without changing the pixel data.
    renamed: dict[str, str] = {}
    for path in sorted(actor_dir.glob("*.png")):
        safe_name = re.sub(r"\\s+", "_", path.name)
        if safe_name == path.name:
            continue
        target = path.with_name(safe_name)
        require(not target.exists(), f"Refusing to overwrite {target}")
        path.rename(target)
        renamed[path.name] = target.name

    # DynOS tokenizes C source by whitespace. Normalize all texture include
    # literals, including palette placeholders. Only .inc.c includes resolve
    # to PNG files; .pal entries are empty palette placeholders in DynOS.
    source = model_file.read_text(encoding="utf-8")
    include_pattern = re.compile(r'(?m)(#include\\s+")([^"\\r\\n]+)(")')
    includes: list[str] = []
    palettes: list[str] = []

    def rewrite(match: re.Match[str]) -> str:
        original_path = match.group(2)
        if not (original_path.endswith(".inc.c") or original_path.endswith(".pal")):
            return match.group(0)
        normalized_path = re.sub(r"\\s+", "_", original_path)
        if normalized_path.endswith(".inc.c"):
            includes.append(normalized_path)
        else:
            palettes.append(normalized_path)
        return match.group(1) + normalized_path + match.group(3)

    updated_source = include_pattern.sub(rewrite, source)
    require(includes, "No DynOS texture .inc.c include paths found in model.inc.c")
    model_file.write_text(updated_source, encoding="utf-8")

    checked: list[str] = []
    for include in includes:
        require(not any(ch.isspace() for ch in include), f"Whitespace remains in texture include: {include}")
        require(include.startswith("actors/cj/"), f"Unexpected actor texture path: {include}")
        png_rel = include[:-6] + ".png"
        png_path = mod_root / png_rel
        require(png_path.is_file(), f"DynOS cannot resolve texture PNG: {png_path}")
        checked.append(png_rel)

    for palette in palettes:
        require(not any(ch.isspace() for ch in palette), f"Whitespace remains in palette placeholder: {palette}")
        require(palette.startswith("actors/cj/"), f"Unexpected palette path: {palette}")

    geo_source = geo_file.read_text(encoding="utf-8")
    geo_header = header_file.read_text(encoding="utf-8")
    require(
        re.search(r"\\bGeoLayout\\s+" + re.escape(expected_geo_name) + r"\\s*\\[\\s*\\]", geo_source),
        f"Missing root GeoLayout {expected_geo_name} in geo.inc.c",
    )
    require(
        f"extern const GeoLayout {expected_geo_name}[];" in geo_header,
        f"Missing root GeoLayout declaration {expected_geo_name} in geo_header.h",
    )
    require(
        re.search(r"\\bGeoLayout\\s+cj_geo\\s*\\[", geo_source) is None,
        "Generic cj_geo root still exists; DynOS name was not namespaced",
    )

    # A stale binary can cause DynOS to skip rebuilding. The game, not this
    # CI script, is responsible for generating the .bin from C sources.
    removed_bins = []
    for binary in mod_root.rglob("*.bin"):
        removed_bins.append(str(binary.relative_to(mod_root)))
        binary.unlink()

    report = json.loads(report_file.read_text(encoding="utf-8"))
    report["status"] = "DYNOS_SOURCE_PREFLIGHT_PASSED_NOT_TESTED_IN_GAME"
    report["dynos_geolayout_name"] = expected_geo_name
    report["dynos_binary_generation"] = "SM64CoopDX generates actors/cj64_cj_geo.bin on mod refresh"
    report["removed_stale_binary_files"] = removed_bins
    report["renamed_texture_files"] = renamed
    report["dynos_texture_includes"] = checked
    report["dynos_palette_placeholders"] = palettes
    report["actor_files"] = [
        {"path": str(path.relative_to(mod_root)), "size": path.stat().st_size}
        for path in sorted(actor_dir.rglob("*"))
        if path.is_file()
    ]
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    archive = output_dir / archive_name
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=8) as zf:
        for path in sorted(mod_root.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(mod_root.parent))

    with zipfile.ZipFile(archive, "r") as zf:
        members = set(zf.namelist())
        for include in checked:
            expected = f"{package_root}/{include}"
            require(expected in members, f"ZIP is missing DynOS texture: {expected}")
        required = (
            f"{package_root}/actors/cj/model.inc.c",
            f"{package_root}/actors/cj/geo.inc.c",
            f"{package_root}/actors/cj/geo_header.h",
            f"{package_root}/character.lua",
            f"{package_root}/main.lua",
            f"{package_root}/rigged_actor.lua",
        )
        for entry in required:
            require(entry in members, f"ZIP is missing required file: {entry}")
        require(
            not any(name.endswith(".bin") for name in members),
            "A stale/precompiled DynOS .bin leaked into the installation ZIP",
        )
        with zf.open(f"{package_root}/actors/cj/geo.inc.c") as fh:
            zipped_geo = fh.read().decode("utf-8")
        require(expected_geo_name in zipped_geo, "ZIP contains wrong DynOS root GeoLayout")

    print(json.dumps({
        "archive": str(archive),
        "renamed_texture_files": renamed,
        "dynos_root": expected_geo_name,
        "texture_includes_verified": len(checked),
        "palette_placeholders_normalized": len(palettes),
        "stale_binary_files_removed": removed_bins,
        "archive_bytes": archive.stat().st_size,
        "status": report["status"],
    }, indent=2))


if __name__ == "__main__":
    main()
