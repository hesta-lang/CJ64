#!/usr/bin/env python3
"""Restore original GTA IDLE_stance pose on neutral-relative CS retarget tables.

This replaces the previous Mario anim_C5 overlay. The CS model binary remains
unchanged; every GTA local channel is restored using the corresponding original
GTA idle-pose quaternion before it is emitted as an SM64 16-bit Euler channel.
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
RESTORED_MARKER = "CJ64_GTA_SOURCE_IDLE_POSE_RESTORED"


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


def qdot(a, b):
    return sum(x * y for x, y in zip(qnorm(a), qnorm(b)))


def quat_error(a, b):
    dot = max(-1.0, min(1.0, abs(qdot(a, b))))
    return 2.0 * math.acos(dot)


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
        raise ValueError(f"Unexpected text in {label}: {remainder[:60]!r}")
    return [int(match.group(1), 16) for match in tokens]


def format_values(values: list[int]) -> str:
    return "\n".join(
        "        " + ", ".join(f"0x{v:04X}" for v in values[i:i + 12]) + ","
        for i in range(0, len(values), 12)
    )


def parse_registrations(source: str) -> list[dict[str, Any]]:
    result = []
    for match in REGISTRATION_RE.finditer(source):
        result.append({
            "name": match.group("name"),
            "header": match.group("header").strip(),
            "values": parse_hex_values(match.group("values"), match.group("name") + " values"),
            "indices": parse_hex_values(match.group("indices"), match.group("name") + " indices"),
            "values_span": match.span("values"),
        })
    expected = source.count("smlua_anim_util_register_animation(")
    if len(result) != expected or not result:
        raise ValueError(f"parsed {len(result)} of {expected} animation registrations")
    if len({item["name"] for item in result}) != len(result):
        raise ValueError("duplicate animation registration names")
    return result


def load_pose(path: Path, node_count: int = 20):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "cj64-gta-idle-source-rest-v1":
        raise ValueError("unsupported GTA source idle-pose format")
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != node_count:
        raise ValueError(f"source idle-pose map must contain {node_count} nodes")
    result = []
    for index, item in enumerate(nodes):
        if item.get("node_index") != index:
            raise ValueError(f"source idle-pose node index mismatch at {index}")
        quat = qnorm(item.get("base_rotation_xyzw", []))
        if len(quat) != 4 or not all(math.isfinite(v) for v in quat):
            raise ValueError(f"invalid source idle quaternion for node {index}")
        result.append(quat)
    return result


def read_node_quaternion(values, indices, node_index, frame):
    angles = []
    for axis in range(3):
        channel = 3 + node_index * 3 + axis
        count, offset = indices[channel * 2:channel * 2 + 2]
        if count < 1 or offset + count > len(values) or frame >= count:
            raise ValueError(f"node {node_index}: invalid axis {axis} sample at frame {frame}")
        angles.append(decode_angle(values[offset + frame]))
    return q_from_euler_xyz(*angles)


def restore_pose(source: str, pose_path: Path, *, expected_clips: int = 13, nodes: int = 20):
    if RESTORED_MARKER in source:
        raise ValueError("GTA source idle pose was already restored")
    if "CJ64_NATIVE_MARIO_IDLE_POSE_ANCHOR_APPLIED" in source:
        raise ValueError("input already has the Mario anim_C5 anchor; expected pre-anchor normalized tables")
    bases = load_pose(pose_path, nodes)
    records = parse_registrations(source)
    if len(records) != expected_clips:
        raise ValueError(f"expected {expected_clips} GTA clips, found {len(records)}")

    expected_channels = 3 + nodes * 3
    replacements = []
    clip_reports = []
    max_idle_residual = 0.0
    max_quantized_residual = 0.0
    idle_record = next((r for r in records if r["name"] == "cj64_anim_idle"), None)
    if idle_record is None:
        raise ValueError("required cj64_anim_idle clip is missing")

    for record in records:
        values = record["values"]
        indices = record["indices"]
        if len(indices) != expected_channels * 2:
            raise ValueError(f"{record['name']}: expected {expected_channels} channels")
        for axis in range(3):
            count, offset = indices[axis * 2:axis * 2 + 2]
            if count != 1 or offset >= len(values) or values[offset] != 0:
                raise ValueError(f"{record['name']}: root translation channel {axis} must stay fixed zero")

        frame_counts = []
        for node in range(nodes):
            counts = []
            for axis in range(3):
                channel = 3 + node * 3 + axis
                count, offset = indices[channel * 2:channel * 2 + 2]
                if count < 1 or offset + count > len(values):
                    raise ValueError(f"{record['name']}: invalid node {node} axis {axis} table")
                counts.append(count)
            if len(set(counts)) != 1:
                raise ValueError(f"{record['name']}: node {node} XYZ counts differ")
            frame_counts.append(counts[0])
        if len(set(frame_counts)) != 1:
            raise ValueError(f"{record['name']}: node frame counts differ")
        frame_count = frame_counts[0]
        declared_frames = int(record["header"].split(",")[-1].strip(), 0) + 1
        if frame_count != declared_frames:
            raise ValueError(f"{record['name']}: header declares {declared_frames} frames, channels have {frame_count}")

        # The source table is q_delta = inverse(GTA_idle_source_pose) * q_GTA_pose.
        # Restore q_GTA_pose = GTA_idle_source_pose * q_delta. This uses GTA's
        # actual IDLE_stance reference, not a Mario/anim_C5 animation frame.
        output_values = list(values)
        residual_before = 0.0
        residual_after = 0.0
        for node, base in enumerate(bases):
            for frame in range(frame_count):
                delta = read_node_quaternion(values, indices, node, frame)
                absolute = qmul(base, delta)
                angles = euler_xyz(absolute)
                channel_offsets = []
                for axis in range(3):
                    channel = 3 + node * 3 + axis
                    count, offset = indices[channel * 2:channel * 2 + 2]
                    channel_offsets.append(offset + frame)
                    output_values[offset + frame] = encode_angle(angles[axis])
                decoded = q_from_euler_xyz(*(
                    decode_angle(output_values[offset]) for offset in channel_offsets
                ))
                residual_after = max(residual_after, quat_error(absolute, decoded))
                if frame == 0 and record["name"] == "cj64_anim_idle":
                    residual_before = max(residual_before, quat_error(base, absolute))

        if record["name"] == "cj64_anim_idle":
            max_idle_residual = max(max_idle_residual, residual_before)
        max_quantized_residual = max(max_quantized_residual, residual_after)
        replacements.append((record["values_span"], format_values(output_values)))
        clip_reports.append({
            "name": record["name"],
            "frames": frame_count,
            "channels": len(indices) // 2,
            "idle_reference_source": "original GTA IDLE_stance frame 0",
            "c5_pose_composed": False,
            "max_quantized_rotation_error_radians": residual_after,
        })

    output = source
    for (start, end), replacement in reversed(replacements):
        output = output[:start] + replacement + output[end:]
    output = (
        "-- " + RESTORED_MARKER + "\n"
        "-- Restored the original GTA IDLE_stance frame-zero pose on all 20 CS animated parts.\n"
        "-- No Mario anim_C5 animation frame or Mario pose anchor is applied.\n"
        + output
    )
    report = {
        "format": "cj64-gta-source-idle-pose-restoration-v1",
        "target_model": "original Character Select actor, actors/cj/mario_geo.bin (copied byte-for-byte)",
        "target_animation_nodes": nodes,
        "clip_count": len(clip_reports),
        "source_pose": "GTA ped.ifp IDLE_stance frame 0",
        "composition": "q_absolute = q_GTA_idle_source * q_relative_motion",
        "native_mario_anim_C5_used": False,
        "root_translation": "preserved fixed zero; SM64CoopDX controls player/world motion",
        "max_idle_reference_residual_radians": max_idle_residual,
        "max_quantized_rotation_error_radians": max_quantized_residual,
        "clips": clip_reports,
        "status": "GTA_SOURCE_POSE_RESTORED_STRUCTURAL_ONLY_REQUIRES_ANDROID_VISUAL_VALIDATION",
    }
    return output, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="neutral-relative GTA Lua table before Mario C5 anchoring")
    parser.add_argument("--pose", type=Path, default=Path("tools/gta_idle_source_pose.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.read_text(encoding="utf-8")
    output, report = restore_pose(source, args.pose)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    report.update({
        "source_module": args.source.name,
        "output_module": args.output.name,
        "output_bytes": args.output.stat().st_size,
    })
    args.output.with_suffix(".source-pose-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "output": str(args.output),
        "clips": report["clip_count"],
        "nodes": report["target_animation_nodes"],
        "native_mario_anim_C5_used": report["native_mario_anim_C5_used"],
        "max_idle_reference_residual_radians": report["max_idle_reference_residual_radians"],
        "max_quantized_rotation_error_radians": report["max_quantized_rotation_error_radians"],
        "status": report["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
