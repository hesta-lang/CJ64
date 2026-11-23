#!/usr/bin/env python3
"""Inspect the CS DynOS actor's animated-part traversal order.

This verifies the compiled GeoLayout's 20 GEO_ANIMATED_PART commands and
selected display-list landmarks against the Fast64/Mario target node order.
It does not infer mesh rest rotations or prove animation-axis compatibility.
"""
from __future__ import annotations
import argparse
import json
import struct
import zlib
from pathlib import Path


def read_geo_words(raw: bytes, geo_name: str):
    marker = geo_name.encode("ascii")
    start = raw.find(marker)
    if start < 0:
        raise ValueError(f"GeoLayout {geo_name!r} not found")
    pos = start + len(marker)
    count = struct.unpack_from("<I", raw, pos)[0]
    pos += 4
    words = []
    for _ in range(count):
        value = struct.unpack_from("<I", raw, pos)[0]
        pos += 4
        if value == 0x52544E50:  # PNTR
            size = raw[pos]
            pos += 1
            name = raw[pos:pos + size].decode("latin1")
            pos += size
            pointer = struct.unpack_from("<I", raw, pos)[0]
            pos += 4
            words.append(("PTR", name, pointer))
        elif value == 0x434E5546:  # FUNC
            function = struct.unpack_from("<i", raw, pos)[0]
            pos += 4
            words.append(("FUNC", function))
        elif value == 0x5641554C:  # LUAV
            size = raw[pos]
            pos += 1
            name = raw[pos:pos + size].decode("latin1")
            pos += size
            words.append(("LUA", name))
        else:
            words.append(("WORD", value))
    return words


def command_length(op: int, params: int) -> int:
    if op in (0x00, 0x02): return 2
    if op in (0x01, 0x03, 0x04, 0x05, 0x06, 0x07, 0x09, 0x0B, 0x0C, 0x17, 0x1B, 0x20): return 1
    if op in (0x08, 0x0F, 0x21): return {0x08: 3, 0x0F: 5, 0x21: 3}[op]
    if op == 0x0A: return 3 if params & 1 else 2
    if op in (0x0D, 0x0E, 0x16, 0x18, 0x19, 0x1A, 0x22, 0x23): return 2
    if op == 0x10:
        length = {0x00: 4, 0x10: 2, 0x20: 2, 0x30: 1}.get(params & 0x70, 4)
        return length + (1 if params & 0x80 else 0)
    if op in (0x11, 0x12): return 2 + (1 if params & 0x80 else 0)
    if op == 0x13: return 3
    if op == 0x14: return 2 + (1 if params & 0x80 else 0)
    if op == 0x15: return 2
    if op == 0x1C: return 3
    if op == 0x1D: return (4 if params & 0x40 else 2) + (1 if params & 0x80 else 0)
    if op == 0x1F: return 4
    if op == 0x24: return 8 if params & 0x80 else 5
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--actor", type=Path, default=Path("actors/cj/mario_geo.bin"))
    ap.add_argument("--geo", default="cj_geo")
    ap.add_argument("--reference", type=Path, default=Path("tools/cj_fast64_animation_node_order.json"))
    ap.add_argument("--output", type=Path, default=Path("build/cs-cj-animation-node-report.json"))
    args = ap.parse_args()

    data = args.actor.read_bytes()
    if len(data) < 16 or data[:8] != b"DYNOSBIN":
        raise SystemExit(f"{args.actor}: invalid DynOS binary")
    raw = zlib.decompress(data[16:])
    declared = struct.unpack_from("<I", data, 8)[0]
    if len(raw) != declared:
        raise SystemExit("DynOS uncompressed-size header mismatch")

    ref = json.loads(args.reference.read_text(encoding="utf-8"))
    expected = [x["name"] for x in ref["nodes"]]
    if ref.get("node_count") != len(expected) or len(expected) != 20:
        raise SystemExit("Fast64 reference node list is not the expected 20 nodes")

    words = read_geo_words(raw, args.geo)
    found = []
    i = 0
    while i < len(words):
        word = words[i]
        if word[0] != "WORD":
            i += 1
            continue
        command = word[1]
        op, params = command & 0xFF, (command >> 8) & 0xFF
        length = command_length(op, params)
        if op == 0x13:
            arg = words[i + 1] if i + 1 < len(words) else None
            ptr = words[i + 2] if i + 2 < len(words) else None
            found.append({
                "index": len(found),
                "reference_node": expected[len(found)] if len(found) < len(expected) else None,
                "word_index": i,
                "command": f"0x{command:08X}",
                "packed_position": f"0x{arg[1]:08X}" if arg and arg[0] == "WORD" else None,
                "display_list": ptr[1] if ptr and ptr[0] == "PTR" else None,
            })
        i += length

    if len(found) != len(expected):
        raise SystemExit(f"CS actor has {len(found)} animated-part commands; expected {len(expected)}")

    landmarks = {
        1: "cj_Butt_mesh_layer_1",
        2: "cj_Torso_mesh_layer_1",
        5: "cj_Left_Arm_Color_mesh_layer_1",
        6: "cj_Left_Forearm_mesh_layer_1",
        9: "cj_Right_Arm_Color_mesh_layer_1",
        10: "cj_Right_Forearm_mesh_layer_1",
        13: "cj_Left_Thigh_Color_mesh_layer_1",
        14: "cj_Left_Leg_mesh_layer_1",
        15: "cj_Left_Foot_mesh_layer_1",
        17: "cj_Right_Thigh_Color_mesh_layer_1",
        18: "cj_Right_Leg_mesh_layer_1",
    }
    for index, display_list in landmarks.items():
        actual = found[index]["display_list"]
        if actual != display_list:
            raise SystemExit(
                f"Node {index} ({expected[index]}): expected {display_list}, got {actual}"
            )

    report = {
        "format": "cj64-cs-animation-node-order-report-v1",
        "actor": str(args.actor),
        "internal_geolayout": args.geo,
        "actor_bytes": len(data),
        "uncompressed_bytes": len(raw),
        "animated_part_count": len(found),
        "reference_node_order": expected,
        "nodes": found,
        "landmark_checks": len(landmarks),
        "status": "ORDERED_20_NODE_LAYOUT_MATCHES_FAST64_REFERENCE",
        "rotation_basis_validation": "NOT_VALIDATED",
        "warnings": [
            "This confirms animated-part traversal order and selected part landmarks only.",
            "It does not recover mesh-local rest rotations or prove that FBX/Mario animation axes equal the CS actor's axes.",
            "The Body root's source orientation must be calibrated separately from MarioState's world heading.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
