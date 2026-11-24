#!/usr/bin/env python3
"""Validate and package direct GTA animation channels in SM64's XYZ convention.

SM64CoopDX geo_process_animated_part calls mtxf_rotate_xyz_and_translate.
The direct GTA table was already serialized as XYZ Euler channels, so this
converter deliberately preserves every 16-bit value and channel index.
"""
from __future__ import annotations

import argparse
import hashlib
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
APPLIED_MARKER = "CJ64_CS_GTA_DIRECT_SM64_XYZ_CHANNEL_ORDER_PRESERVED"


def decode_angle(value: int) -> float:
    signed = value - 65536 if value >= 32768 else value
    return signed * (2.0 * math.pi / 65536.0)


def qnorm(q):
    length = math.sqrt(sum(float(value) * float(value) for value in q))
    if not math.isfinite(length) or length < 1e-12:
        raise ValueError("zero-length or invalid quaternion")
    return tuple(float(value) / length for value in q)


def q_from_euler_xyz(rx: float, ry: float, rz: float):
    """Quaternion equivalent of the SM64 XYZ animation matrix."""
    cr, sr = math.cos(rx / 2.0), math.sin(rx / 2.0)
    cp, sp = math.cos(ry / 2.0), math.sin(ry / 2.0)
    cy, sy = math.cos(rz / 2.0), math.sin(rz / 2.0)
    return qnorm((
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    ))


def q_to_matrix(q):
    x, y, z, w = qnorm(q)
    return (
        (1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)),
        (2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)),
        (2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)),
    )


def sm64_mtxf_rotate_xyz(rx: float, ry: float, rz: float):
    """The 3x3 coefficients written by SM64CoopDX mtxf_rotate_xyz_and_translate."""
    sx, cx = math.sin(rx), math.cos(rx)
    sy, cy = math.sin(ry), math.cos(ry)
    sz, cz = math.sin(rz), math.cos(rz)
    return (
        (cy * cz, cy * sz, -sy),
        (sx * sy * cz - cx * sz, sx * sy * sz + cx * cz, sx * cy),
        (cx * sy * cz + sx * sz, cx * sy * sz - sx * cz, cx * cy),
    )


def max_matrix_error(a, b) -> float:
    return max(abs(a[row][col] - b[row][col]) for row in range(3) for col in range(3))


def validate_engine_xyz_convention() -> float:
    """Cross-check the game's C matrix against the independent quaternion matrix."""
    samples = (
        (0.0, 0.0, 0.0),
        (math.pi / 2.0, 0.0, 0.0),
        (0.0, -math.pi / 2.0, 0.0),
        (0.0, 0.0, math.pi / 2.0),
        (0.43, -0.71, 1.12),
        (-1.03, 0.62, -0.87),
    )
    maximum = 0.0
    for angles in samples:
        q_matrix = q_to_matrix(q_from_euler_xyz(*angles))
        expected_engine_matrix = tuple(
            tuple(q_matrix[col][row] for col in range(3))
            for row in range(3)
        )
        maximum = max(
            maximum,
            max_matrix_error(sm64_mtxf_rotate_xyz(*angles), expected_engine_matrix),
        )
    if maximum > 1e-10:
        raise ValueError(
            "XYZ quaternion/matrix check failed: "
            f"{maximum:.12g}; do not package these channels"
        )
    return maximum


def parse_hex_values(block: str, label: str) -> list[int]:
    tokens = list(HEX_RE.finditer(block))
    remainder = HEX_RE.sub("", block).strip(" \t\r\n,")
    if remainder:
        raise ValueError(f"Unexpected text in {label} table: {remainder[:60]!r}")
    return [int(match.group(1), 16) for match in tokens]


