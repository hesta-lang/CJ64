#!/usr/bin/env python3
"""Compose neutral-relative GTA motion with all native CS anim_00 XYZ joints.

This changes animation tables only. It never edits the model, DynOS actor,
skeleton, bone hierarchy, or root translation.
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
MARKER = "CJ64_CS_NATIVE_ANIM00_XYZ_POSE_APPLIED"
IDENTITY = (0.0, 0.0, 0.0, 1.0)
NODE_ORDER = [
    "Body", "Butt", "Torso", "Head", "Left Arm", "Left Arm Color",
    "Left Forearm", "Left Hand", "Right Arm", "Right Arm Color",
    "Right Forearm", "Right Hand", "Left Thigh", "Left Thigh Color",
    "Left Leg", "Left Shoe", "Right Thigh", "Right Thigh Color",
    "Right Leg", "Right Shoe",
]
EXPECTED_CLIPS = {
    "cj64_anim_idle", "cj64_anim_walk_start", "cj64_anim_walk",
    "cj64_anim_run", "cj64_anim_sprint_candidate", "cj64_anim_run_stop",
    "cj64_anim_jump_start", "cj64_anim_jump_air", "cj64_anim_jump_land",
    "cj64_anim_fall", "cj64_anim_fall_air", "cj64_anim_fall_land",
    "cj64_anim_swim_tread",
}


def qnorm(q):
    length = math.sqrt(sum(float(v) * float(v) for v in q))
    if not math.isfinite(length) or length < 1e-12:
        raise ValueError("zero-length or invalid quaternion")
    return tuple(float(v) / length for v in q)


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
        return 2.0 * math.atan2(x, w), math.pi / 2.0, 0.0
    if sin_y <= -1.0 + 1e-7:
        return 2.0 * math.atan2(-z, w), -math.pi / 2.0, 0.0
    return (
        math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y)),
        math.asin(sin_y),
        math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)),
    )


def wrap_near(angle, reference):
    return angle + round((reference - angle) / (2.0 * math.pi)) * (2.0 * math.pi)


def euler_xyz_near(q, reference):
    rx, ry, rz = euler_xyz(q)
    candidates = [(rx, ry, rz)]
    alternate_x = rx + math.pi
    alternate_y = math.pi - ry if ry >= 0.0 else -math.pi - ry
    candidates.append((alternate_x, alternate_y, rz + math.pi))
    adjusted = [
        tuple(wrap_near(value, ref) for value, ref in zip(candidate, reference))
        for candidate in candidates
    ]
    return min(
        adjusted,
        key=lambda candidate: sum((value - ref) ** 2 for value, ref in zip(candidate, reference)),
    )


def decode_angle(value):
    signed = value - 65536 if value >= 32768 else value
    return signed * (2.0 * math.pi / 65536.0)


def encode_angle(radians):
    return int(round(radians * 65536.0 / (2.0 * math.pi))) & 0xFFFF


def quaternion_error(a, b):
    dot = abs(sum(x * y for x, y in zip(qnorm(a), qnorm(b))))
    return 2.0 * math.acos(max(-1.0, min(1.0, dot)))


def parse_values(block: str, label: str) -> list[int]:
    tokens = list(HEX_RE.finditer(block))
    remainder = HEX_RE.sub("", block).strip(" \t\r\n,")
    if remainder:
        raise ValueError(f"Unexpected text in {label}: {remainder[:60]!r}")
    return [int(match.group(1), 16) for match in tokens]


def parse_registrations(source: str) -> list[dict[str, Any]]:
    result = []
    for match in REGISTER_RE.finditer(source):
        result.append({
            "name": match.group("name"),
            "header": match.group("header").strip(),
            "values": parse_values(match.group("values"), f"{match.group('name')} values"),
            "indices": parse_values(match.group("indices"), f"{match.group('name')} indices"),
            "span": match.span("values"),
        })
    expected = source.count("smlua_anim_util_register_animation(")
    if len(result) != expected:
        raise ValueError(f"Parsed {len(result)} of {expected} animation registrations")
    if not result:
        raise ValueError("No animation registrations found")
    return result


def load_native_pose(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "cj64-native-cs-anim00-pose-xyz-v1":
        raise ValueError("Unsupported native anim_00 XYZ pose format")
    if data.get("rotation_function") != "mtxf_rotate_xyz_and_translate":
        raise ValueError("Native pose does not declare the engine animated-part XYZ function")
    nodes = data.get("nodes")
    if data.get("node_count") != 20 or not isinstance(nodes, list) or len(nodes) != 20:
        raise ValueError("Native anim_00 pose must contain exactly 20 nodes")
    names, rotations, angles = [], {}, {}
    for index, item in enumerate(nodes):
        name = item.get("node")
        raw = item.get("first_frame_euler16")
        if index >= len(NODE_ORDER) or item.get("index") != index or name != NODE_ORDER[index]:
            raise ValueError(f"Native pose node order mismatch at index {index}")
        if not isinstance(raw, list) or len(raw) != 3:
            raise ValueError(f"{name}: expected three native XYZ angles")
        if any(not isinstance(value, str) or not re.fullmatch(r"[0-9A-Fa-f]{4}", value) for value in raw):
            raise ValueError(f"{name}: invalid 16-bit XYZ angle")
        frame_angles = tuple(decode_angle(int(value, 16)) for value in raw)
        names.append(name)
        angles[name] = frame_angles
        rotations[name] = q_from_euler_xyz(*frame_angles)
    if names != NODE_ORDER:
        raise ValueError("Native anim_00 node list does not match the verified CS order")
    return names, rotations, angles


def validate_registration(record):
    values, indices = record["values"], record["indices"]
    if len(indices) != 126:
        raise ValueError(f"{record['name']}: expected 126 index entries for 63 channels")
    try:
        frame_count = int(record["header"].split(",")[-1].strip(), 0) + 1
    except (ValueError, IndexError) as exc:
        raise ValueError(f"{record['name']}: invalid last-frame header value") from exc
    if frame_count < 1:
        raise ValueError(f"{record['name']}: invalid frame count")
    for channel in range(63):
        count, offset = indices[channel * 2:channel * 2 + 2]
        if count < 1 or offset < 0 or offset + count > len(values):
            raise ValueError(f"{record['name']}: channel {channel} points outside its values")
    for axis in range(3):
        count, offset = indices[axis * 2:axis * 2 + 2]
        if count != 1 or values[offset] != 0:
            raise ValueError(f"{record['name']}: player root translation axis {axis} must remain zero")
    for node_index, node_name in enumerate(NODE_ORDER):
        counts = [
            indices[(3 + node_index * 3 + axis) * 2]
            for axis in range(3)
        ]
        if counts != [frame_count] * 3:
            raise ValueError(
                f"{record['name']}/{node_name}: expected {frame_count} XYZ samples, got {counts}"
            )
    return frame_count


def apply_native_pose(source: str, pose_path: Path):
    if MARKER in source:
        raise ValueError("Native anim_00 XYZ pose has already been applied; refusing double composition")
    if "CJ64_CS_GTA_DIRECT_SM64_ZXY_CHANNEL_ORDER_APPLIED" in source or "CJ64_CS_SM64_ZXY_CHANNEL_ORDER_APPLIED" in source:
        raise ValueError("Rejected ZXY animation source; rebuild from the direct XYZ source table")
    names, bases, base_angles = load_native_pose(pose_path)
    records = parse_registrations(source)
    if {item["name"] for item in records} != EXPECTED_CLIPS or len(records) != len(EXPECTED_CLIPS):
        raise ValueError("Expected the exact 13 CJ64 GTA animation clips")

    replacements, reports = [], []
    max_idle_first_frame_error = 0.0
    max_frame_roundtrip_error = 0.0

    for record in records:
        frame_count = validate_registration(record)
        values = list(record["values"])
        indices = record["indices"]
        clip_error = 0.0

        for node_index, node_name in enumerate(names):
            channels = [
                indices[(3 + node_index * 3 + axis) * 2:(3 + node_index * 3 + axis) * 2 + 2]
                for axis in range(3)
            ]
            offsets = [entry[1] for entry in channels]
            reference_angles = base_angles[node_name]
            previous_angles = reference_angles

            for frame in range(frame_count):
                # The GTA Normal/root channel is not Mario's world root.
                # Keep Body at native anim_00 so SM64CoopDX owns heading.
                if node_index == 0:
                    combined = bases[node_name]
                else:
                    delta_angles = tuple(
                        decode_angle(values[offset + frame]) for offset in offsets
                    )
                    motion_delta = q_from_euler_xyz(*delta_angles)
                    combined = qmul(bases[node_name], motion_delta)

                if frame == 0 and quaternion_error(combined, bases[node_name]) < 1e-9:
                    output_angles = reference_angles
                else:
                    output_angles = euler_xyz_near(combined, previous_angles)

                encoded = [encode_angle(value) for value in output_angles]
                for axis, offset in enumerate(offsets):
                    values[offset + frame] = encoded[axis]

                reconstructed = q_from_euler_xyz(*(
                    decode_angle(value) for value in encoded
                ))
                error = quaternion_error(combined, reconstructed)
                clip_error = max(clip_error, error)
                max_frame_roundtrip_error = max(max_frame_roundtrip_error, error)
                previous_angles = tuple(decode_angle(value) for value in encoded)

        if record["name"] == "cj64_anim_idle":
            for node_index, node_name in enumerate(names):
                output_angles = tuple(
                    decode_angle(values[indices[(3 + node_index * 3 + axis) * 2 + 1]])
                    for axis in range(3)
                )
                actual = q_from_euler_xyz(*output_angles)
                max_idle_first_frame_error = max(
                    max_idle_first_frame_error,
                    quaternion_error(actual, bases[node_name]),
                )

        replacements.append((record["span"], values, record["values"]))
        reports.append({
            "name": record["name"],
            "frame_count": frame_count,
            "max_xyz_roundtrip_error_radians": clip_error,
        })

    if max_idle_first_frame_error > math.radians(0.02):
        raise ValueError(
            "cj64_anim_idle frame 0 does not reproduce all 20 native anim_00 joints: "
            f"{math.degrees(max_idle_first_frame_error):.6f} degrees"
        )
    if max_frame_roundtrip_error > math.radians(0.02):
        raise ValueError(
            "Engine XYZ angle round-trip error is too large: "
            f"{math.degrees(max_frame_roundtrip_error):.6f} degrees"
        )

    output = source
    for (start, end), new_values, _old_values in reversed(replacements):
        formatted = "\n".join(
            "        " + ", ".join(f"0x{value:04X}" for value in new_values[i:i + 12]) + ","
            for i in range(0, len(new_values), 12)
        )
        output = output[:start] + formatted + output[end:]
    output = (
        "-- " + MARKER + "\n"
        "-- Neutral-relative GTA motion composed on every native CS anim_00 XYZ joint.\n"
        "-- GTA Normal/root rotation is ignored; native Body stays fixed and MarioState owns world heading.\n"
        "-- Only animation samples changed. Model, actor binary, bones and hierarchy are not edited.\n"
        + output
    )
    report = {
        "format": "cj64-native-anim00-xyz-animation-report-v1",
        "target_pose": "native SM64 MARIO_ANIM_IDLE (anim_00), frame 0",
        "rotation_function": "mtxf_rotate_xyz_and_translate",
        "rotation_composition": "native_anim_00_XYZ_pose * neutral_relative_GTA_motion_delta",
        "target_node_count": len(names),
        "clip_count": len(reports),
        "root_translation": "fixed zero; SM64CoopDX owns movement",
        "Body": "fixed to native anim_00 XYZ pose; GTA Normal/root track excluded",
        "all_20_idle_first_frame_pose_error_degrees": math.degrees(max_idle_first_frame_error),
        "max_xyz_roundtrip_error_degrees": math.degrees(max_frame_roundtrip_error),
        "animation_samples_modified": True,
        "model_or_skeleton_modified": False,
        "clips": reports,
        "status": "ALL_20_NATIVE_ANIM00_XYZ_JOINTS_COMPOSED_REQUIRES_ANDROID_VISUAL_CHECK",
    }
    return output, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="neutral-relative XYZ GTA animation Lua table")
    parser.add_argument("--pose", type=Path, default=Path("tools/native_mario_idle_pose_xyz.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        output, report = apply_native_pose(
            args.source.read_text(encoding="utf-8"), args.pose
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    report_path = args.output.with_suffix(".native-anim00-xyz-report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "clips": report["clip_count"],
        "nodes": report["target_node_count"],
        "idle_first_frame_error_degrees": report["all_20_idle_first_frame_pose_error_degrees"],
        "max_xyz_roundtrip_error_degrees": report["max_xyz_roundtrip_error_degrees"],
        "model_or_skeleton_modified": report["model_or_skeleton_modified"],
        "status": report["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
