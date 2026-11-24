#!/usr/bin/env python3
"""Preserve direct GTA source poses while encoding channels for SM64's ZXY matrix order.

The archived direct-source table serializes target rotations as XYZ Euler values.
SM64 animated parts interpret the stored channels using a Z-then-X-then-Y
matrix. Convert through quaternions so the intended GTA rotations survive
without adding any Mario idle-pose overlay.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from apply_native_cs_idle_pose import (
    REGISTRATION_RE,
    decode_angle,
    euler_sm64_zxy_near,
    encode_angle,
    format_values,
    parse_hex_values,
    q_from_euler_xyz,
    q_from_sm64_zxy,
    qnorm,
)

NODE_ORDER = [
    "Body", "Butt", "Torso", "Head", "Left Arm", "Left Arm Color",
    "Left Forearm", "Left Hand", "Right Arm", "Right Arm Color",
    "Right Forearm", "Right Hand", "Left Thigh", "Left Thigh Color",
    "Left Leg", "Left Shoe", "Right Thigh", "Right Thigh Color",
    "Right Leg", "Right Shoe",
]
CLIP_NAMES = {
    "cj64_anim_idle", "cj64_anim_walk_start", "cj64_anim_walk",
    "cj64_anim_run", "cj64_anim_sprint_candidate", "cj64_anim_run_stop",
    "cj64_anim_jump_start", "cj64_anim_jump_air", "cj64_anim_jump_land",
    "cj64_anim_fall", "cj64_anim_fall_air", "cj64_anim_fall_land",
    "cj64_anim_swim_tread",
}
APPLIED_MARKER = "CJ64_CS_GTA_DIRECT_SM64_ZXY_CHANNEL_ORDER_APPLIED"


def q_angle(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = abs(sum(x * y for x, y in zip(qnorm(a), qnorm(b))))
    return 2.0 * math.acos(max(-1.0, min(1.0, dot)))


def load_gta_idle_pose(path: Path) -> dict[str, tuple[float, ...]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "cj64-gta-idle-source-rest-v1":
        raise ValueError("Unsupported GTA source idle-pose format")
    if data.get("node_count") != 20 or not isinstance(data.get("nodes"), list):
        raise ValueError("GTA idle pose must contain exactly 20 nodes")
    if len(data["nodes"]) != 20:
        raise ValueError("GTA idle pose must contain exactly 20 nodes")
    result: dict[str, tuple[float, ...]] = {}
    names = []
    for index, item in enumerate(data["nodes"]):
        name = item.get("node")
        quat = item.get("base_rotation_xyzw")
        if item.get("node_index") != index or not isinstance(name, str):
            raise ValueError(f"Invalid GTA idle node at index {index}")
        if not isinstance(quat, list) or len(quat) != 4:
            raise ValueError(f"{name}: expected an XYZW quaternion")
        normalized = qnorm(tuple(float(v) for v in quat))
        if not all(math.isfinite(v) for v in normalized):
            raise ValueError(f"{name}: non-finite GTA idle quaternion")
        result[name] = normalized
        names.append(name)
    if names != NODE_ORDER:
        raise ValueError("GTA idle-pose node order does not match the 20-part CS actor")
    return result


def parse_tables(source: str) -> list[dict[str, Any]]:
    result = []
    for match in REGISTRATION_RE.finditer(source):
        result.append({
            "name": match.group("name"),
            "header": match.group("header").strip(),
            "values": parse_hex_values(match.group("values"), "animation values"),
            "indices": parse_hex_values(match.group("indices"), "animation indices"),
            "span": match.span("values"),
        })
    expected = source.count("smlua_anim_util_register_animation(")
    if len(result) != expected:
        raise ValueError(f"Parsed {len(result)} of {expected} animation registrations")
    if {item["name"] for item in result} != CLIP_NAMES or len(result) != 13:
        raise ValueError("Direct GTA table must contain the expected 13 CJ64 clips")
    return result


def convert_values(values: list[int], indices: list[int]) -> tuple[list[int], float]:
    if len(indices) != 126:
        raise ValueError(f"Expected 126 channel-index entries, got {len(indices)}")
    output = list(values)
    for axis in range(3):
        count, offset = indices[axis * 2:axis * 2 + 2]
        if count != 1 or offset < 0 or offset >= len(values) or values[offset] != 0:
            raise ValueError(f"Root translation channel {axis} must remain a single zero sample")

    max_residual = 0.0
    for node_index, node_name in enumerate(NODE_ORDER):
        channel_ranges = []
        for axis in range(3):
            channel = 3 + node_index * 3 + axis
            count, offset = indices[channel * 2:channel * 2 + 2]
            if count < 1 or offset < 0 or offset + count > len(values):
                raise ValueError(f"{node_name}: invalid rotation channel {axis}")
            channel_ranges.append((count, offset))
        if len({count for count, _ in channel_ranges}) != 1:
            raise ValueError(f"{node_name}: XYZ rotation sample counts differ")

        previous = None
        frame_count = channel_ranges[0][0]
        for frame in range(frame_count):
            raw_xyz = tuple(
                decode_angle(values[offset + frame])
                for _count, offset in channel_ranges
            )
            intended = q_from_euler_xyz(*raw_xyz)
            encoded_xyz = euler_sm64_zxy_near(intended, previous)
            encoded = [encode_angle(v) for v in encoded_xyz]
            for axis, (_count, offset) in enumerate(channel_ranges):
                output[offset + frame] = encoded[axis]
            reconstructed = q_from_sm64_zxy(*(
                decode_angle(value) for value in encoded
            ))
            residual = q_angle(intended, reconstructed)
            max_residual = max(max_residual, residual)
            previous = tuple(decode_angle(value) for value in encoded)
    return output, max_residual


def convert_direct_table(source: str, pose_path: Path) -> tuple[str, dict[str, Any]]:
    if APPLIED_MARKER in source or "CJ64_CS_SM64_ZXY_CHANNEL_ORDER_APPLIED" in source:
        raise ValueError("SM64 ZXY conversion has already been applied")
    gta_idle_pose = load_gta_idle_pose(pose_path)
    tables = parse_tables(source)
    replacements = []
    clip_reports = []
    max_residual = 0.0
    idle_pose_error = None

    for table in tables:
        declared_frames = int(table["header"].split(",")[-1].strip(), 0) + 1
        if declared_frames < 1:
            raise ValueError(f"{table['name']}: invalid declared frame count")
        output_values, clip_residual = convert_values(table["values"], table["indices"])
        node_frame_counts = {
            table["indices"][(3 + node * 3) * 2]
            for node in range(20)
        }
        if node_frame_counts != {declared_frames}:
            raise ValueError(
                f"{table['name']}: declared {declared_frames} frames but channels contain "
                f"{sorted(node_frame_counts)}"
            )
        max_residual = max(max_residual, clip_residual)
        if table["name"] == "cj64_anim_idle":
            node_errors = []
            for node_index, node_name in enumerate(NODE_ORDER):
                channels = []
                for axis in range(3):
                    channel = 3 + node_index * 3 + axis
                    count, offset = table["indices"][channel * 2:channel * 2 + 2]
                    if count != 46:
                        raise ValueError(f"{node_name}: expected the 46-frame IDLE_stance clip")
                    channels.append(decode_angle(output_values[offset]))
                node_errors.append(q_angle(q_from_sm64_zxy(*channels), gta_idle_pose[node_name]))
            idle_pose_error = max(node_errors)
        replacements.append((table["span"], format_values(output_values)))
        clip_reports.append({
            "name": table["name"],
            "frame_count": declared_frames,
            "max_zxy_quantization_error_radians": clip_residual,
        })

    if idle_pose_error is None:
        raise ValueError("Direct GTA idle clip is missing")
    if idle_pose_error >= math.radians(0.02):
        raise ValueError(
            "Converted IDLE_stance frame zero does not match gta_idle_source_pose.json: "
            f"{math.degrees(idle_pose_error):.6f} degrees"
        )
    if max_residual >= math.radians(0.02):
        raise ValueError(
            f"SM64 ZXY conversion residual is too high: {math.degrees(max_residual):.6f} degrees"
        )

    output = source
    for (start, end), replacement in reversed(replacements):
        output = output[:start] + replacement + output[end:]
    output = (
        "-- " + APPLIED_MARKER + "\n"
        "-- Direct GTA source-pose channels preserved as quaternions and re-encoded for SM64 ZXY.\n"
        "-- No Mario idle animation or Mario pose anchor is applied.\n"
        "-- Root translation remains zero; SM64CoopDX owns movement and heading.\n"
        + output
    )
    report = {
        "format": "cj64-direct-gta-sm64-zxy-conversion-report-v1",
        "source_pose": "GTA San Andreas IDLE_stance frame 0",
        "source_pose_file": pose_path.name,
        "target_nodes": NODE_ORDER,
        "clip_count": len(clip_reports),
        "root_translation": "fixed zero",
        "rotation_conversion": "XYZ Euler serialization -> quaternion -> SM64 ZXY Euler channels",
        "mario_pose_anchor_applied": False,
        "gta_idle_frame_zero_max_error_radians": idle_pose_error,
        "max_frame_quantization_error_radians": max_residual,
        "clips": clip_reports,
        "status": "DIRECT_GTA_SOURCE_POSE_REENCODED_FOR_SM64_ZXY_REQUIRES_ANDROID_VISUAL_CHECK",
    }
    return output, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="direct GTA Lua table before SM64 ZXY conversion")
    parser.add_argument("--pose", type=Path, default=Path("tools/gta_idle_source_pose.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        output, report = convert_direct_table(
            args.source.read_text(encoding="utf-8"), args.pose
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    args.output.with_suffix(".report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "clips": report["clip_count"],
        "nodes": len(report["target_nodes"]),
        "mario_pose_anchor_applied": False,
        "gta_idle_frame_zero_error_degrees": math.degrees(report["gta_idle_frame_zero_max_error_radians"]),
        "max_frame_quantization_error_degrees": math.degrees(report["max_frame_quantization_error_radians"]),
        "status": report["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