def parse_tables(source: str) -> list[dict[str, Any]]:
    result = []
    for match in REGISTRATION_RE.finditer(source):
        result.append({
            "name": match.group("name"),
            "header": match.group("header").strip(),
            "values": parse_hex_values(match.group("values"), "animation values"),
            "indices": parse_hex_values(match.group("indices"), "animation indices"),
        })
    expected = source.count("smlua_anim_util_register_animation(")
    if len(result) != expected:
        raise ValueError(f"Parsed {len(result)} of {expected} animation registrations")
    if len(result) != 13 or {item["name"] for item in result} != CLIP_NAMES:
        raise ValueError("Direct GTA table must contain the exact expected 13 CJ64 clips")
    return result


def validate_table(table: dict[str, Any]) -> dict[str, Any]:
    name = table["name"]
    values = table["values"]
    indices = table["indices"]
    if len(indices) != 126:
        raise ValueError(f"{name}: expected 126 index entries for 63 XYZ channels")

    try:
        declared_frames = int(table["header"].split(",")[-1].strip(), 0) + 1
    except ValueError as exc:
        raise ValueError(f"{name}: invalid animation header frame count") from exc
    if declared_frames < 1:
        raise ValueError(f"{name}: invalid declared frame count")

    for channel in range(63):
        count, offset = indices[channel * 2:channel * 2 + 2]
        if count < 1 or offset < 0 or offset + count > len(values):
            raise ValueError(f"{name}: channel {channel} points outside its value table")

    for axis in range(3):
        count, offset = indices[axis * 2:axis * 2 + 2]
        if count != 1 or values[offset] != 0:
            raise ValueError(f"{name}: root translation channel {axis} must remain zero")

    frame_counts = []
    max_engine_error = 0.0
    for node_index, node_name in enumerate(NODE_ORDER):
        channels = []
        for axis in range(3):
            channel = 3 + node_index * 3 + axis
            channels.append(indices[channel * 2:channel * 2 + 2])
        counts = {pair[0] for pair in channels}
        if counts != {declared_frames}:
            raise ValueError(
                f"{name}/{node_name}: declared {declared_frames} frames but XYZ "
                f"channels contain {sorted(counts)}"
            )
        frame_counts.append(declared_frames)
        for frame in range(declared_frames):
            angles = tuple(decode_angle(values[offset + frame]) for _count, offset in channels)
            quaternion_matrix = q_to_matrix(q_from_euler_xyz(*angles))
            engine_matrix = sm64_mtxf_rotate_xyz(*angles)
            expected_engine_matrix = tuple(
                tuple(quaternion_matrix[col][row] for col in range(3))
                for row in range(3)
            )
            max_engine_error = max(
                max_engine_error,
                max_matrix_error(engine_matrix, expected_engine_matrix),
            )

    return {
        "name": name,
        "frame_count": declared_frames,
        "values_entries": len(values),
        "index_entries": len(indices),
        "max_engine_xyz_matrix_error": max_engine_error,
    }


