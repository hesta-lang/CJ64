#!/usr/bin/env python3
"""Validate selected GTA ped.ifp clips against the CJ FBX joint map.

This checks structural coverage only. It does not prove coordinate conversion,
retargeting, or compatibility with SM64 animation arrays.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from ifp_reader import IFPError, load_ifp

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "cj_animation_manifest.json"
BONE_MAP = ROOT / "cj_fbx_bone_map.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ifp", type=Path)
    args = parser.parse_args()
    try:
        ifp = load_ifp(str(args.ifp))
    except (OSError, IFPError) as exc:
        parser.error(str(exc))

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    mapping = json.loads(BONE_MAP.read_text(encoding="utf-8"))
    remap = {name.strip().casefold(): target for name, target in mapping["ifp_to_fbx"].items()}
    known_fbx = set(mapping["ifp_to_fbx"].values())
    known_fbx.update(mapping.get("fbx_bones_without_ifp_track", []))
    intentional = {name.strip().casefold() for name in mapping.get("intentionally_unmapped_ifp_tracks", {})}

    failed = False
    print(f"Package: {ifp.package_name}; clips: {len(ifp.animations)}")
    print("clip\tframes\tduration_s\ttracks\tmapped\tunmapped\tmissing_target")
    for item in manifest["clips"]:
        clip = ifp.find(item["name"])
        if clip is None:
            print(f"{item['name']}\t-\t-\t-\t0\tMISSING CLIP\t-")
            failed = True
            continue
        mapped = 0
        unmapped = []
        missing_target = []
        total_frames = 0
        for track in clip.bones:
            total_frames += len(track.frames)
            target = remap.get(track.name.strip().casefold())
            if target:
                mapped += 1
                if target not in known_fbx:
                    missing_target.append(f"{track.name}->{target}")
            elif track.name.strip().casefold() not in intentional:
                unmapped.append(track.name)
        print(
            f"{clip.name}\t{total_frames}\t{clip.duration:.3f}\t{len(clip.bones)}"
            f"\t{mapped}\t{','.join(unmapped) or '-'}\t{','.join(missing_target) or '-'}"
        )
        if unmapped or missing_target:
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
