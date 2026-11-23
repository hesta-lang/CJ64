#!/usr/bin/env python3
"""Neutral-pose calibration for CJ64's private GTA/SM64 Lua animation tables."""
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


def qnorm(q):
    length = math.sqrt(sum(value * value for value in q))
    if not math.isfinite(length) or length < 1e-12:
        raise ValueError("zero-length or invalid quaternion")
    return tuple(value / length for value in q)


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def qinv(q):
    x, y, z, w = qnorm(q)
    return (-x, -y, -z, w)


def q_from_euler_xyz(rx, ry, rz):
    cr, sr = math.cos(rx / 2), math.sin(rx / 2)
    cp, sp = math.cos(ry / 2), math.sin(ry / 2)
    cy, sy = math.cos(rz / 2), math.sin(rz / 2)
    return qnorm((
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    ))


def euler_xyz(q):
    x, y, z, w = qnorm(q)
    rx = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    sin_y = 2 * (w * y - z * x)
    ry = math.copysign(math.pi / 2, sin_y) if abs(sin_y) >= 1 else math.asin(sin_y)
    rz = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return rx, ry, rz


def decode_angle(value):
    signed = value - 65536 if value >= 32768 else value
    return signed * (2 * math.pi / 65536)


def encode_angle(radians):
    return int(round(radians * 65536 / (2 * math.pi))) & 0xFFFF


def parse_hex_values(block, label):
    tokens = list(HEX_RE.finditer(block))
    remainder = HEX_RE.sub("", block).strip(" \t\r\n,")
    if remainder:
        raise ValueError(f"Unexpected text in {label} table: {remainder[:40]!r}")
    return [int(match.group(1), 16) for match in tokens]


def parse_registrations(source):
    registrations = []
    for match in REGISTER_RE.finditer(source):
        registrations.append({
            "name": match.group("name"),
            "header": match.group("header").strip(),
            "values": parse_hex_values(match.group("values"), f"{match.group('name')} values"),
            "indices": parse_hex_values(match.group("indices"), f"{match.group('name')} indices"),
            "values_span": match.span("values"),
        })
    expected = source.count("smlua_anim_util_register_animation(")
    if len(registrations) != expected:
        raise ValueError(f"Parsed {len(registrations)} of {expected} animation registrations")
    return registrations


def channel_samples(values, indices, channel_index):
    count, offset = indices[channel_index * 2:channel_index * 2 + 2]
    return values[offset:offset + count]