def load_gta_idle_pose(path: Path) -> dict[str, tuple[float, ...]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "cj64-gta-idle-source-rest-v1":
        raise ValueError("Unsupported GTA source idle-pose format")
    nodes = data.get("nodes")
    if data.get("node_count") != 20 or not isinstance(nodes, list) or len(nodes) != 20:
        raise ValueError("GTA idle reference must contain exactly 20 nodes")
    result = {}
    names = []
    for index, item in enumerate(nodes):
        name = item.get("node")
        raw = item.get("base_rotation_xyzw")
        if item.get("node_index") != index or not isinstance(raw, list) or len(raw) != 4:
            raise ValueError(f"Invalid GTA idle reference at node {index}")
        if not isinstance(name, str) or name in result:
            raise ValueError(f"Invalid or duplicate GTA idle node {name!r}")
        result[name] = qnorm(tuple(float(value) for value in raw))
        names.append(name)
    if names != NODE_ORDER:
        raise ValueError("GTA idle reference order differs from the 20-node CS actor order")
    return result


def quaternion_error(a, b) -> float:
    dot = abs(sum(x * y for x, y in zip(qnorm(a), qnorm(b))))
    return 2.0 * math.acos(max(-1.0, min(1.0, dot)))


def convert_direct_table(source: str, pose_path: Path) -> tuple[str, dict[str, Any]]:
    if APPLIED_MARKER in source:
        raise ValueError("XYZ preservation marker is already present; refusing duplicate packaging")
    if "CJ64_CS_GTA_DIRECT_SM64_ZXY_CHANNEL_ORDER_APPLIED" in source:
        raise ValueError("Rejected ZXY-converted animation table; rebuild from the direct GTA source")

    engine_matrix_error = validate_engine_xyz_convention()
    reference_pose = load_gta_idle_pose(pose_path)
    tables = parse_tables(source)
    clip_reports = []
    idle_pose_error = None
    for table in tables:
        clip_report = validate_table(table)
        clip_reports.append(clip_report)
        if table["name"] == "cj64_anim_idle":
            node_errors = []
            for node_index, node_name in enumerate(NODE_ORDER):
                channels = []
                for axis in range(3):
                    channel = 3 + node_index * 3 + axis
                    count, offset = table["indices"][channel * 2:channel * 2 + 2]
                    if count != 46:
                        raise ValueError(f"{node_name}: expected the 46-frame IDLE_stance clip")
                    channels.append(decode_angle(table["values"][offset]))
                node_errors.append(
                    quaternion_error(q_from_euler_xyz(*channels), reference_pose[node_name])
                )
            idle_pose_error = max(node_errors)

    if idle_pose_error is None:
        raise ValueError("Direct GTA idle clip is missing")
    if idle_pose_error >= math.radians(0.02):
        raise ValueError(
            "Unmodified XYZ idle frame does not match the stored GTA source reference: "
            f"{math.degrees(idle_pose_error):.6f} degrees"
        )

    values_digest = hashlib.sha256()
    for table in tables:
        values_digest.update(table["name"].encode("utf-8"))
        values_digest.update(bytes(table["values"]))
        values_digest.update(bytes(table["indices"]))
    output = (
        "-- " + APPLIED_MARKER + "\n"
        "-- The source table already uses SM64 animated-part XYZ channel order.\n"
        "-- Values and index tables are preserved exactly; no quaternion/Euler re-encoding is applied.\n"
        "-- SM64CoopDX remains responsible for movement, heading, collision, camera and physics.\n"
        + source
    )
    report = {
        "format": "cj64-direct-gta-sm64-xyz-validation-report-v1",
        "source_pose": "GTA San Andreas IDLE_stance frame 0",
        "source_pose_file": pose_path.name,
        "target_nodes": NODE_ORDER,
        "clip_count": len(clip_reports),
        "root_translation": "fixed zero",
        "rotation_channel_order": "XYZ",
        "rotation_engine_function": "mtxf_rotate_xyz_and_translate",
        "rotation_conversion": "none; original 16-bit XYZ values preserved",
        "source_channel_values_preserved": True,
        "channel_values_sha256": values_digest.hexdigest(),
        "mario_pose_anchor_applied": False,
        "gta_idle_frame_zero_max_error_radians": idle_pose_error,
        "engine_matrix_crosscheck_max_error": engine_matrix_error,
        "rotation_basis_validation": "NOT_VALIDATED_FOR_COMPILED_CS_MESH",
        "clips": clip_reports,
        "status": "DIRECT_GTA_XYZ_CHANNELS_PRESERVED_REQUIRES_ANDROID_VISUAL_CHECK",
    }
    return output, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="direct GTA Lua table with original XYZ channels")
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
    args.output.with_suffix(".report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "clips": report["clip_count"],
        "nodes": len(report["target_nodes"]),
        "channel_order": report["rotation_channel_order"],
        "source_values_preserved": report["source_channel_values_preserved"],
        "gta_idle_frame_zero_error_degrees": math.degrees(
            report["gta_idle_frame_zero_max_error_radians"]
        ),
        "engine_matrix_crosscheck_max_error": report["engine_matrix_crosscheck_max_error"],
        "rotation_basis_validation": report["rotation_basis_validation"],
        "status": report["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
