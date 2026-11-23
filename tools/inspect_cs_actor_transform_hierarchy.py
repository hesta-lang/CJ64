#!/usr/bin/env python3
"""Inspect a DynOS actor's root transforms and animated-part parent hierarchy.

The report separates checks provable from the binary (GeoLayout commands,
parentage, static transforms and scale) from local mesh-axis/rest-basis facts
that require Blender mesh data or runtime rendering.
"""
from __future__ import annotations
import argparse
import json
import struct
import zlib
from pathlib import Path

NODE_OPS = {
    0x08, 0x09, 0x0A, 0x0B, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12,
    0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1B, 0x1C, 0x1D,
    0x20, 0x21, 0x22, 0x23, 0x24,
}
OP_NAMES = {
    0x08: "SCREEN_AREA", 0x09: "ORTHO", 0x0A: "FRUSTUM",
    0x0B: "NODE_START", 0x0D: "RENDER_RANGE", 0x0E: "SWITCH_CASE",
    0x0F: "CAMERA", 0x10: "TRANSLATE_ROTATE", 0x11: "TRANSLATE_NODE",
    0x12: "ROTATION_NODE", 0x13: "ANIMATED_PART", 0x14: "BILLBOARD",
    0x15: "DISPLAY_LIST", 0x16: "SHADOW", 0x17: "RENDER_OBJ",
    0x18: "ASM", 0x19: "BACKGROUND", 0x1B: "COPY_VIEW",
    0x1C: "HELD_OBJECT", 0x1D: "SCALE", 0x20: "CULLING_RADIUS",
    0x21: "BACKGROUND_EXT", 0x22: "SWITCH_CASE_EXT",
    0x23: "ASM_EXT", 0x24: "BONE",
}
REFERENCE_PARENT_ALIASES = {
    "Cap State Switch": None,
    "2 Torso Rotation": "Butt",
    "Left Hand Switch": "Left Forearm",
    "Right Hand Switch": "Right Forearm",
}

def command_length(op: int, params: int) -> int:
    if op in (0x00, 0x02): return 2
    if op in (0x01, 0x03, 0x04, 0x05, 0x06, 0x07, 0x09, 0x0B, 0x0C, 0x17, 0x1B, 0x20): return 1
    if op in (0x08, 0x0F, 0x21): return {0x08: 3, 0x0F: 5, 0x21: 3}[op]
    if op == 0x0A: return 3 if params & 1 else 2
    if op in (0x0D, 0x0E, 0x16, 0x18, 0x19, 0x1A, 0x22, 0x23): return 2
    if op == 0x10:
        return {0x00: 4, 0x10: 2, 0x20: 2, 0x30: 1}.get(params & 0x70, 4) + (1 if params & 0x80 else 0)
    if op in (0x11, 0x12): return 2 + (1 if params & 0x80 else 0)
    if op == 0x13: return 3
    if op == 0x14: return 2 + (1 if params & 0x80 else 0)
    if op == 0x15: return 2
    if op == 0x1C: return 3
    if op == 0x1D: return (4 if params & 0x40 else 2) + (1 if params & 0x80 else 0)
    if op == 0x1F: return 4
    if op == 0x24: return 8 if params & 0x80 else 5
    return 1

def signed16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value

def read_geo_words(raw: bytes, geo_name: str):
    marker = geo_name.encode("ascii")
    start = raw.find(marker)
    if start < 0:
        raise ValueError(f"GeoLayout {geo_name!r} not found in DynOS data")
    pos = start + len(marker)
    if pos + 4 > len(raw):
        raise ValueError("Truncated GeoLayout header")
    count = struct.unpack_from("<I", raw, pos)[0]
    pos += 4
    words = []
    for _ in range(count):
        if pos + 4 > len(raw):
            raise ValueError("Truncated GeoLayout command stream")
        value = struct.unpack_from("<I", raw, pos)[0]
        pos += 4
        if value == 0x52544E50:  # PNTR
            if pos >= len(raw): raise ValueError("Truncated DynOS pointer name")
            size = raw[pos]; pos += 1
            name = raw[pos:pos + size].decode("latin1"); pos += size
            if pos + 4 > len(raw): raise ValueError("Truncated DynOS pointer value")
            pointer = struct.unpack_from("<I", raw, pos)[0]; pos += 4
            words.append(("PTR", name, pointer))
        elif value == 0x434E5546:  # FUNC
            if pos + 4 > len(raw): raise ValueError("Truncated DynOS function pointer")
            function = struct.unpack_from("<i", raw, pos)[0]; pos += 4
            words.append(("FUNC", function))
        elif value == 0x5641554C:  # LUAV
            if pos >= len(raw): raise ValueError("Truncated DynOS Lua name")
            size = raw[pos]; pos += 1
            name = raw[pos:pos + size].decode("latin1"); pos += size
            words.append(("LUA", name))
        else:
            words.append(("WORD", value))
    return words

def command_values(words, index: int, length: int):
    return [item[1] if item[0] == "WORD" else item[1:] for item in words[index + 1:index + length]]

