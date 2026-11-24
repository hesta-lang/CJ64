#!/usr/bin/env python3
"""Convert retargeted GTA rotations to the SM64 engine's Z-X-Y matrix order.

The checked-in retarget table stores its intermediate local quaternion as XYZ
Euler angles. SM64 does not interpret those values as an XYZ rotation: its
animated-part matrix is built by applying Z, then X, then Y
(mtxf_rotate_zxy_and_translate). This tool decodes the intermediate quaternion,
composes it with the exact anim_00 frame-zero pose, and writes channels that
reconstruct the intended quaternion under SM64's ZXY convention.

Root translation channels remain zero so MarioState keeps control of movement.
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
SM64_ZXY_MARKER = "CJ64_CS_SM64_ZXY_CHANNEL_ORDER_APPLIED"


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





def q_axis(axis: str, radians: float):
    half = radians / 2.0
    sine, cosine = math.sin(half), math.cos(half)
    if axis == "x":
        return sine, 0.0, 0.0, cosine
    if axis == "y":
        return 0.0, sine, 0.0, cosine
    if axis == "z":
        return 0.0, 0.0, sine, cosine
    raise ValueError(f"Unknown quaternion axis {axis!r}")


def q_from_sm64_zxy(rx: float, ry: float, rz: float):
    """Return the quaternion for SM64's Ry * Rx * Rz matrix.

    The channel tuple is still stored as (X, Y, Z), but SM64 applies the
    rotations in the order Z, then X, then Y.
    """
    return qmul(q_axis("y", ry), qmul(q_axis("x", rx), q_axis("z", rz)))


def q_to_matrix(q):
    x, y, z, w = qnorm(q)
    return (
        (1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)),
        (2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)),
        (2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)),
    )


def _wrap_near(value: float, reference: float) -> float:
    return value + round((reference - value) / (2.0 * math.pi)) * (2.0 * math.pi)


def euler_sm64_zxy_near(q, reference=None):
    """Decompose a quaternion into SM64 ZXY channels near a reference pose.

    Choosing the equivalent Euler solution nearest the previous frame avoids
    180-degree representation flips in shoulder and thigh channels.
    """
    matrix = q_to_matrix(q)
    r00, r01, r02 = matrix[0]
    r10, r11, r12 = matrix[1]
    _r20, _r21, _r22 = matrix[2]

    sin_x = max(-1.0, min(1.0, -r12))
    cos_x = math.hypot(r02, _r22)
    if cos_x > 1e-8:
        rx = math.atan2(sin_x, cos_x)
        ry = math.atan2(r02, _r22)
        rz = math.atan2(r10, r11)
    else:
        rx = math.copysign(math.pi / 2.0, sin_x)
        rz = reference[2] if reference is not None else 0.0
        if sin_x >= 0.0:
            # At +90 degrees X, only (Y - Z) is observable.
            difference = math.atan2(r01, r00)
            ry = difference + rz
        else:
            # At -90 degrees X, only (Y + Z) is observable.
            total = math.atan2(-r01, r00)
            ry = total - rz

    if reference is None:
        reference = (0.0, 0.0, 0.0)
    alternate_x = math.pi - rx if rx >= 0.0 else -math.pi - rx
    candidates = (
        (rx, ry, rz),
        (alternate_x, ry + math.pi, rz + math.pi),
    )
    adjusted = [
        tuple(_wrap_near(angle, target) for angle, target in zip(candidate, reference))
        for candidate in candidates
    ]
    return min(
        adjusted,
        key=lambda candidate: sum((angle - target) ** 2
                                  for angle, target in zip(candidate, reference)),
    )


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


def load_native_pose(path: Path, expected_nodes: int = 20):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "cj64-native-cs-pose-anchor-sm64-zxy-v2":
        raise ValueError("Unsupported SM64 ZXY pose-anchor format")
    if data.get("rotation_order") != "SM64_ZXY_APPLIES_Z_THEN_X_THEN_Y":
        raise ValueError("Native pose file does not declare SM64's ZXY engine order")
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != expected_nodes:
        raise ValueError(f"Native pose anchor must have exactly {expected_nodes} nodes")
    names = []
    rotations = {}
    reference_angles = {}
    for index, item in enumerate(nodes):
        name = item.get("node")
        raw_angles = item.get("first_frame_euler16")
        stored_q = item.get("base_rotation_xyzw")
        if (not isinstance(name, str) or not name
                or not isinstance(raw_angles, list) or len(raw_angles) != 3
                or not isinstance(stored_q, list) or len(stored_q) != 4):
            raise ValueError(f"Invalid native pose entry at node index {index}")
        if item.get("index") != index:
            raise ValueError(f"Native pose entry {name!r} has incorrect index {item.get('index')}")
        if name in rotations:
            raise ValueError(f"Duplicate native pose node {name!r}")
        if any(not isinstance(value, str) or not re.fullmatch(r"[0-9A-Fa-f]{4}", value)
               for value in raw_angles):
            raise ValueError(f"{name}: first_frame_euler16 must contain three 16-bit hex values")
        angles = tuple(decode_angle(int(value, 16)) for value in raw_angles)
        q = q_from_sm64_zxy(*angles)
        stored = qnorm(stored_q)
        dot = abs(sum(a * b for a, b in zip(q, stored)))
        if 1.0 - min(1.0, dot) > 1e-7:
            raise ValueError(f"{name}: stored quaternion does not match SM64 ZXY frame-zero angles")
        if not all(math.isfinite(value) for value in q):
            raise ValueError(f"Non-finite SM64 ZXY base rotation for {name!r}")
        names.append(name)
        rotations[name] = q
        reference_angles[name] = angles
    if len(set(names)) != expected_nodes:
        raise ValueError("Native pose node names are not unique")
    return names, rotations, reference_angles

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
    base_euler_angles: dict[str, tuple[float, float, float]],
) -> tuple[list[int], float, float]:
    node_count = len(node_names)
    if len(indices) != (3 + node_count * 3) * 2:
        raise ValueError(f"Expected {(3 + node_count * 3) * 2} channel index entries, got {len(indices)}")

    output = list(values)
    max_first_frame_residual = 0.0
    max_frame_residual = 0.0

    # Preserve game-owned root translation exactly as supplied by the input.
    for axis in range(3):
        count, offset = indices[axis * 2:axis * 2 + 2]
        if count != 1 or offset >= len(values) or values[offset] != 0:
            raise ValueError(f"Root translation channel {axis} must contain one zero sample")

    for node_index, node_name in enumerate(node_names):
        base = base_rotations[node_name]
        previous_angles = base_euler_angles[node_name]
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
            intermediate_xyz = [
                decode_angle(values[offset + frame_index])
                for _count, offset in channels
            ]
            # The source Lua table is an intermediate XYZ-Euler serialization
            # of a retargeted quaternion. Decode it as generated, then re-encode
            # the composed result using SM64's actual ZXY matrix convention.
            motion_delta = q_from_euler_xyz(*intermediate_xyz)
            combined = qmul(base, motion_delta)
            sm64_angles = euler_sm64_zxy_near(combined, previous_angles)
            encoded_angles = [encode_angle(value) for value in sm64_angles]
            for axis, (_count, offset) in enumerate(channels):
                output[offset + frame_index] = encoded_angles[axis]

            reconstructed = q_from_sm64_zxy(*(
                decode_angle(value) for value in encoded_angles
            ))
            dot = abs(sum(a * b for a, b in zip(combined, reconstructed)))
            dot = max(-1.0, min(1.0, dot))
            residual = 2.0 * math.acos(dot)
            max_frame_residual = max(max_frame_residual, residual)
            if frame_index == 0:
                max_first_frame_residual = max(max_first_frame_residual, residual)
            previous_angles = tuple(decode_angle(value) for value in encoded_angles)

    return output, max_first_frame_residual, max_frame_residual

def apply_native_pose(source: str, pose_path: Path) -> tuple[str, dict[str, Any]]:
    if APPLIED_MARKER in source or SM64_ZXY_MARKER in source:
        raise ValueError("SM64 pose conversion has already been applied; refusing double application")
    node_names, base_rotations, base_euler_angles = load_native_pose(pose_path)
    registrations = parse_registrations(source)
    replacements = []
    clip_reports = []
    max_first_frame_residual = 0.0
    max_frame_residual = 0.0
    neutral_idle_residual = None

    for item in registrations:
        if len(item["indices"]) != 126:
            raise ValueError(f"{item['name']}: expected 126 index entries, got {len(item['indices'])}")
        output_values, first_residual, frame_residual = apply_pose_to_values(
            item["values"], item["indices"], node_names,
            base_rotations, base_euler_angles
        )
        max_first_frame_residual = max(max_first_frame_residual, first_residual)
        max_frame_residual = max(max_frame_residual, frame_residual)
        if item["name"] == "cj64_anim_idle":
            neutral_idle_residual = first_residual
        replacements.append((item["span"], format_values(output_values)))
        clip_reports.append({
            "name": item["name"],
            "values_entries": len(output_values),
            "index_entries": len(item["indices"]),
            "first_frame_quantization_residual_radians": first_residual,
            "max_frame_quantization_residual_radians": frame_residual,
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
        "-- " + SM64_ZXY_MARKER + "\n"
        "-- " + APPLIED_MARKER + "\n"
        "-- Native pose anchor: SM64 MARIO_ANIM_IDLE (anim_00), frame 0.\n"
        "-- SM64 engine order: apply Z, then X, then Y; channel storage remains X,Y,Z.\n"
        "-- Intermediate retarget quaternions are decoded from XYZ Euler and emitted as SM64 ZXY channels.\n"
        + output
    )

    report = {
        "format": "cj64-sm64-zxy-pose-application-report-v1",
        "source_native_animation": "MARIO_ANIM_IDLE (anim_00), frame 0",
        "source_pose_file": pose_path.name,
        "target_nodes": node_names,
        "clip_count": len(clip_reports),
        "native_engine_rotation_order": "SM64 ZXY (apply Z then X then Y; matrix Ry * Rx * Rz)",
        "input_delta_encoding": "intermediate retarget quaternion serialized as XYZ Euler",
        "output_channel_order": "SM64 XYZ channel storage interpreted by ZXY engine matrix",
        "max_first_frame_quantization_residual_radians": max_first_frame_residual,
        "max_frame_quantization_residual_radians": max_frame_residual,
        "neutral_idle_first_frame_residual_radians": neutral_idle_residual,
        "body_base_euler_degrees": [
            round(math.degrees(value), 6)
            for value in base_euler_angles["Body"]
        ],
        "root_translation": "preserved zero; SM64CoopDX owns movement",
        "composition": "native_anim_00_SM64_ZXY_pose * GTA_local_motion_delta",
        "clips": clip_reports,
        "status": "SM64_ZXY_CHANNELS_STRUCTURALLY_VALIDATED_REQUIRES_ANDROID_VISUAL_CHECK",
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
        "max_first_frame_quantization_residual_radians": report["max_first_frame_quantization_residual_radians"],
        "max_frame_quantization_residual_radians": report["max_frame_quantization_residual_radians"],
        "neutral_idle_first_frame_residual_radians": report["neutral_idle_first_frame_residual_radians"],
        "rotation_order": report["native_engine_rotation_order"],
        "status": report["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
