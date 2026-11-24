#!/usr/bin/env python3
"""Apply only the CS actor's fixed Body-root orientation to neutral GTA clips.

The working Character Select CJ binary renders upright with its Body root
rotated about +90 degrees around local Y. Its other 19 animated-part nodes
must NOT inherit Mario's idle pose. This postprocessor applies that single
static root orientation to all frames of all GTA clips, leaving limb channels
and their GTA motion deltas unchanged.
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


def apply_body_root_orientation(source: str, *, expected_clips: int = 13, node_count: int = 20):
    if MARKER in source:
        raise ValueError("Body root orientation has already been applied")
    if "CJ64_NATIVE_MARIO_IDLE_POSE_ANCHOR_APPLIED" in source:
        raise ValueError("Refusing input with full Mario idle pose; use neutral-relative source tables")

    records = parse_registrations(source)
    if len(records) != expected_clips:
        raise ValueError(f"Expected {expected_clips} clips, found {len(records)}")

    expected_index_entries = (3 + node_count * 3) * 2
    replacements = []
    reports = []
    root_angle = 0x3FFF
    expected_degrees = signed_degrees(root_angle)

    for record in records:
        name = record["name"]
        values = list(record["values"])
        indices = record["indices"]
        if len(indices) != expected_index_entries:
            raise ValueError(f"{name}: expected {expected_index_entries} index entries, got {len(indices)}")
        declared_frames = int(record["header"].split(",")[-1].strip(), 0) + 1

        # Root translations are game-owned and must remain fixed at zero.
        for axis in range(3):
            count, offset = indices[axis * 2:axis * 2 + 2]
            if count != 1 or offset >= len(values) or values[offset] != 0:
                raise ValueError(f"{name}: root translation channel {axis} must be one zero sample")

        body_channels = []
        for axis in range(3):
            channel_index = 3 + axis
            count, offset = indices[channel_index * 2:channel_index * 2 + 2]
            if count != declared_frames or offset + count > len(values):
                raise ValueError(f"{name}: Body axis {axis} sample count/bounds mismatch")
            body_channels.append((count, offset))

        # The GTA Normal/root track is deliberately excluded. The only Body
        # operation is the static +89.9945 degree CS actor orientation.
        # Reject non-identity Body input rather than silently double-rotating it.
        for axis, (count, offset) in enumerate(body_channels):
            if any(values[offset + frame] != 0 for frame in range(count)):
                raise ValueError(f"{name}: Body axis {axis} already contains motion; refusing unsafe composition")

        body_y_count, body_y_offset = body_channels[1]
        for frame in range(body_y_count):
            values[body_y_offset + frame] = root_angle

        # Confirm every other animated node is byte-for-byte preserved.
        for node in range(1, node_count):
            for axis in range(3):
                channel_index = 3 + node * 3 + axis
                count, offset = indices[channel_index * 2:channel_index * 2 + 2]
                if count != declared_frames or offset + count > len(values):
                    raise ValueError(f"{name}: node {node} axis {axis} sample count/bounds mismatch")

        replacements.append((record["span"], format_values(values)))
        reports.append({
            "name": name,
            "frames": declared_frames,
            "body_root_y_degrees": expected_degrees,
            "body_root_x_degrees": 0.0,
            "body_root_z_degrees": 0.0,
            "limb_nodes_modified": 0,
            "root_translation": "unchanged zero",
        })

    output = source
    for (start, end), replacement in reversed(replacements):
        output = output[:start] + replacement + output[end:]
    output = (
        "-- " + MARKER + "\n"
        "-- Only the fixed CS actor Body-root Y orientation is applied (+89.9945 degrees).\n"
        "-- No Mario idle animation pose is copied to the 19 articulated limb nodes.\n"
        + output
    )
    report = {
        "format": "cj64-body-root-orientation-only-v1",
        "clip_count": len(reports),
        "node_count": node_count,
        "body_root_y_degrees": expected_degrees,
        "body_root_orientation_source": "validated CS actor upright orientation observed with prior C5 test; Body node only",
        "native_mario_pose_applied_to_limbs": False,
        "limb_nodes_modified": 0,
        "root_translation": "fixed zero",
        "clips": reports,
        "status": "STRUCTURAL_CHECKS_PASSED_REQUIRES_ANDROID_VISUAL_VALIDATION",
    }
    return output, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="neutral-relative GTA Lua module")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-clips", type=int, default=13)
    args = parser.parse_args()
    try:
        output, report = apply_body_root_orientation(
            args.source.read_text(encoding="utf-8"),
            expected_clips=args.expected_clips,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    report.update({"source_module": args.source.name, "output_module": args.output.name})
    args.output.with_suffix(".body-root-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "output": str(args.output),
        "clips": report["clip_count"],
        "body_root_y_degrees": report["body_root_y_degrees"],
        "limb_nodes_modified": report["limb_nodes_modified"],
        "status": report["status"],
    }, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