def decode_node(op: int, command: int, params: int, values: list):
    data = {"translation": None, "rotation_raw": None, "scale": None, "display_list": None}
    if op == 0x13:  # GEO_ANIMATED_PART
        yz = int(values[0]) if values and isinstance(values[0], int) else 0
        data["translation"] = [signed16(command >> 16), signed16(yz), signed16(yz >> 16)]
        if len(values) > 1 and isinstance(values[1], tuple) and values[1][0] == "PTR":
            data["display_list"] = values[1][1]
    elif op == 0x12:  # GEO_ROTATION_NODE
        yz = int(values[0]) if values and isinstance(values[0], int) else 0
        data["rotation_raw"] = [signed16(command >> 16), signed16(yz), signed16(yz >> 16)]
    elif op == 0x11:  # GEO_TRANSLATE_NODE
        yz = int(values[0]) if values and isinstance(values[0], int) else 0
        data["translation"] = [signed16(command >> 16), signed16(yz), signed16(yz >> 16)]
    elif op == 0x10:  # GEO_TRANSLATE_ROTATE and variants
        mode = params & 0x70
        payload = [int(v) for v in values if isinstance(v, int)]
        if mode == 0x00 and len(payload) >= 3:
            data["translation"] = [signed16(payload[0]), signed16(payload[0] >> 16), signed16(payload[1])]
            data["rotation_raw"] = [signed16(payload[1] >> 16), signed16(payload[2]), signed16(payload[2] >> 16)]
        elif mode == 0x10 and payload:
            data["translation"] = [signed16(command >> 16), signed16(payload[0]), signed16(payload[0] >> 16)]
        elif mode == 0x20 and payload:
            data["rotation_raw"] = [signed16(command >> 16), signed16(payload[0]), signed16(payload[0] >> 16)]
        elif mode == 0x30:
            data["rotation_raw"] = [0, signed16(command >> 16), 0]
        if params & 0x80 and values and isinstance(values[-1], tuple) and values[-1][0] == "PTR":
            data["display_list"] = values[-1][1]
    elif op == 0x1D:  # GEO_SCALE
        ints = [int(v) for v in values if isinstance(v, int)]
        if params & 0x40 and len(ints) >= 3:
            data["scale"] = [v / 65536.0 for v in ints[:3]]
        elif ints:
            data["scale"] = ints[0] / 65536.0
    if data["rotation_raw"] is not None:
        data["rotation_degrees"] = [v * 360.0 / 65536.0 for v in data["rotation_raw"]]
    return data

def parse_tree(words):
    root = {"id": -1, "op": "ROOT", "children": [], "parent": None, "data": {}}
    stack = [root]; last_node = None; nodes = []; i = 0
    while i < len(words):
        item = words[i]
        if item[0] != "WORD":
            last_node = None; i += 1; continue
        command = item[1]; op = command & 0xFF; params = (command >> 8) & 0xFF
        if op == 0x04:
            if last_node is None: raise ValueError(f"GEO_OPEN_NODE without preceding node at word {i}")
            stack.append(last_node); last_node = None; i += 1; continue
        if op == 0x05:
            if len(stack) <= 1: raise ValueError(f"Unbalanced GEO_CLOSE_NODE at word {i}")
            stack.pop(); last_node = None; i += 1; continue
        length = command_length(op, params)
        if length < 1 or i + length > len(words):
            raise ValueError(f"Invalid command length for op 0x{op:02X} at word {i}")
        if op in NODE_OPS:
            node = {"id": len(nodes), "op": OP_NAMES.get(op, f"UNKNOWN_{op:02X}"),
                    "word_index": i, "parent": stack[-1], "children": [],
                    "data": decode_node(op, command, params, command_values(words, i, length))}
            stack[-1]["children"].append(node); nodes.append(node); last_node = node
        else:
            last_node = None
        i += length
    if len(stack) != 1: raise ValueError(f"GeoLayout finished with {len(stack) - 1} unclosed nodes")
    return root, nodes

def resolve_reference_parent_indices(reference_nodes):
    names = [node["name"] for node in reference_nodes]
    index_by_name = {name: index for index, name in enumerate(names)}
    result = []
    for node in reference_nodes:
        parent = node.get("parent")
        if parent in index_by_name:
            result.append(index_by_name[parent])
        elif parent in REFERENCE_PARENT_ALIASES:
            alias = REFERENCE_PARENT_ALIASES[parent]
            result.append(index_by_name[alias] if alias is not None else None)
        else:
            raise ValueError(f"Unknown helper parent {parent!r} for {node['name']!r}")
    return result

