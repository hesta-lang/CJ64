#!/usr/bin/env python3
"""Embed the generated CJ actor source into the Lua mod and build its install ZIP.

SM64CoopDX scans each mod's actors/ directory, generates its actor binary there,
and registers that binary as a custom actor owned by the same mod. This script
validates the source tree and creates a single-folder mod installation archive.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import zipfile
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def add_tree(zf: zipfile.ZipFile, root: Path, archive_prefix: str) -> None:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            zf.write(path, f"{archive_prefix}/{path.relative_to(root).as_posix()}")


def main() -> None:
    if len(sys.argv) not in (4, 5):
        raise SystemExit(
            "usage: fix_cj_dynos_texture_paths.py <lua_mod_root> <actor_source_root> "
            "<output_dir> [report_name]"
        )

    mod_root = Path(sys.argv[1]).resolve()
    pack_root = Path(sys.argv[2]).resolve()
    output_dir = Path(sys.argv[3]).resolve()
    report_name = sys.argv[4] if len(sys.argv) == 5 else "cj64_rig_transfer_report.json"
    report_file = output_dir / report_name
    package_root = mod_root.name
    pack_name = pack_root.name
    actor_dir = pack_root / "Assets"
    mod_actor_dir = mod_root / "actors"
    mod_actor_assets_dir = mod_actor_dir / "Assets"
    model_file = actor_dir / "model.inc.c"
    geo_file = actor_dir / "geo.inc.c"
    header_file = actor_dir / "geo_header.h"
    expected_geo_name = "mario_geo"

    require(mod_root.is_dir(), f"Lua mod folder not found: {mod_root}")
    require(pack_root.is_dir(), f"Actor source staging folder not found: {pack_root}")
    require(pack_name == "CJ64", f"Actor source staging folder must be named CJ64, got {pack_name}")
    require(actor_dir.is_dir(), f"DynOS actor source folder not found: {actor_dir}")
    for path in (model_file, geo_file, header_file, report_file):
        require(path.is_file(), f"Missing required file: {path}")
    for path in (mod_root / "main.lua", mod_root / "character.lua", mod_root / "rigged_actor.lua"):
        require(path.is_file(), f"Missing required Lua mod file: {path}")

    # Normalize image names without changing pixels.
    renamed: dict[str, str] = {}
    for path in sorted(actor_dir.glob("*.png")):
        safe_name = re.sub(r"\s+", "_", path.name)
        if safe_name == path.name:
            continue
        target = path.with_name(safe_name)
        require(not target.exists(), f"Refusing to overwrite {target}")
        path.rename(target)
        renamed[path.name] = target.name

    # The actor-source compiler resolves texture includes from its actor root. Fast64 therefore
    # emits Assets/<texture>.inc.c for this pack layout.
    source = model_file.read_text(encoding="utf-8")
    include_pattern = re.compile(r'(?m)(#include\s+")([^"\r\n]+)(")')
    includes: list[str] = []
    palettes: list[str] = []

    def rewrite(match: re.Match[str]) -> str:
        original_path = match.group(2)
        if not (original_path.endswith(".inc.c") or original_path.endswith(".pal")):
            return match.group(0)
        normalized_path = re.sub(r"\s+", "_", original_path)
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
        require(include.startswith("Assets/"), f"Unexpected DynOS pack texture path: {include}")
        png_rel = include[:-6] + ".png"
        png_path = pack_root / png_rel
        require(png_path.is_file(), f"DynOS cannot resolve texture PNG: {png_path}")
        checked.append(png_rel)

    for palette in palettes:
        require(not any(ch.isspace() for ch in palette), f"Whitespace remains in palette placeholder: {palette}")
        require(palette.startswith("Assets/"), f"Unexpected DynOS palette path: {palette}")

    geo_source = geo_file.read_text(encoding="utf-8")
    geo_header = header_file.read_text(encoding="utf-8")

    # Fast64-Gart can emit empty CUSTOM_CMD() placeholders for custom GeoLayout
    # commands that have no preset. SM64CoopDX's DynOS parser does not recognize
    # this symbol and aborts actor generation with "Unknown geo symbol".
    # These empty placeholders carry no GeoLayout arguments or geometry, so
    # remove the standalone calls while preserving the surrounding node tree.
    unsupported_custom_geo_commands_removed = len(
        re.findall(r"(?m)^[ \t]*CUSTOM_CMD\s*\(\s*\)\s*,[ \t]*(?:\r?\n|$)", geo_source)
    )
    geo_source = re.sub(
        r"(?m)^[ \t]*CUSTOM_CMD\s*\(\s*\)\s*,[ \t]*(?:\r?\n|$)",
        "",
        geo_source,
    )
    require(
        "CUSTOM_CMD" not in geo_source,
        "Unsupported CUSTOM_CMD placeholder remains in geo.inc.c",
    )

    # Fast64 exports the stock Mario actor with a 0.25 root scale (16384).
    # That factor is appropriate for Nintendo's original Mario mesh, whose
    # source dimensions are four times larger than the SM64 target space.
    # CJ has already been normalized to 280 SM64 units before export, so
    # retaining 0.25 shrinks it to 70 units in game. Promote only the root
    # GeoLayout scale to 1.0; leave hand/foot animation scales untouched.
    root_scale_pattern = re.compile(
        r"(GEO_SCALE\s*\(\s*LAYER_FORCE\s*,\s*)16384(\s*\))"
    )
    root_scale_matches = list(root_scale_pattern.finditer(geo_source))
    require(len(root_scale_matches) == 1,
            f"Expected exactly one stock Mario root scale 16384, found {len(root_scale_matches)}")
    geo_source = root_scale_pattern.sub(r"\g<1>65536\g<2>", geo_source, count=1)
    require(
        re.search(r"GEO_SCALE\s*\(\s*LAYER_FORCE\s*,\s*65536\s*\)", geo_source),
        "CJ root GeoLayout scale was not normalized to 1.0",
    )
    geo_file.write_text(geo_source, encoding="utf-8")
    require(
        re.search(r"\bGeoLayout\s+" + re.escape(expected_geo_name) + r"\s*\[\s*\]", geo_source),
        f"Missing root GeoLayout {expected_geo_name} in geo.inc.c",
    )
    require(
        f"extern const GeoLayout {expected_geo_name}[];" in geo_header,
        f"Missing root GeoLayout declaration {expected_geo_name} in geo_header.h",
    )
    require(
        re.search(r"\bGeoLayout\s+cj_geo\s*\[", geo_source) is None,
        "Generic cj_geo root still exists; DynOS name was not namespaced",
    )

    # Embed the actor source tree inside this mod. CoopDX scans <mod>/actors
    # at startup, generates actors/mario_geo.bin there, and registers it as a
    # custom actor owned by this mod.
    mod_actor_dir.mkdir(parents=True, exist_ok=True)
    if mod_actor_assets_dir.exists():
        shutil.rmtree(mod_actor_assets_dir)
    shutil.copytree(actor_dir, mod_actor_assets_dir)
    require((mod_actor_assets_dir / "model.inc.c").is_file(),
            "Embedded actor is missing model.inc.c")
    require((mod_actor_assets_dir / "geo.inc.c").is_file(),
            "Embedded actor is missing geo.inc.c")
    require(len(list(mod_actor_assets_dir.glob("*.png"))) >= 40,
            "Embedded actor is missing its texture PNGs")

    # CoopDX generates the actor binary in this mod's actors/ folder.
    generated_binary = mod_actor_dir / f"{expected_geo_name}.bin"
    if generated_binary.exists():
        generated_binary.unlink()

    (mod_root / "README-INSTALL.txt").write_text(
        "CJ64 is a self-contained SM64CoopDX mod. Install only this folder in mods/. "
        "Its model sources and textures are embedded in actors/Assets. At startup, "
        "SM64CoopDX generates actors/mario_geo.bin inside this mod and registers it "
        "automatically. No separate DynOS pack installation is required.\n",
        encoding="utf-8",
    )

    report = json.loads(report_file.read_text(encoding="utf-8"))
    report["status"] = "DYNOS_PACK_SOURCE_PREFLIGHT_PASSED_NOT_TESTED_IN_GAME"
    report["dynos_geolayout_name"] = expected_geo_name
    report["dynos_pack_name"] = "CJ64"
    report["dynos_pack_install_path"] = "dynos/packs/CJ64"
    report["dynos_binary_generation"] = "SM64CoopDX DynOS_Gfx_Init generates CJ64/mario_geo.bin on startup"
    report["unsupported_custom_geo_commands_removed"] = unsupported_custom_geo_commands_removed
    report["unsupported_custom_geo_commands_remaining"] = geo_source.count("CUSTOM_CMD")
    report["root_geolayout_scale"] = 1.0
    report["root_geolayout_scale_fixed_from"] = 0.25
    report["renamed_texture_files"] = renamed
    report["dynos_texture_includes"] = checked
    report["dynos_palette_placeholders"] = palettes
    report["actor_files"] = [
        {"path": str(path.relative_to(pack_root)), "size": path.stat().st_size}
        for path in sorted(actor_dir.rglob("*"))
        if path.is_file()
    ]
    report["lua_mod_files"] = [
        {"path": str(path.relative_to(mod_root)), "size": path.stat().st_size}
        for path in sorted(mod_root.rglob("*"))
        if path.is_file()
    ]
    report = json.loads(report_file.read_text(encoding="utf-8"))
    report["status"] = "MOD_EMBEDDED_DYNOS_ACTOR_SOURCE_PREFLIGHT_PASSED_NOT_TESTED_IN_GAME"
    report["dynos_geolayout_name"] = expected_geo_name
    report["dynos_pack_name"] = None
    report["dynos_pack_install_path"] = None
    report["dynos_pack_actor_folder"] = None
    report["dynos_actor_install_path"] = "mods/CJ64-Rigged-Test/actors"
    report["dynos_binary_generation"] = "SM64CoopDX DynOS_Gfx_GenerateModPacks generates actors/mario_geo.bin inside this mod at startup"
    report["actor_is_embedded_in_mod"] = True
    report["unsupported_custom_geo_commands_removed"] = unsupported_custom_geo_commands_removed
    report["unsupported_custom_geo_commands_remaining"] = geo_source.count("CUSTOM_CMD")
    report["root_geolayout_scale"] = 1.0
    report["root_geolayout_scale_fixed_from"] = 0.25
    report["renamed_texture_files"] = renamed
    report["dynos_texture_includes"] = checked
    report["dynos_palette_placeholders"] = palettes
    report["actor_files"] = [
        {"path": str(path.relative_to(mod_actor_dir)), "size": path.stat().st_size}
        for path in sorted(mod_actor_assets_dir.rglob("*"))
        if path.is_file()
    ]
    report["lua_mod_files"] = [
        {"path": str(path.relative_to(mod_root)), "size": path.stat().st_size}
        for path in sorted(mod_root.rglob("*"))
        if path.is_file()
    ]
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    mod_archive = output_dir / "CJ64-Rigged-Test.zip"
    install_archive = output_dir / "CJ64-Install-Package.zip"
    for archive in (mod_archive, install_archive):
        if archive.exists():
            archive.unlink()

    with zipfile.ZipFile(mod_archive, "w", zipfile.ZIP_DEFLATED, compresslevel=8) as zf:
        add_tree(zf, mod_root, package_root)
    with zipfile.ZipFile(install_archive, "w", zipfile.ZIP_DEFLATED, compresslevel=8) as zf:
        add_tree(zf, mod_root, "mods/CJ64-Rigged-Test")

    with zipfile.ZipFile(install_archive, "r") as zf:
        members = set(zf.namelist())
        required = (
            "mods/CJ64-Rigged-Test/main.lua",
            "mods/CJ64-Rigged-Test/character.lua",
            "mods/CJ64-Rigged-Test/rigged_actor.lua",
            "mods/CJ64-Rigged-Test/actors/Assets/model.inc.c",
            "mods/CJ64-Rigged-Test/actors/Assets/geo.inc.c",
            "mods/CJ64-Rigged-Test/actors/Assets/geo_header.h",
            "mods/CJ64-Rigged-Test/README-INSTALL.txt",
        )
        for rel in required:
            require(rel in members, f"Install archive is missing {rel}")
        for include in checked:
            expected = f"mods/CJ64-Rigged-Test/actors/{include}"
            require(expected in members, f"Install archive is missing embedded texture {expected}")
        require(
            not any(name.startswith("dynos/packs/") for name in members),
            "Install archive must not contain a separate DynOS pack folder",
        )
        require(
            not any(name.endswith(".bin") for name in members),
            "A precompiled actor .bin leaked into the archive; CoopDX generates it inside the mod",
        )
        with zf.open("mods/CJ64-Rigged-Test/character.lua") as fh:
            lua_source = fh.read().decode("utf-8")
        require('modelName = "mario_geo"' in lua_source,
                "Lua controller must request the embedded actor by GeoLayout name")
        require("dynos_pack_" not in lua_source,
                "Lua controller still depends on external DynOS pack APIs")
        with zf.open("mods/CJ64-Rigged-Test/actors/Assets/geo.inc.c") as fh:
            zipped_geo = fh.read().decode("utf-8")
        require(expected_geo_name in zipped_geo, "Install archive contains wrong GeoLayout root")
        require("CUSTOM_CMD" not in zipped_geo, "Install archive still contains unsupported CUSTOM_CMD placeholders")
        require(
            re.search(r"GEO_SCALE\s*\(\s*LAYER_FORCE\s*,\s*65536\s*\)", zipped_geo),
            "Install archive still has the stock 0.25 Mario root scale",
        )

    print(json.dumps({
        "install_archive": str(install_archive),
        "lua_mod_archive": str(mod_archive),
        "dynos_root": expected_geo_name,
        "actor_is_embedded_in_mod": True,
        "actor_install_path": "mods/CJ64-Rigged-Test/actors/Assets",
        "texture_includes_verified": len(checked),
        "palette_placeholders_normalized": len(palettes),
        "unsupported_custom_geo_commands_removed": unsupported_custom_geo_commands_removed,
        "root_geolayout_scale": 1.0,
        "renamed_texture_files": renamed,
        "install_archive_bytes": install_archive.stat().st_size,
        "status": report["status"],
    }, indent=2))

if __name__ == "__main__":
    main()
