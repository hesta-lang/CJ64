#!/usr/bin/env python3
"""Build an experimental CJ64 mod on the FBX rest rig, without Mario pose overlays."""
from __future__ import annotations
import argparse
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rebase_gta_animation_rest_pose import rebase  # noqa: E402

PACKAGE_NAME = "CJ64-GTA-SourceRest-Test"
VERSION = "0.3.0-alpha"
REMOVE_GEO_CALLBACKS = (
    "geo_mario_tilt_torso",
    "geo_mario_head_rotation",
    "geo_mario_hand_foot_scaler",
    "geo_mario_rotate_wing_cap_wings",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def patch_geo_layout(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    counts = {}
    for callback in REMOVE_GEO_CALLBACKS:
        pattern = re.compile(
            rf"(?m)^[ \t]*GEO_ASM\(\s*\d+\s*,\s*{re.escape(callback)}\s*\)\s*,[ \t]*(?:\r?\n|$)"
        )
        source, count = pattern.subn("", source)
        counts[callback] = count
        require(count > 0, f"Expected at least one Mario pose callback to remove: {callback}")
        require(callback not in source, f"Mario pose callback remains in GeoLayout: {callback}")
    # This callback only carries a player when attached to another object.
    # Keep it; it does not add a Mario joint pose to CJ's GTA animation.
    require("GEO_ASM(0, geo_move_mario_part_from_parent)" in source,
            "Player parent-transform hook disappeared unexpectedly")
    path.write_text(source, encoding="utf-8")
    return {
        "removed_mario_geo_callbacks": counts,
        "preserved_geo_move_mario_part_from_parent": True,
    }


def configure_main(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    require('CJ64.version = "0.1.8-alpha"' in source, "Unexpected source-rest actor main.lua baseline")
    require("CJ64.useGTAAnimations = false" in source, "Expected GTA animations to be disabled in source baseline")
    source = source.replace('CJ64.name = "CJ64"', 'CJ64.name = "CJ64 GTA Source Rest"', 1)
    source = source.replace('CJ64.version = "0.1.8-alpha"', f'CJ64.version = "{VERSION}"', 1)
    source = source.replace("CJ64.csActor = true", "CJ64.csActor = false\nCJ64.sourceRestActor = true", 1)
    source = source.replace(
        "-- Use the original Character Select DynOS actor, which was confirmed in-game\n"
        "-- with native Mario animations. Do not substitute the experimental FBX export.\n"
        "-- GTA playback remains disabled until the CS actor local rotation basis is calibrated.\n"
        "CJ64.useGTAAnimations = false\n"
        "CJ64.animationTablesLoaded = false\n"
        'CJ64.animationStatus = "disabled_unverified_cs_node_order_and_rest_pose"',
        "-- This build uses the CJ FBX source-rest rig and rebased GTA local channels.\n"
        "-- It deliberately does not apply Mario anim_C5 as a pose anchor.\n"
        "CJ64.useGTAAnimations = true\n"
        "CJ64.animationTablesLoaded = false\n"
        'CJ64.animationStatus = "source_rest_gta_retarget_experimental"',
        1,
    )
    source = source.replace(
        'print("[CJ64] GTA clips disabled: using SM64CoopDX native player animations until the CS node order and rest pose are verified.")',
        'print("[CJ64] GTA source-rest animation retarget enabled (experimental).")',
        1,
    )
    require("CJ64.useGTAAnimations = true" in source, "Failed to enable GTA animation playback")
    require("CJ64_NATIVE_MARIO_IDLE_POSE_ANCHOR_APPLIED" not in source,
            "Mario idle pose anchor must not be loaded by main.lua")
    path.write_text(source, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor-zip", type=Path, required=True,
                        help="CJ64-Rigged-Test.zip from the successful rig-export workflow artifact")
    parser.add_argument("--map", type=Path, required=True,
                        help="dual-rest retarget map from the same rig-export artifact")
    parser.add_argument("--raw-lua", type=Path, required=True,
                        help="GTA animation tables before Mario idle-pose anchoring")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path, label in ((args.actor_zip, "actor ZIP"), (args.map, "retarget map"), (args.raw_lua, "raw animation Lua")):
        require(path.is_file(), f"{label} missing: {path}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="cj64-source-rest-") as tmp:
        work = Path(tmp)
        with zipfile.ZipFile(args.actor_zip) as archive:
            bad = archive.testzip()
            require(bad is None, f"Corrupt input actor archive member: {bad}")
            archive.extractall(work / "actor")
        candidates = [p for p in (work / "actor").rglob("*") if p.is_dir() and p.name == "CJ64-Rigged-Test"]
        require(len(candidates) == 1, f"Expected one CJ64-Rigged-Test actor folder, found {len(candidates)}")
        mod_root = candidates[0]
        assets = mod_root / "actors" / "Assets"
        for name in ("geo.inc.c", "model.inc.c", "geo_header.h"):
            require((assets / name).is_file(), f"Missing generated actor asset: {name}")
        require((mod_root / "rigged_actor.lua").is_file(), "Missing rigged_actor.lua")

        mapping = json.loads(args.map.read_text(encoding="utf-8"))
        output_lua, animation_report = rebase(
            args.raw_lua.read_text(encoding="utf-8"), args.map
        )
        (mod_root / "cj64_gta_animations.lua").write_text(output_lua, encoding="utf-8")
        geo_report = patch_geo_layout(assets / "geo.inc.c")
        configure_main(mod_root / "main.lua")
        character = mod_root / "character.lua"
        char_text = character.read_text(encoding="utf-8")
        char_text = char_text.replace(
            "-- CJ64: replace only Mario's rendered model with the CS DynOS CJ actor.\n"
            "-- Optional GTA clips are used only when main.lua successfully loads the calibrated table.\n",
            "-- CJ64: replace Mario's rendered model with the CJ FBX source-rest DynOS actor.\n"
            "-- GTA clips are rebased to the CJ rest frame; movement and physics stay native.\n",
            1,
        )
        character.write_text(char_text, encoding="utf-8")
        (mod_root / "README-INSTALL.txt").write_text(
            f"CJ64 {VERSION} - GTA San Andreas source-rest animation test\n\n"
            "Install this folder inside the SM64CoopDX mods/ directory.\n"
            "Disable/remove all older CJ64 test folders first.\n\n"
            "This build uses the FBX-derived CJ rest rig. Its GTA clips were mathematically\n"
            "rebased from the existing native-CS animation channels into the CJ rest frames.\n"
            "It does not compose Mario anim_C5 or another Mario animation as a base pose.\n"
            "Mario-only torso tilt, head rotation, hand/foot scaling and wing callbacks are\n"
            "removed from the actor GeoLayout. Player movement, collision and world heading\n"
            "remain controlled by SM64CoopDX. This is an experimental test and still needs\n"
            "visual validation in-game on Android.\n",
            encoding="utf-8",
        )

        require("CJ64_REBASED_TO_CJ_FBX_SOURCE_REST_V1" in output_lua, "Rebased animation marker missing")
        require("CJ64_NATIVE_MARIO_IDLE_POSE_ANCHOR_APPLIED" not in output_lua,
                "Native Mario pose anchor must not be present")
        require(animation_report["clip_count"] == 13,
                f"Expected 13 GTA clips, got {animation_report['clip_count']}")
        require(animation_report["max_quantized_global_delta_error_radians"] < 0.001,
                "Quantized rebase changed reconstructed global motion excessively")
        require(mapping.get("target_animation_node_count") == 20,
                "Source-rest map does not have 20 animated nodes")

        final_mod = args.output_dir / PACKAGE_NAME
        if final_mod.exists():
            shutil.rmtree(final_mod)
        shutil.copytree(mod_root, final_mod)

    report = {
        "format": "cj64-source-rest-gta-package-v1",
        "version": VERSION,
        "actor_source": "Fast64-Gart CJ FBX source-rest actor export",
        "animation_source": "existing GTA San Andreas IFP-derived raw retarget tables",
        "pose_reference": "CJ FBX source-rest joint frames",
        "native_mario_animation_pose_anchor": False,
        "removed_geo_callbacks": geo_report["removed_mario_geo_callbacks"],
        "preserved_player_parent_transform_hook": geo_report["preserved_geo_move_mario_part_from_parent"],
        "animation_rebase": animation_report,
        "status": "PACKAGE_STRUCTURALLY_VALIDATED_NOT_TESTED_IN_GAME",
    }
    report_path = args.output_dir / f"{PACKAGE_NAME}-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    zip_path = args.output_dir / f"{PACKAGE_NAME}-{VERSION}-install.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(final_mod.rglob("*")):
            if path.is_file():
                archive.write(path, f"{PACKAGE_NAME}/{path.relative_to(final_mod).as_posix()}")
    with zipfile.ZipFile(zip_path) as archive:
        require(archive.testzip() is None, "Output installation ZIP is corrupt")
        names = archive.namelist()
        require(any(name.endswith("/actors/Assets/geo.inc.c") for name in names), "Packaged GeoLayout is missing")
        require(any(name.endswith("/cj64_gta_animations.lua") for name in names), "Packaged GTA table is missing")
    print(json.dumps({
        "package": str(zip_path),
        "size_bytes": zip_path.stat().st_size,
        "clips": animation_report["clip_count"],
        "nodes": animation_report["target_node_count"],
        "max_quantized_global_delta_error_radians": animation_report["max_quantized_global_delta_error_radians"],
        "native_mario_animation_anchor": False,
        "removed_geo_callbacks": geo_report["removed_mario_geo_callbacks"],
        "status": report["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
