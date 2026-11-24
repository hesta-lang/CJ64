#!/usr/bin/env python3
"""Rebase GTA animation channels from native-CS parent frames to CJ FBX rest frames.

The input Lua tables are the existing GTA San Andreas retarget result before the
Mario anim_C5 pose anchor is applied. This converts each per-node local channel
so the same articulated global motion is expressed in the actual CJ/FBX rest
frames emitted by the source-rest Fast64 export.
"""
from __future__ import annotations
import argparse
import json
import math
import re
from pathlib import Path

REGISTRATION_RE = re.compile(
    r'(smlua_anim_util_register_animation\(\s*"(?P<name>[^"]+)"\s*,\s*'
    r'(?P<header>.*?)\s*,\s*\{\s*)'
    r'(?P<values>.*?)'
    r'(\s*\},\s*\{\s*)'
    r'(?P<indices>.*?)'
    r'(\s*\}\s*\))', re.S,
)
HEX_RE = re.compile(r"0x([0-9A-Fa-f]{1,4})")
IDENTITY = (0.0, 0.0, 0.0, 1.0)


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
    sin_y = 2 * (w * y - z * x)
    if sin_y >= 1.0 - 1e-7:
        return 2 * math.atan2(x, w), math.pi / 2, 0.0
    if sin_y <= -1.0 + 1e-7:
        return 2 * math.atan2(-z, w), -math.pi / 2, 0.0
    rx = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    ry = math.asin(max(-1.0, min(1.0, sin_y)))
    rz = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return rx, ry, rz


def decode_angle(value):
    signed = value - 65536 if value >= 32768 else value
    return signed * (2 * math.pi / 65536.0)


def encode_angle(value):
    return int(round(value * 65536 / (2 * math.pi))) & 0xFFFF


def parse_values(block, label):
    tokens = list(HEX_RE.finditer(block))
    rest = HEX_RE.sub("", block).strip(" \t\r\n,")
    if rest:
        raise ValueError(f"Unexpected text in {label}: {rest[:60]!r}")
    return [int(x.group(1), 16) for x in tokens]


def fmt_values(values):
    return "\n".join(
        "        " + ", ".join(f"0x{x:04X}" for x in values[i:i + 12]) + ","
        for i in range(0, len(values), 12)
    )


def from_wxyz(q):
    if not isinstance(q, list) or len(q) != 4:
        raise ValueError("expected WXYZ quaternion")
    return qnorm((q[1], q[2], q[3], q[0]))


def parse_map(path):
    m = json.loads(Path(path).read_text(encoding="utf-8"))
    if m.get("generated_from_actual_rig") is not True:
        raise ValueError("retarget map must come from the actual CJ/Fast64 rig export")
    nodes = m.get("target_node_order")
    parents = m.get("target_parent_animation_node")
    old_raw = m.get("native_mario_parent_rest_rotation_wxyz")
    new_raw = m.get("target_parent_rest_rotation_wxyz")
    if not isinstance(nodes, list) or len(nodes) != 20 or len(set(nodes)) != 20:
        raise ValueError("retarget map must describe exactly 20 unique target nodes")
    for label, obj in (("parent tree", parents), ("native CS parent rest", old_raw), ("CJ FBX parent rest", new_raw)):
        if not isinstance(obj, dict) or set(obj) != set(nodes):
            raise ValueError(f"retarget map does not contain complete {label} data")
    old_rest = {n: from_wxyz(old_raw[n]) for n in nodes}
    new_rest = {n: from_wxyz(new_raw[n]) for n in nodes}
    for node in nodes:
        parent = parents[node]
        if node == "Body":
            if parent is not None:
                raise ValueError("Body must be the root animation node")
        elif parent is None or parent not in nodes:
            raise ValueError(f"{node}: invalid or missing animated parent {parent!r}")
        for label, quaternion in (("native", old_rest[node]), ("CJ", new_rest[node])):
            if not all(math.isfinite(v) for v in quaternion):
                raise ValueError(f"{node}: non-finite {label} rest quaternion")
    if nodes[0] != "Body":
        raise ValueError("Body must be the first animation node")
    return m, nodes, parents, old_rest, new_rest