def validate_registration(registration, expected_channels):
    name, values, indices = registration["name"], registration["values"], registration["indices"]
    if len(indices) != expected_channels * 2:
        raise ValueError(f"{name}: has {len(indices) // 2} channels; expected {expected_channels}")
    for channel_index in range(expected_channels):
        count, offset = indices[channel_index * 2:channel_index * 2 + 2]
        if count < 1:
            raise ValueError(f"{name}: channel {channel_index} has no samples")
        if offset + count > len(values):
            raise ValueError(f"{name}: channel {channel_index} points outside values table")

    # Player position and world movement stay under MarioState control.
    for channel_index in range(3):
        count, offset = indices[channel_index * 2:channel_index * 2 + 2]
        if count != 1 or values[offset] != 0:
            raise ValueError(f"{name}: root translation channel {channel_index} is not fixed zero")

    fields = registration["header"].split(",")
    try:
        declared_samples = int(fields[-1].strip(), 0) + 1
    except (ValueError, IndexError) as exc:
        raise ValueError(f"{name}: cannot read last-frame value from animation header") from exc
    if declared_samples < 1:
        raise ValueError(f"{name}: invalid frame count in animation header")

    for node in range((expected_channels - 3) // 3):
        counts = [indices[(3 + node * 3 + axis) * 2] for axis in range(3)]
        if len(set(counts)) != 1:
            raise ValueError(f"{name}: node {node} XYZ sample counts differ: {counts}")
        if counts[0] != declared_samples:
            raise ValueError(
                f"{name}: node {node} has {counts[0]} samples but header declares {declared_samples}"
            )


def format_values(values):
    lines = []
    for start in range(0, len(values), 12):
        line = ", ".join(f"0x{value:04X}" for value in values[start:start + 12]) + ","
        lines.append(line if start == 0 else "        " + line)
    return "\n".join(lines)


def unwrap_angles(frames):
    result = [list(frame) for frame in frames]
    for frame_index in range(1, len(result)):
        for axis in range(3):
            current, previous = result[frame_index][axis], result[frame_index - 1][axis]
            while current - previous > math.pi:
                current -= 2 * math.pi
            while current - previous < -math.pi:
                current += 2 * math.pi
            result[frame_index][axis] = current
    return [tuple(frame) for frame in result]


def calibrate_text(source, *, reference="cj64_anim_idle", nodes=20):
    if nodes < 1:
        raise ValueError("nodes must be at least 1")
    registrations = parse_registrations(source)
    if not registrations:
        raise ValueError("No animation registrations found")
    names = [item["name"] for item in registrations]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate animation registration names")

    expected_channels = 3 + nodes * 3
    for item in registrations:
        validate_registration(item, expected_channels)
    reference_item = next((item for item in registrations if item["name"] == reference), None)
    if reference_item is None:
        raise ValueError(f"Reference animation not found: {reference}")

    bases = []
    for node in range(nodes):
        angles = [
            decode_angle(channel_samples(
                reference_item["values"], reference_item["indices"], 3 + node * 3 + axis
            )[0])
            for axis in range(3)
        ]
        bases.append(q_from_euler_xyz(*angles))

    replacements, clip_reports = [], []
    max_reference_residual = 0.0
    max_any_clip_residual = 0.0
    for item in registrations:
        values, indices = item["values"], item["indices"]
        output_values = list(values)
        sample_counts = []
        for node, base in enumerate(bases):
            axes = [
                channel_samples(values, indices, 3 + node * 3 + axis)
                for axis in range(3)
            ]
            sample_count = len(axes[0])
            sample_counts.append(sample_count)
            frames = []
            for frame_index in range(sample_count):
                absolute = q_from_euler_xyz(*(
                    decode_angle(axes[axis][frame_index]) for axis in range(3)
                ))
                relative = qnorm(qmul(qinv(base), absolute))
                frames.append(euler_xyz(relative))
            frames = unwrap_angles(frames)
            residual = max(abs(value) for value in frames[0])
            max_any_clip_residual = max(max_any_clip_residual, residual)
            if item["name"] == reference:
                max_reference_residual = max(max_reference_residual, residual)
            for axis in range(3):
                _count, offset = indices[(3 + node * 3 + axis) * 2:(3 + node * 3 + axis) * 2 + 2]
                for frame_index, frame in enumerate(frames):
                    output_values[offset + frame_index] = encode_angle(frame[axis])

        if len(output_values) != len(values):
            raise AssertionError(f"{item['name']}: value table length changed")
        replacements.append((item["values_span"], format_values(output_values)))
        clip_reports.append({
            "name": item["name"],
            "channels": len(indices) // 2,
            "values_entries": len(output_values),
            "rotation_frames_min": min(sample_counts),
            "rotation_frames_max": max(sample_counts),
            "last_frame_parameter": item["header"].split(",")[-1].strip(),
        })

    output = source
    for (start, end), replacement in reversed(replacements):
        output = output[:start] + replacement + output[end:]

    report = {
        "format": "cj64-cs-animation-calibration-report-v2",
        "reference_animation": reference,
        "target_node_count": nodes,
        "channel_count_per_clip": expected_channels,
        "calibration": "inverse(reference_idle_first_pose) * current_pose",
        "root_translation": "preserved_fixed_zero",
        "clip_count": len(clip_reports),
        "max_neutral_first_frame_residual_radians": max_reference_residual,
        "max_any_clip_first_frame_residual_radians": max_any_clip_residual,
        "neutral_reference_identity": max_reference_residual < math.radians(0.02),
        "visual_validation": False,
        "in_game_validation": False,
        "clips": clip_reports,
        "limitations": [
            "The CS actor has 20 animated parts, not the full GTA ped skeleton.",
            "Individual finger, toe, breast and belly tracks cannot be represented independently.",
            "This is a neutral-pose-calibrated best-fit retarget, not exact GTA skeleton parity.",
            "The converted clips still require visual and in-game validation.",
        ],
    }
    return output, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="private generated animation Lua module")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", default="cj64_anim_idle")
    parser.add_argument("--nodes", type=int, default=20)
    args = parser.parse_args()
    try:
        source = args.source.read_text(encoding="utf-8")
        output, report = calibrate_text(source, reference=args.reference, nodes=args.nodes)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    report.update({
        "source_module": args.source.name,
        "output_module": args.output.name,
        "output_bytes": args.output.stat().st_size,
    })
    args.output.with_suffix(".report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "animations": report["clip_count"],
        "nodes": report["target_node_count"],
        "neutral_reference_identity": report["neutral_reference_identity"],
        "max_neutral_residual_radians": report["max_neutral_first_frame_residual_radians"],
        "max_any_clip_first_frame_residual_radians": report["max_any_clip_first_frame_residual_radians"],
        "visual_validation": report["visual_validation"],
        "in_game_validation": report["in_game_validation"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