def analyze_words(words, expected_names, expected_parent_indices):
    if len(expected_names) != len(expected_parent_indices):
        raise ValueError("Expected names and parent indices differ in length")
    root, nodes = parse_tree(words)
    animated = [n for n in nodes if n["op"] == "ANIMATED_PART"]
    actual = []; mismatches = []
    for index, node in enumerate(animated):
        ancestor = node["parent"]
        while ancestor is not None and ancestor["op"] != "ANIMATED_PART":
            ancestor = ancestor["parent"]
        parent_index = animated.index(ancestor) if ancestor is not None else None
        actual.append(parent_index)
        expected = expected_parent_indices[index] if index < len(expected_parent_indices) else None
        if parent_index != expected:
            mismatches.append({"index": index, "node": expected_names[index] if index < len(expected_names) else None,
                               "expected_parent_index": expected, "actual_parent_index": parent_index})
    hierarchy_ok = len(animated) == len(expected_names) and not mismatches
    body = animated[0] if animated else None
    root_path = []; cursor = body["parent"] if body else None
    while cursor is not None and cursor is not root:
        root_path.append(cursor); cursor = cursor["parent"]
    root_path.reverse()
    root_rotations = []; root_scale = None
    for node in root_path:
        if node["op"] in ("ROTATION_NODE", "TRANSLATE_ROTATE", "BONE"):
            deg = node["data"].get("rotation_degrees")
            if deg and any(abs(v) > 1e-5 for v in deg):
                root_rotations.append({"node_id": node["id"], "op": node["op"],
                    "word_index": node["word_index"], "rotation_degrees": deg})
        if node["op"] == "SCALE" and node["data"].get("scale") is not None:
            root_scale = node["data"]["scale"]
    static_rotations = []
    for node in nodes:
        deg = node["data"].get("rotation_degrees")
        if deg and any(abs(v) > 1e-5 for v in deg):
            static_rotations.append({"node_id": node["id"], "op": node["op"],
                "word_index": node["word_index"], "rotation_degrees": deg})
    animated_nodes = [{
        "index": i, "reference_name": expected_names[i] if i < len(expected_names) else None,
        "nearest_animated_parent_index": actual[i], "translation": n["data"].get("translation"),
        "display_list": n["data"].get("display_list"), "word_index": n["word_index"]
    } for i, n in enumerate(animated)]
    return {
        "animated_part_count": len(animated), "actual_parent_indices": actual,
        "expected_parent_indices": expected_parent_indices,
        "animated_parent_hierarchy_matches_reference": hierarchy_ok,
        "parent_mismatches": mismatches, "root_static_rotation_detected": bool(root_rotations),
        "root_static_rotation_degrees": root_rotations, "root_scale": root_scale,
        "body_root_translation": body["data"].get("translation") if body else None,
        "body_root_path": [{"id": n["id"], "op": n["op"], "data": n["data"]} for n in root_path],
        "animated_nodes": animated_nodes, "nonzero_static_rotations": static_rotations,
        "local_mesh_axis_basis_validation": "NOT_VALIDATED_BY_DYNOS_BIN_ONLY",
        "vertex_orientation_validation": "NOT_VALIDATED",
    }

def load_actor(path, geo_name):
    data = path.read_bytes()
    if len(data) < 16 or data[:8] != b"DYNOSBIN": raise ValueError(f"{path}: invalid DynOS binary header")
    declared = struct.unpack_from("<I", data, 8)[0]; raw = zlib.decompress(data[16:])
    if len(raw) != declared: raise ValueError(f"{path}: uncompressed size mismatch")
    return data, raw, read_geo_words(raw, geo_name)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor", type=Path, default=Path("actors/cj/mario_geo.bin"))
    parser.add_argument("--geo", default="cj_geo")
    parser.add_argument("--reference", type=Path, default=Path("tools/cj_fast64_animation_node_order.json"))
    parser.add_argument("--output", type=Path, default=Path("build/cj64-transform-diagnostic.json"))
    args = parser.parse_args()
    data, raw, words = load_actor(args.actor, args.geo)
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    ref_nodes = reference.get("nodes", []); names = [x["name"] for x in ref_nodes]
    expected = resolve_reference_parent_indices(ref_nodes)
    report = analyze_words(words, names, expected)
    report.update({
        "reference_parent_aliases": REFERENCE_PARENT_ALIASES,
        "format": "cj64-dynos-root-and-animated-hierarchy-report-v1",
        "actor": str(args.actor), "actor_bytes": len(data), "uncompressed_bytes": len(raw),
        "internal_geolayout": args.geo, "registered_actor_filename": args.actor.name,
        "root_orientation_status": "NO_STATIC_ROOT_ROTATION_FOUND" if not report["root_static_rotation_detected"] else "STATIC_ROOT_ROTATION_PRESENT",
        "status": "ROOT_AND_ANIMATED_PARENT_HIERARCHY_INSPECTED_LOCAL_MESH_AXES_STILL_UNVERIFIED",
        "conclusion_limits": [
            "This inspects DynOS GeoLayout transforms, not vertex-space orientation inside display lists.",
            "Matching nearest animated-parent hierarchy does not prove matching local rotation axes/rest bases.",
            "A Blender reconstruction/render or an in-game neutral-pose test is still needed to prove mesh orientation."
        ]
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
