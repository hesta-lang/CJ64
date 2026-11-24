#!/usr/bin/env python3
"""Compose GTA rotation deltas on the default SM64 Character Select idle pose.

The CS DynOS actor is animated with SM64's 20-part Mario animation layout.
Zero Euler channels are NOT its visible neutral pose. For example, the
MARIO_ANIM_IDLE Body channel has a ~90 degree Y rotation.

This tool restores the native Mario idle frame-zero pose for all 20 parts,
then composes the GTA retargeted local-motion delta on top of that pose.
Root translation channels remain untouched and must stay zero.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

REGISTRATION_RE = re.compile(
    r'(smlua_anim_util_register_animation\(\s*"(?P<name>[^"]+)"\s*,\s*'
    r'(?P<header>.*?)\s*,\s*\{\s*)'
    r'(?P<values>.*?)'
    r'(\s*\},\s*\{\s*)'
    r'(?P<indices>.*?)'
    r'(\s*\}\s*\))',
    re.S,
)
HEX_RE = re.compile(r"0x([0-9A-Fa-f]{1,4})")
APPLIED_MARKER = "CJ64_CS_DEFAULT_IDLE_POSE_ANCHOR_APPLIED"


def qnorm(q):
    length = math.sqrt(sum(float(value) * float(value) for value in q))
    if not math.isfinite(length) or length < 1e-12:
        raise ValueError("zero-length or invalid quaternion")
    return tuple(float(value) / length for value in q)


def qmul(a, b):
    ax, ay, az, aw = qnorm(a)
    bx, by, bz, bw = qnorm(b)
    return qnorm((
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ))


def q_from_euler_xyz(rx, ry, rz):
    cr, sr = math.cos(rx / 2.0), math.sin(rx / 2.0)
    cp, sp = math.cos(ry / 2.0), math.sin(ry / 2.0)
    cy, sy = math.cos(rz / 2.0), math.sin(rz / 2.0)
    return qnorm((
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    ))


def euler_xyz(q):
    x, y, z, w = qnorm(q)
    sin_y = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    if sin_y >= 1.0 - 1e-7:
        # At +90 degrees pitch the ordinary roll/yaw atan2 pairs both
        # approach 0/0. Choose the equivalent stable representation with
        # yaw=0 and keep the combined roll in X.
        return 2.0 * math.atan2(x, w), math.pi / 2.0, 0.0
    if sin_y <= -1.0 + 1e-7:
        # Equivalent stable representation for -90 degrees pitch.
        return 2.0 * math.atan2(-z, w), -math.pi / 2.0, 0.0
    rx = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    ry = math.asin(sin_y)
    rz = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return rx, ry, rz


def decode_angle(value):
    signed = value - 65536 if value >= 32768 else value
    return signed * (2.0 * math.pi / 65536.0)


def encode_angle(radians):
    return int(round(radians * 65536.0 / (2.0 * math.pi))) & 0xFFFF


def parse_hex_values(block: str, label: str) -> list[int]:
    tokens = list(HEX_RE.finditer(block))
    remainder = HEX_RE.sub("", block).strip(" \t\r\n,")
    if remainder:
        raise ValueError(f"Unexpected text in {label} table: {remainder[:60]!r}")
    return [int(match.group(1), 16) for match in tokens]


def format_values(values: list[int]) -> str:
    lines = []
    for start in range(0, len(values), 12):
        lines.append("        " + ", ".join(
            f"0x{value:04X}" for value in values[start:start + 12]
        ) + ",")
    return "\n".join(lines)


def load_native_pose(path: Path, expected_nodes: int = 20) -> tuple[list[str], dict[str, tuple[float, ...]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "cj64-native-mario-cs-pose-anchor-v1":
        raise ValueError("Unsupported native Mario pose-anchor format")
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != expected_nodes:
        raise ValueError(f"Native pose anchor must have exactly {expected_nodes} nodes")
    names = []
    rotations = {}
    for index, item in enumerate(nodes):
        name = item.get("node")
        raw_q = item.get("base_rotation_xyzw")
        if not isinstance(name, str) or not name or not isinstance(raw_q, list) or len(raw_q) != 4:
            raise ValueError(f"Invalid native pose entry at node index {index}")
        if item.get("index") != index:
            raise ValueError(f"Native pose entry {name!r} has incorrect index {item.get('index')}")
        if name in rotations:
            raise ValueError(f"Duplicate native pose node {name!r}")
        q = qnorm(raw_q)
        if not all(math.isfinite(value) for value in q):
            raise ValueError(f"Non-finite native pose quaternion for {name!r}")
        names.append(name)
        rotations[name] = q
    if len(set(names)) != expected_nodes:
        raise ValueError("Native pose node names are not unique")
    return names, rotations


def parse_registrations(source: str) -> list[dict[str, Any]]:
    result = []
    for match in REGISTRATION_RE.finditer(source):
        result.append({
            "name": match.group("name"),
            "header": match.group("header").strip(),
            "values": parse_hex_values(match.group("values"), f"{match.group('name')} values"),
            "indices": parse_hex_values(match.group("indices"), f"{match.group('name')} indices"),
            "span": match.span("values"),
        })
    expected = source.count("smlua_anim_util_register_animation(")
    if len(result) != expected:
        raise ValueError(f"Parsed {len(result)} of {expected} animation registrations")
    if not result:
        raise ValueError("No animation registrations found")
    return result


def apply_pose_to_values(
    values: list[int],
    indices: list[int],
    node_names: list[str],
    base_rotations: dict[str, tuple[float, ...]],
) -> tuple[list[int], float]:
    node_count = len(node_names)
    if len(indices) != (3 + node_count * 3) * 2:
        raise ValueError(f"Expected {(3 + node_count * 3) * 2} channel index entries, got {len(indices)}")

    output = list(values)
    max_first_frame_residual = 0.0

    # Preserve game-owned root translation exactly as supplied by the input.
    for axis in range(3):
        count, offset = indices[axis * 2:axis * 2 + 2]
        if count != 1 or offset >= len(values) or values[offset] != 0:
            raise ValueError(f"Root translation channel {axis} must contain one zero sample")

    for node_index, node_name in enumerate(node_names):
        base = base_rotations[node_name]
        channels = []
        for axis in range(3):
            channel_index = 3 + node_index * 3 + axis
            count, offset = indices[channel_index * 2:channel_index * 2 + 2]
            if count < 1 or offset + count > len(values):
                raise ValueError(f"{node_name}: invalid rotation channel {axis}")
            channels.append((count, offset))

        if len({count for count, _ in channels}) != 1:
            raise ValueError(f"{node_name}: XYZ rotation channel sample counts differ")
        frame_count = channels[0][0]

        for frame_index in range(frame_count):
            delta_angles = [
                decode_angle(values[offset + frame_index])
                for _count, offset in channels
            ]
            delta = q_from_euler_xyz(*delta_angles)
            # Local motion is applied on top of the native Mario/CS idle pose.
            combined = qmul(base, delta)
            encoded_angles = [encode_angle(value) for value in euler_xyz(combined)]
            for axis, (_count, offset) in enumerate(channels):
                output[offset + frame_index] = encoded_angles[axis]

            if frame_index == 0:
                reconstructed = q_from_euler_xyz(*(
                    decode_angle(value) for value in encoded_angles
                ))
                dot = abs(sum(a * b for a, b in zip(base, reconstructed)))
                dot = max(-1.0, min(1.0, dot))
                max_first_frame_residual = max(
                    max_first_frame_residual, 2.0 * math.acos(dot)
                )

    return output, max_first_frame_residual


def apply_native_pose(source: str, pose_path: Path) -> tuple[str, dict[str, Any]]:
    if APPLIED_MARKER in source:
        raise ValueError("Native Mario pose anchor has already been applied; refusing double application")
    node_names, base_rotations = load_native_pose(pose_path)
    registrations = parse_registrations(source)
    replacements = []
    clip_reports = []
    max_residual = 0.0
    neutral_idle_residual = None

    for item in registrations:
        if len(item["indices"]) != 126:
            raise ValueError(f"{item['name']}: expected 126 index entries, got {len(item['indices'])}")
        output_values, residual = apply_pose_to_values(
            item["values"], item["indices"], node_names, base_rotations
        )
        max_residual = max(max_residual, residual)
        if item["name"] == "cj64_anim_idle":
            neutral_idle_residual = residual
        replacements.append((item["span"], format_values(output_values)))
        clip_reports.append({
            "name": item["name"],
            "values_entries": len(output_values),
            "index_entries": len(item["indices"]),
            "first_frame_pose_residual_radians": residual,
            "sampled_frames": max(
                item["indices"][(3 + node * 3) * 2]
                for node in range(len(node_names))
            ),
        })
    if neutral_idle_residual is None:
        raise ValueError("Required neutral clip 'cj64_anim_idle' is missing")

    output = source
    for (start, end), replacement in reversed(replacements):
        output = output[:start] + replacement + output[end:]
    output = (
        "-- " + APPLIED_MARKER + "\n"
        "-- Native pose anchor: SM64 MARIO_ANIM_IDLE (anim_00), frame 0.\n"
        "-- GTA retarget channels are local motion deltas composed on top of this pose.\n"
        + output
    )

    report = {
        "format": "cj64-native-cs-pose-application-report-v1",
        "source_native_animation": "MARIO_ANIM_IDLE_HEAD_CENTER (anim_C5), frame 0",
        "source_pose_file": pose_path.name,
        "target_nodes": node_names,
        "clip_count": len(clip_reports),
        "max_first_frame_native_pose_residual_radians": max_residual,
        "neutral_idle_first_frame_residual_radians": neutral_idle_residual,
        "body_base_euler_degrees": [0.0, 89.994507, 0.0],
        "root_translation": "preserved zero; SM64CoopDX owns movement",
        "composition": "native_idle_local_pose * GTA_local_motion_delta",
        "clips": clip_reports,
        "status": "NATIVE_POSE_ANCHORED_STRUCTURAL_ONLY_REQUIRES_ANDROID_VISUAL_CHECK",
    }
    return output, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="generated GTA animation Lua module")
    parser.add_argument("--pose", type=Path, default=Path("tools/native_mario_idle_pose.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        source = args.source.read_text(encoding="utf-8")
        output, report = apply_native_pose(source, args.pose)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    report.update({
        "source_module": args.source.name,
        "output_module": args.output.name,
        "output_bytes": args.output.stat().st_size,
    })
    args.output.with_suffix(".pose-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "output": str(args.output),
        "clips": report["clip_count"],
        "nodes": len(report["target_nodes"]),
        "body_base_euler_degrees": report["body_base_euler_degrees"],
        "max_first_frame_residual_radians": report["max_first_frame_native_pose_residual_radians"],
        "neutral_idle_first_frame_residual_radians": report["neutral_idle_first_frame_residual_radians"],
        "status": report["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