def parse_lua(source):
    records = []
    for match in REGISTRATION_RE.finditer(source):
        records.append({
            "name": match.group("name"),
            "header": match.group("header").strip(),
            "values": parse_values(match.group("values"), match.group("name") + " values"),
            "indices": parse_values(match.group("indices"), match.group("name") + " indices"),
            "values_span": match.span("values"),
        })
    expected = source.count("smlua_anim_util_register_animation(")
    if expected != len(records) or not records:
        raise ValueError(f"parsed {len(records)} of {expected} animation registrations")
    return records


def read_node_local_quat(values, indices, node_index, frame):
    angles = []
    for axis in range(3):
        channel = 3 + node_index * 3 + axis
        count, offset = indices[channel * 2:channel * 2 + 2]
        if count <= 0 or offset + count > len(values) or frame >= count:
            raise ValueError(f"node {node_index}: invalid channel {axis} or frame {frame}")
        angles.append(decode_angle(values[offset + frame]))
    return q_from_euler_xyz(*angles)


def quat_error(a, b):
    dot = min(1.0, abs(sum(x * y for x, y in zip(qnorm(a), qnorm(b)))))
    return 2 * math.acos(dot)


def rebase_registration(record, nodes, parents, old_rest, new_rest):
    values = list(record["values"])
    indices = record["indices"]
    if len(indices) != 126:
        raise ValueError(f"{record['name']}: expected 126 channel index entries")
    if len(values) >= 65536:
        raise ValueError(f"{record['name']}: animation value table exceeds 16-bit offsets")

    frame_counts = []
    for node_index in range(len(nodes)):
        for axis in range(3):
            channel = (3 + node_index * 3 + axis) * 2
            count, offset = indices[channel:channel + 2]
            if count <= 0 or offset + count > len(values):
                raise ValueError(f"{record['name']}: invalid node {node_index} channel {axis}")
            frame_counts.append(count)
    if len(set(frame_counts)) != 1:
        raise ValueError(f"{record['name']}: inconsistent node frame counts")
    frame_count = frame_counts[0]

    for axis in range(3):
        count, offset = indices[axis * 2:axis * 2 + 2]
        if count != 1 or offset >= len(values) or values[offset] != 0:
            raise ValueError(f"{record['name']}: root translation axis {axis} must remain zero")

    rebased_locals = {name: [IDENTITY] * frame_count for name in nodes}
    expected_global_per_frame = []
    max_pre_encode_error = 0.0

    for frame in range(frame_count):
        old_global = {"Body": IDENTITY}
        new_global = {"Body": IDENTITY}
        frame_expected = {"Body": IDENTITY}
        for node_index, node in enumerate(nodes):
            if node == "Body":
                continue
            parent = parents[node]
            if parent not in old_global or parent not in new_global:
                raise ValueError(f"{record['name']}: {node} parent is not topologically ordered")
            local_old = read_node_local_quat(values, indices, node_index, frame)
            old_global[node] = qmul(
                qmul(qmul(old_global[parent], old_rest[node]), local_old),
                qinv(old_rest[node]),
            )
            local_new = qmul(
                qmul(qmul(qinv(new_rest[node]), qinv(new_global[parent])), old_global[node]),
                new_rest[node],
            )
            rebased_locals[node][frame] = local_new
            new_global[node] = qmul(
                qmul(qmul(new_global[parent], new_rest[node]), local_new),
                qinv(new_rest[node]),
            )
            frame_expected[node] = old_global[node]
            max_pre_encode_error = max(max_pre_encode_error, quat_error(old_global[node], new_global[node]))
        expected_global_per_frame.append(frame_expected)

    for node_index, node in enumerate(nodes):
        axis_angles = [list(euler_xyz(q)) for q in rebased_locals[node]]
        if node == "Body":
            axis_angles = [(0.0, 0.0, 0.0)] * frame_count
        for axis in range(3):
            series = [frame[axis] for frame in axis_angles]
            for frame in range(1, frame_count):
                while series[frame] - series[frame - 1] > math.pi:
                    series[frame] -= 2 * math.pi
                while series[frame] - series[frame - 1] < -math.pi:
                    series[frame] += 2 * math.pi
            channel = 3 + node_index * 3 + axis
            count, offset = indices[channel * 2:channel * 2 + 2]
            if count != frame_count:
                raise ValueError(f"{record['name']}: {node} channel {axis} count changed")
            for frame, angle in enumerate(series):
                values[offset + frame] = encode_angle(angle)

    max_quantized_error = 0.0
    for frame in range(frame_count):
        new_global = {"Body": IDENTITY}
        for node_index, node in enumerate(nodes):
            if node == "Body":
                continue
            parent = parents[node]
            local_new = read_node_local_quat(values, indices, node_index, frame)
            new_global[node] = qmul(
                qmul(qmul(new_global[parent], new_rest[node]), local_new),
                qinv(new_rest[node]),
            )
            max_quantized_error = max(
                max_quantized_error,
                quat_error(expected_global_per_frame[frame][node], new_global[node]),
            )
    return values, frame_count, max_pre_encode_error, max_quantized_error


