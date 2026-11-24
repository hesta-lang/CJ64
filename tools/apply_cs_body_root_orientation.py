#!/usr/bin/env python3
"""RETIRED: body-only alignment experiment; not used by the active 0.2.11 pipeline.

The old helper replaced only Body and left 19 absolute GTA child rotations intact.
That approach did not correct the complete pose and is superseded by the active
all-joint neutral-relative XYZ compositor. Do not use this file in the build.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

REGISTER_RE = re.compile(
    r'(smlua_anim_util_register_animation\(\s*"(?P<name>[^"]+)"\s*,\s*'
    r'(?P<header>.*?)\s*,\s*\{\s*)'
    r'(?P<values>.*?)'
    r'(\s*\},\s*\{\s*)'
    r'(?P<indices>.*?)'
    r'(\s*\}\s*\))',
    re.S,
)
HEX_RE = re.compile(r"0x([0-9A-Fa-f]{1,4})")
MARKER = "CJ64_CS_BODY_ROOT_ORIENTATION_ONLY"
LEGACY_FULL_POSE_MARKERS = (
    "CJ64_NATIVE_MARIO_IDLE_POSE_ANCHOR_APPLIED",
    "CJ64_CS_DEFAULT_IDLE_POSE_ANCHOR_APPLIED",
)
EXPECTED_NODE_COUNT = 20
EXPECTED_INDEX_ENTRIES = (3 + EXPECTED_NODE_COUNT * 3) * 2


def parse_values(block: str, label: str) -> list[int]:
    matches = list(HEX_RE.finditer(block))
    remainder = HEX_RE.sub("", block).strip(" \t\r\n,")
    if remainder:
        raise ValueError(f"Unexpected text in {label}: {remainder[:60]!r}")
    return [int(match.group(1), 16) for match in matches]


def format_values(values: list[int]) -> str:
    return "\n".join(
        "        " + ", ".join(f"0x{value:04X}" for value in values[i:i + 12]) + ","
        for i in range(0, len(values), 12)
    )


def signed_degrees(value: int) -> float:
    signed = value - 65536 if value >= 32768 else value
    return signed * (360.0 / 65536.0)


def load_body_orientation(pose_path: Path) -> tuple[int, int, int]:
    data = json.loads(pose_path.read_text(encoding="utf-8"))
    if data.get("format") != "cj64-native-cs-pose-anchor-sm64-zxy-v2":
        raise ValueError("Unsupported native CS idle-pose reference format")
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != EXPECTED_NODE_COUNT:
        raise ValueError("Native CS idle-pose reference must contain 20 animated nodes")
    body = nodes[0]
    raw = body.get("first_frame_euler16")
    if body.get("index") != 0 or body.get("node") != "Body":
        raise ValueError("Native CS pose reference does not start with the Body node")
    if not isinstance(raw, list) or len(raw) != 3:
        raise ValueError("Native CS Body pose must contain three XYZ angles")
    if any(not isinstance(value, str) or not re.fullmatch(r"[0-9A-Fa-f]{4}", value)
           for value in raw):
        raise ValueError("Native CS Body XYZ angles must be four-digit 16-bit hex values")
    angles = tuple(int(value, 16) for value in raw)
    # This exact one-axis reference is from the known-good Mario/CS anim_00.
    # Since X and Z are zero, it represents the same physical rotation even
    # though the archived pose file also documents the historical ZXY path.
    if angles != (0x0000, 0x3FFF, 0x0000):
        raise ValueError(
            "Unexpected native CS Body orientation; expected XYZ [0000, 3FFF, 0000], "
            f"got {[f'{value:04X}' for value in angles]}"
        )
    return angles


def parse_registrations(source: str) -> list[dict[str, Any]]:
    records = []
    for match in REGISTER_RE.finditer(source):
        records.append({
            "name": match.group("name"),
            "header": match.group("header").strip(),
            "values": parse_values(match.group("values"), match.group("name") + " values"),
            "indices": parse_values(match.group("indices"), match.group("name") + " indices"),
            "span": match.span("values"),
        })
    expected = source.count("smlua_anim_util_register_animation(")
    if len(records) != expected or not records:
        raise ValueError(f"Parsed {len(records)} of {expected} animation registrations")
    names = [record["name"] for record in records]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate animation names")
    return records


def apply_body_root_orientation(
    source: str,
    *,
    pose_path: Path,
    expected_clips: int = 13,
    node_count: int = EXPECTED_NODE_COUNT,
) -> tuple[str, dict[str, Any]]:
    if MARKER in source:
        raise ValueError("Body root orientation has already been applied")
    if any(marker in source for marker in LEGACY_FULL_POSE_MARKERS):
        raise ValueError("Refusing a table with a full Mario idle-pose overlay; only Body may be aligned")

    if node_count != EXPECTED_NODE_COUNT:
        raise ValueError(f"CJ64's compiled CS actor requires exactly {EXPECTED_NODE_COUNT} animated parts")
    body_angles = load_body_orientation(pose_path)
    records = parse_registrations(source)
    if len(records) != expected_clips:
        raise ValueError(f"Expected {expected_clips} clips, found {len(records)}")

    replacements = []
    reports = []
    changed_source_body_frames = 0

    for record in records:
        name = record["name"]
        values = list(record["values"])
        indices = record["indices"]
        if len(indices) != EXPECTED_INDEX_ENTRIES:
            raise ValueError(
                f"{name}: expected {EXPECTED_INDEX_ENTRIES} channel index entries, got {len(indices)}"
            )
        try:
            declared_frames = int(record["header"].split(",")[-1].strip(), 0) + 1
        except ValueError as exc:
            raise ValueError(f"{name}: invalid declared frame count") from exc
        if declared_frames < 1:
            raise ValueError(f"{name}: invalid declared frame count")

        # The three translation channels are owned by the game and must remain
        # a single zero sample. Do not feed GTA root displacement into MarioState.
        for axis in range(3):
            count, offset = indices[axis * 2:axis * 2 + 2]
            if count != 1 or offset < 0 or offset >= len(values) or values[offset] != 0:
                raise ValueError(f"{name}: root translation channel {axis} must be one zero sample")

        # Confirm every node has three correctly sized XYZ channels before
        # changing anything. This also catches a shifted/corrupt index table.
        channel_ranges = []
        for node_index in range(node_count):
            axes = []
            for axis in range(3):
                channel_index = 3 + node_index * 3 + axis
                count, offset = indices[channel_index * 2:channel_index * 2 + 2]
                if count != declared_frames or offset < 0 or offset + count > len(values):
                    raise ValueError(
                        f"{name}: node {node_index} axis {axis} frame count or value bounds mismatch"
                    )
                axes.append((count, offset))
            channel_ranges.append(axes)

        # Discard GTA's Normal/root orientation only. Keep all local limb motion
        # and samples (nodes 1–19) unchanged, and use the working native CS Body
        # orientation for every frame so the complete actor stays upright.
        source_body_values = []
        for axis, target_angle in enumerate(body_angles):
            count, offset = channel_ranges[0][axis]
            source_body_values.append(values[offset:offset + count])
            changed_source_body_frames += sum(
                sample != target_angle for sample in source_body_values[-1]
            )
            values[offset:offset + count] = [target_angle] * count

        replacements.append((record["span"], format_values(values)))
        reports.append({
            "name": name,
            "frames": declared_frames,
            "body_root_xyz_euler16": [f"{value:04X}" for value in body_angles],
            "body_root_xyz_degrees": [round(signed_degrees(value), 6) for value in body_angles],
            "gta_body_root_orientation_replaced": True,
            "articulated_nodes_modified": 0,
            "root_translation": "unchanged zero",
        })

    output = source
    for (start, end), replacement in reversed(replacements):
        output = output[:start] + replacement + output[end:]
    output = (
        "-- " + MARKER + "\n"
        "-- Body alone is aligned to native CS anim_00 frame zero: XYZ [0000, 3FFF, 0000].\n"
        "-- GTA Normal/root orientation is not transferred to the SM64CoopDX player object.\n"
        "-- The other 19 animated parts and all root translations are preserved unchanged.\n"
        + output
    )
    report = {
        "format": "cj64-body-root-orientation-only-v2",
        "clip_count": len(reports),
        "node_count": node_count,
        "body_root_xyz_euler16": [f"{value:04X}" for value in body_angles],
        "body_root_xyz_degrees": [round(signed_degrees(value), 6) for value in body_angles],
        "body_root_orientation_source": "tools/native_mario_idle_pose.json: MARIO_ANIM_IDLE (anim_00), frame 0, Body only",
        "gta_body_root_orientation_replaced": True,
        "articulated_nodes_modified": 0,
        "root_translation": "fixed zero and preserved",
        "non_body_animation_channels": "preserved exactly",
        "source_body_samples_replaced": changed_source_body_frames,
        "clips": reports,
        "status": "BODY_ROOT_ALIGNED_OTHER_19_ANIMATED_PARTS_PRESERVED_REQUIRES_ANDROID_VISUAL_CHECK",
    }
    return output, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="XYZ-preserved GTA animation Lua module")
    parser.add_argument("--pose", type=Path, default=Path("tools/native_mario_idle_pose.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-clips", type=int, default=13)
    args = parser.parse_args()
    try:
        output, report = apply_body_root_orientation(
            args.source.read_text(encoding="utf-8"),
            pose_path=args.pose,
            expected_clips=args.expected_clips,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    report.update({"source_module": args.source.name, "output_module": args.output.name})
    report_path = args.output.with_suffix(".body-root-report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "clips": report["clip_count"],
        "body_root_xyz_euler16": report["body_root_xyz_euler16"],
        "body_root_xyz_degrees": report["body_root_xyz_degrees"],
        "articulated_nodes_modified": report["articulated_nodes_modified"],
        "source_body_samples_replaced": report["source_body_samples_replaced"],
        "status": report["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
