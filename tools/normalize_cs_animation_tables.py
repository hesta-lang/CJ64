#!/usr/bin/env python3
"""Neutral-pose calibration for CJ64's private GTA/SM64 Lua animation tables.

The input tables already contain 20 Fast64/Mario animated-part channels. This
utility removes the static first-frame orientation of a trusted neutral idle
clip from each node, then preserves each clip's motion relative to that pose.
It does not manufacture missing GTA joints or prove visual/in-game correctness.
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


def qnorm(q: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    magnitude = math.sqrt(sum(value * value for value in q))
    if not math.isfinite(magnitude) or magnitude < 1e-12:
        raise ValueError("zero-length or invalid quaternion")
    return tuple(value / magnitude for value in q)  # type: ignore[return-value]


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


def q_from_euler_xyz(rx: float, ry: float, rz: float):
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


def signed16(value: int) -> int:
    return value - 65536 if value >= 32768 else value


def decode_angle(value: int) -> float:
    return signed16(value) * (2 * math.pi / 65536)


def encode_angle(radians: float) -> int:
    return int(round(radians * 65536 / (2 * math.pi))) & 0xFFFF


def parse_hex_values(block: str, label: str) -> list[int]:
    tokens = list(HEX_RE.finditer(block))
    remainder = HEX_RE.sub("", block).strip(" \t\r\n,")
    if remainder:
        raise ValueError(f"Unexpected text in {label} table: {remainder[:40]!r}")
    return [int(match.group(1), 16) for match in tokens]


def parse_registrations(source: str) -> list[dict[str, Any]]:
    registrations = []
    for match in REGISTER_RE.finditer(source):
        values = parse_hex_values(match.group("values"), f"{match.group('name')} values")
        indices = parse_hex_values(match.group("indices"), f"{match.group('name')} indices")
        registrations.append({
            "name": match.group("name"),
            "header": match.group("header").strip(),
            "values": values,
            "indices": indices,
            "values_span": match.span("values"),
            "match": match,
        })
    return registrations


def validate_registration(registration: dict[str, Any], expected_channels: int) -> None:
    name = registration["name"]
    values = registration["values"]
    indices = registration["indices"]
    if len(indices) != expected_channels * 2:
        raise ValueError(
            f"{name}: has {len(indices) // 2} channels; expected {expected_channels}"
        )
    for channel_index in range(expected_channels):
        count, offset = indices[channel_index * 2:channel_index * 2 + 2]
        if count < 1:
            raise ValueError(f"{name}: channel {channel_index} has no samples")
        if offset + count > len(values):
            raise ValueError(
                f"{name}: channel {channel_index} range [{offset}, {offset + count}) "
                f"exceeds {len(values)} values"
            )

    # The three translation channels must remain one-sample zeroes. MarioState
    # owns world movement; these arrays may not override it.
    for channel_index in range(3):
        count, offset = indices[channel_index * 2:channel_index * 2 + 2]
        if count != 1 or values[offset] != 0:
            raise ValueError(
                f"{name}: root translation channel {channel_index} is not fixed zero"
            )

    for node in range((expected_channels - 3) // 3):
        counts = [indices[(3 + node * 3 + axis) * 2] for axis in range(3)]
        if len(set(counts)) != 1:
            raise ValueError(f"{name}: node {node} XYZ sample counts differ: {counts}")


def channel_samples(values: list[int], indices: list[int], channel_index: int) -> list[int]:
    count, offset = indices[channel_index * 2:channel_index * 2 + 2]
    return values[offset:offset + count]


def format_values(values: list[int]) -> str:
    lines = []
    for start in range(0, len(values), 12):
        line = ", ".join(f"0x{value:04X}" for value in values[start:start + 12]) + ","
        lines.append(line if start == 0 else "        " + line)
    return "\n".join(lines)


def unwrap_angles(frames: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    result = [list(frame) for frame in frames]
    for frame_index in range(1, len(result)):
        for axis in range(3):
            current = result[frame_index][axis]
            previous = result[frame_index - 1][axis]
            while current - previous > math.pi:
                current -= 2 * math.pi
            while current - previous < -math.pi:
                current += 2 * math.pi
            result[frame_index][axis] = current
    return [tuple(frame) for frame in result]  # type: ignore[return-value]


def calibrate_text(
    source: str,
    *,
    reference: str = "cj64_anim_idle",
    nodes: int = 20,
) -> tuple[str, dict[str, Any]]:
    if nodes < 1:
        raise ValueError("nodes must be at least 1")
    registrations = parse_registrations(source)
    if not registrations:
        raise ValueError("No animation registrations found")

    names = [registration["name"] for registration in registrations]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate animation registration names")

    expected_channels = 3 + nodes * 3
    for registration in registrations:
        validate_registration(registration, expected_channels)

    reference_registration = next(
        (item for item in registrations if item["name"] == reference), None
    )
    if reference_registration is None:
        raise ValueError(f"Reference animation not found: {reference}")

    reference_values = reference_registration["values"]
    reference_indices = reference_registration["indices"]
    bases = []
    for node in range(nodes):
        angles = []
        for axis in range(3):
            sample = channel_samples(reference_values, reference_indices, 3 + node * 3 + axis)
            angles.append(decode_angle(sample[0]))
        bases.append(q_from_euler_xyz(*angles))

    replacements = []
    clip_reports = []
    max_reference_first_frame_residual = 0.0
    max_any_clip_first_frame_residual = 0.0
    for registration in registrations:
        values = registration["values"]
        indices = registration["indices"]
        output_values = list(values)
        rotation_sample_counts = []

        for node, base in enumerate(bases):
            per_axis = [
                channel_samples(values, indices, 3 + node * 3 + axis)
                for axis in range(3)
            ]
            sample_count = len(per_axis[0])
            rotation_sample_counts.append(sample_count)
            relative_frames = []
            for frame_index in range(sample_count):
                absolute = q_from_euler_xyz(*(
                    decode_angle(per_axis[axis][frame_index]) for axis in range(3)
                ))
                relative = qnorm(qmul(qinv(base), absolute))
                relative_frames.append(euler_xyz(relative))
            relative_frames = unwrap_angles(relative_frames)

            first_residual = max(abs(value) for value in relative_frames[0])
            max_any_clip_first_frame_residual = max(
                max_any_clip_first_frame_residual, first_residual
            )
            if registration["name"] == reference:
                max_reference_first_frame_residual = max(
                    max_reference_first_frame_residual, first_residual
                )
            for axis in range(3):
                channel_index = 3 + node * 3 + axis
                _count, offset = indices[channel_index * 2:channel_index * 2 + 2]
                for frame_index, frame in enumerate(relative_frames):
                    output_values[offset + frame_index] = encode_angle(frame[axis])

        if len(output_values) != len(values):
            raise AssertionError(f"{registration['name']}: values length changed during calibration")
        replacements.append((registration["values_span"], format_values(output_values)))
        clip_reports.append({
            "name": registration["name"],
            "channels": len(indices) // 2,
            "values_entries": len(output_values),
            "rotation_frames_min": min(rotation_sample_counts),
            "rotation_frames_max": max(rotation_sample_counts),
            "last_frame_parameter": registration["header"].split(",")[-1].strip(),
        })

    calibrated = source
    for (start, end), replacement in reversed(replacements):
        calibrated = calibrated[:start] + replacement + calibrated[end:]

    report = {
        "format": "cj64-cs-animation-calibration-report-v2",
        "reference_animation": reference,
        "target_node_count": nodes,
        "channel_count_per_clip": expected_channels,
        "calibration": "inverse(reference_idle_first_pose) * current_pose",
        "root_translation": "preserved_fixed_zero",
        "clip_count": len(clip_reports),
        "max_neutral_first_frame_residual_radians": max_reference_first_frame_residual,
        "max_any_clip_first_frame_residual_radians": max_any_clip_first_frame_residual,
        "neutral_reference_identity": max_reference_first_frame_residual < math.radians(0.02),
        "visual_validation": False,
        "in_game_validation": False,
        "clips": clip_reports,
        "limitations": [
            "The CS actor has 20 animated parts, not the full GTA ped skeleton.",
            "Individual finger, toe, breast and belly tracks cannot be represented independently.",
            "This is a neutral-pose-calibrated best-fit retarget, not exact GTA skeleton parity.",
            "The current actor's neutral pose and the converted clips still require in-game visual validation.",
        ],
    }
    return calibrated, report


def main() -> int:
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
    report["source_module"] = args.source.name
    report["output_module"] = args.output.name
    report["output_bytes"] = args.output.stat().st_size
    report_path = args.output.with_suffix(".report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
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