def rebase(source: str, mapping_path: Path):
    if "CJ64_NATIVE_MARIO_IDLE_POSE_ANCHOR_APPLIED" in source:
        raise ValueError("input must be raw/unanchored animation tables, not Mario-anchored output")
    mapping, nodes, parents, old_rest, new_rest = parse_map(mapping_path)
    records = parse_lua(source)
    replacements = []
    reports = []
    max_pre_encode_error = 0.0
    max_quantized_error = 0.0
    for record in records:
        values, frames, pre_err, quant_err = rebase_registration(record, nodes, parents, old_rest, new_rest)
        max_pre_encode_error = max(max_pre_encode_error, pre_err)
        max_quantized_error = max(max_quantized_error, quant_err)
        replacements.append((record["values_span"], fmt_values(values)))
        reports.append({
            "name": record["name"],
            "frames": frames,
            "max_pre_encode_global_delta_error_radians": pre_err,
            "max_quantized_global_delta_error_radians": quant_err,
        })
    output = source
    for (start, end), replacement in reversed(replacements):
        output = output[:start] + replacement + output[end:]
    output = (
        "-- CJ64_REBASED_TO_CJ_FBX_SOURCE_REST_V1\n"
        "-- GTA articulation is expressed in CJ/FBX source-rest joint frames.\n"
        "-- No SM64 Mario animation frame is used as a base pose.\n"
        + output
    )
    report = {
        "format": "cj64-source-rest-animation-rebase-v1",
        "source_animation_profile": "native_mario_cs_actor_local_deltas",
        "destination_animation_profile": "cj_fbx_source_rest_actor",
        "source_parent_rest": "native_mario_parent_rest_rotation_wxyz",
        "destination_parent_rest": "target_parent_rest_rotation_wxyz",
        "target_node_count": len(nodes),
        "target_nodes": nodes,
        "clip_count": len(reports),
        "max_pre_encode_global_delta_error_radians": max_pre_encode_error,
        "max_quantized_global_delta_error_radians": max_quantized_error,
        "uses_native_mario_idle_animation_as_pose_anchor": False,
        "root_translation": "zero; SM64CoopDX owns movement and world orientation",
        "clips": reports,
        "status": "REBASED_TO_CJ_SOURCE_REST_STRUCTURAL_ONLY_REQUIRES_IN_GAME_VALIDATION",
    }
    return output, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="raw GTA animation Lua module before Mario idle-pose anchoring")
    parser.add_argument("--map", type=Path, required=True, help="dual-profile retarget map from actual Fast64 rig export")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output, report = rebase(args.source.read_text(encoding="utf-8"), args.map)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    report.update({"output_lua": args.output.name, "output_lua_bytes": args.output.stat().st_size})
    args.output.with_suffix(".rebase-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "destination_animation_profile", "target_node_count", "clip_count",
        "max_pre_encode_global_delta_error_radians", "max_quantized_global_delta_error_radians",
        "uses_native_mario_idle_animation_as_pose_anchor", "status"
    )}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
