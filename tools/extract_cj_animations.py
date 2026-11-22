#!/usr/bin/env python3
"""Extract candidate player clips from a user-provided GTA:SA ped.ifp."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from ifp_reader import IFPError, load_ifp

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "cj_animation_manifest.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ifp", type=Path, help="ped.ifp from your own GTA San Andreas installation")
    ap.add_argument("-o", "--output", type=Path, default=Path("cj_original_animations.json"))
    ap.add_argument("--list", action="store_true", help="list every animation and exit")
    args = ap.parse_args()
    try:
        package = load_ifp(str(args.ifp))
    except (OSError, IFPError) as exc:
        ap.error(str(exc))

    if args.list:
        for clip in package.animations:
            print(f"{clip.name}\t{len(clip.bones)} bones\t{clip.duration:.3f}s")
        return 0

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    selected, missing = [], []
    for requested in manifest["clips"]:
        clip = package.find(requested["name"])
        if clip is None:
            missing.append(requested["name"])
            continue
        selected.append({
            "name": clip.name,
            "role": requested["role"],
            "loop": requested["loop"],
            "duration_seconds": clip.duration,
            "bones": [{
                "name": track.name,
                "bone_id": track.bone_id,
                "keyframe_type": track.keyframe_type,
                "frames": [{
                    "time_seconds": frame.time_seconds,
                    "rotation_xyzw": list(frame.rotation_xyzw),
                    **({"translation": list(frame.translation), "translation_raw": list(frame.translation_raw)}
                       if frame.translation is not None else {})
                } for frame in track.frames]
            } for track in clip.bones]
        })
    result = {
        "format": "cj64-gta-ifp-interchange-v1",
        "source_file": args.ifp.name,
        "source_package": package.package_name,
        "warning": "Intermediate only. Retarget and bake to the Mario Armature before using in the game.",
        "animations": selected,
        "missing_clips": missing
    }
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {len(selected)} clips to {args.output}; missing: {len(missing)}")
    if missing:
        print("Missing clips: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
