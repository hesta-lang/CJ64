#!/usr/bin/env python3
"""Build preview Actions on the uploaded CJ FBX armature.

Requires Blender 3.6 LTS. Example:
  blender --background --python tools/import_cj_ifp_actions_blender.py -- \
    assets/cj/source/CarlJohnson-GTASA.FBX /path/to/ped.ifp cj_ifp_preview.blend

This is deliberately a source-rig preview, not an SM64CoopDX conversion. The
local quaternion/axis convention must be visually checked before retargeting.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import bpy  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from ifp_reader import IFPError, load_ifp  # noqa: E402


def arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fbx", type=Path)
    parser.add_argument("ifp", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--clips", default="", help="comma-separated clip names; default: manifest")
    parser.add_argument("--apply-translations", action="store_true",
                        help="apply IFP type-4 location tracks; normally keep disabled")
    parser.add_argument("--translation-scale", type=float, default=1.0)
    parser.add_argument("--report", type=Path, default=None)
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def manifest_names() -> list[str]:
    data = json.loads((ROOT / "tools" / "cj_animation_manifest.json").read_text(encoding="utf-8"))
    return [entry["name"] for entry in data["clips"]]


def main() -> int:
    args = arguments()
    if args.fps <= 0:
        raise SystemExit("--fps must be positive")
    if not args.fbx.is_file() or not args.ifp.is_file():
        raise SystemExit("Both FBX and ped.ifp files must exist")

    try:
        package = load_ifp(str(args.ifp))
    except (OSError, IFPError) as exc:
        raise SystemExit(f"Could not parse ped.ifp: {exc}") from exc

    bone_map = json.loads((ROOT / "tools" / "cj_fbx_bone_map.json").read_text(encoding="utf-8"))
    remap = {name.strip().casefold(): target for name, target in bone_map["ifp_to_fbx"].items()}
    intentional = {name.strip().casefold() for name in bone_map.get("intentionally_unmapped_ifp_tracks", {})}
    requested = [name.strip() for name in args.clips.split(",") if name.strip()] or manifest_names()
    selected = []
    missing = []
    for name in requested:
        clip = package.find(name)
        if clip is None:
            missing.append(name)
        else:
            selected.append(clip)
    if missing:
        raise SystemExit("Missing IFP clips: " + ", ".join(missing))

    clear_scene()
    bpy.ops.import_scene.fbx(
        filepath=str(args.fbx), use_anim=False, automatic_bone_orientation=False
    )
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(armatures) != 1:
        raise SystemExit(f"Expected one imported CJ armature; found {len(armatures)}")

    armature = armatures[0]
    armature.data.pose_position = "POSE"
    available = set(armature.data.bones.keys())
    scene = bpy.context.scene
    scene.render.fps = args.fps
    scene.render.fps_base = 1.0

    report = {
        "format": "cj64-source-rig-preview-v1",
        "source_package": package.package_name,
        "source_ifp": args.ifp.name,
        "source_fbx": args.fbx.name,
        "fps": args.fps,
        "translations_applied": bool(args.apply_translations),
        "warning": "Not retargeted to Mario Armature; not game-ready. Validate rest pose and axes visually.",
        "actions": [],
    }

    for clip in selected:
        action = bpy.data.actions.new(name=f"cj_ifp__{clip.name}")
        armature.animation_data_create()
        armature.animation_data.action = action
        mapped = 0
        ignored = []
        for track in clip.bones:
            target = remap.get(track.name.strip().casefold())
            if target is None:
                if track.name.strip().casefold() not in intentional:
                    ignored.append(track.name)
                continue
            if target not in available:
                raise SystemExit(f"FBX joint missing: {track.name!r} -> {target!r}")
            pose_bone = armature.pose.bones[target]
            pose_bone.rotation_mode = "QUATERNION"
            mapped += 1
            for key in track.frames:
                frame = 1.0 + key.time_seconds * args.fps
                x, y, z, w = key.rotation_xyzw
                pose_bone.rotation_quaternion = (w, x, y, z)
                pose_bone.keyframe_insert(
                    data_path="rotation_quaternion", frame=frame, group=target
                )
                if args.apply_translations and key.translation is not None:
                    pose_bone.location = tuple(
                        value * args.translation_scale for value in key.translation
                    )
                    pose_bone.keyframe_insert(data_path="location", frame=frame, group=target)
        for curve in action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"
        action.use_fake_user = True
        report["actions"].append({
            "name": action.name,
            "duration_seconds": clip.duration,
            "ifp_tracks": len(clip.bones),
            "mapped_tracks": mapped,
            "ignored_tracks": ignored,
            "frame_range": [float(action.frame_range[0]), float(action.frame_range[1])],
        })

    if report["actions"]:
        scene.frame_start = 1
        scene.frame_end = max(int(round(item["frame_range"][1])) for item in report["actions"])
        armature.animation_data.action = bpy.data.actions.get(report["actions"][0]["name"])

    bpy.data.texts.new("CJ64_IFP_IMPORT_REPORT.json").write(json.dumps(report, indent=2))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
