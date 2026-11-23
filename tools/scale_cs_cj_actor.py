#!/usr/bin/env python3
"""Set the root GEO_SCALE in the CS CJ DynOS actor binaries.

This changes only the root GeoLayout scale command. It does not rotate the
actor, change its animation hierarchy, or alter MarioState/physics.
"""
from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path

def read_words(raw: bytes, geoname: str):
    marker = geoname.encode("ascii")
    name_offset = raw.find(marker)
    if name_offset < 0:
        raise ValueError(f"GeoLayout {geoname!r} not found")
    pos = name_offset + len(marker)
    word_count = struct.unpack_from("<I", raw, pos)[0]
    pos += 4
    words, offsets = [], []
    for _ in range(word_count):
        offset = pos
        value = struct.unpack_from("<I", raw, pos)[0]
        pos += 4
        offsets.append(offset)
        if value == 0x52544E50:  # PNTR
            length = raw[pos]
            pos += 1
            name = raw[pos:pos + length].decode("latin1")
            pos += length
            pointer = struct.unpack_from("<I", raw, pos)[0]
            pos += 4
            words.append(("PTR", name, pointer))
        elif value == 0x434E5546:  # FUNC
            function = struct.unpack_from("<i", raw, pos)[0]
            pos += 4
            words.append(("FUNC", function))
        elif value == 0x5641554C:  # LUAV
            length = raw[pos]
            pos += 1
            name = raw[pos:pos + length].decode("latin1")
            pos += length
            words.append(("LUA", name))
        else:
            words.append(("WORD", value))
    return words, offsets, word_count

def command_length(op, params):
    if op in (0x00, 0x02): return 2
    if op in (0x01,0x03,0x04,0x05,0x06,0x07,0x09,0x0B,0x0C,0x17,0x1B,0x20): return 1
    if op in (0x08,0x0F,0x21): return {0x08:3,0x0F:5,0x21:3}[op]
    if op == 0x0A: return 3 if params & 1 else 2
    if op in (0x0D,0x0E,0x16,0x18,0x19,0x1A,0x22,0x23): return 2
    if op == 0x10:
        length = {0x00:4,0x10:2,0x20:2,0x30:1}.get(params & 0x70,4)
        return length + (1 if params & 0x80 else 0)
    if op in (0x11,0x12): return 2 + (1 if params & 0x80 else 0)
    if op == 0x13: return 3
    if op == 0x14: return 2 + (1 if params & 0x80 else 0)
    if op == 0x15: return 2
    if op == 0x1C: return 3
    if op == 0x1D:
        length = 4 if params & 0x40 else 2
        return length + (1 if params & 0x80 else 0)
    if op == 0x1F: return 4
    if op == 0x24: return 8 if params & 0x80 else 5
    return 1

def patch_actor(path: Path, geoname: str, scale: float):
    data = path.read_bytes()
    if len(data) < 16 or data[:8] != b"DYNOSBIN":
        raise ValueError(f"{path}: not a DynOS actor binary")
    raw = bytearray(zlib.decompress(data[16:]))
    expected_raw_size = struct.unpack_from("<I", data, 8)[0]
    if len(raw) != expected_raw_size:
        raise ValueError(f"{path}: DynOS raw-size header mismatch")

    words, offsets, word_count = read_words(raw, geoname)
    animated_parts = 0
    root_scale_word = None
    i = 0
    while i < len(words):
        if words[i][0] != "WORD":
            i += 1
            continue
        command = words[i][1]
        op, params = command & 0xFF, (command >> 8) & 0xFF
        length = command_length(op, params)
        if op == 0x13:
            animated_parts += 1
        if op == 0x1D and root_scale_word is None:
            root_scale_word = i + 1
        i += length

    if root_scale_word is None or words[root_scale_word][0] != "WORD":
        raise ValueError(f"{path}: root GEO_SCALE data word not found")
    old_value = words[root_scale_word][1]
    new_value = int(round(scale * 65536.0))
    if not (0 < new_value <= 0x7FFFFFFF):
        raise ValueError("Scale is outside the supported positive 16.16 range")

    struct.pack_into("<I", raw, offsets[root_scale_word], new_value)
    header = bytearray(data[:16])
    struct.pack_into("<I", header, 8, len(raw))
    output = bytes(header) + zlib.compress(raw, 9)

    verify_data = zlib.decompress(output[16:])
    verify_value = struct.unpack_from("<I", verify_data, offsets[root_scale_word])[0]
    if verify_value != new_value:
        raise ValueError(f"{path}: failed to verify patched root scale")
    path.write_bytes(output)

    return {
        "file": str(path),
        "geolayout": geoname,
        "geo_word_count": word_count,
        "animated_part_nodes": animated_parts,
        "old_scale": old_value / 65536.0,
        "new_scale": verify_value / 65536.0,
        "multiplier": verify_value / old_value if old_value else None,
        "bytes": len(output),
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor", type=Path, default=Path("actors/cj/mario_geo.bin"))
    parser.add_argument("--actor-geo", default="cj_geo")
    parser.add_argument("--wingcap", type=Path, default=Path("actors/cj/mario_wingcap_geo.bin"))
    parser.add_argument("--wingcap-geo", default="cj_wingcap_geo")
    parser.add_argument("--scale", type=float, default=0.39)
    parser.add_argument("--report", type=Path, default=Path("build/cs-cj-scale-report.json"))
    args = parser.parse_args()

    report = {
        "format": "cj64-cs-dynos-scale-report-v1",
        "requested_root_scale": args.scale,
        "actors": [
            patch_actor(args.actor, args.actor_geo, args.scale),
            patch_actor(args.wingcap, args.wingcap_geo, args.scale),
        ],
        "visual_size_validation": "NOT_DONE_IN_GAME",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
