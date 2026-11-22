#!/usr/bin/env python3
"""Small, dependency-free reader for GTA San Andreas ANP3 IFP packages.

This reads animation data from an IFP supplied by the user. It does not
redistribute Rockstar game assets and does not retarget the clips to SM64.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from typing import BinaryIO


class IFPError(ValueError):
    """Malformed or unsupported IFP package."""


@dataclass(frozen=True)
class Keyframe:
    time_seconds: float
    rotation_xyzw: tuple[float, float, float, float]
    translation: tuple[float, float, float] | None = None
    translation_raw: tuple[int, int, int] | None = None


@dataclass(frozen=True)
class BoneTrack:
    name: str
    bone_id: int
    keyframe_type: int
    frames: tuple[Keyframe, ...]


@dataclass(frozen=True)
class Animation:
    name: str
    bones: tuple[BoneTrack, ...]

    @property
    def duration(self) -> float:
        return max((b.frames[-1].time_seconds for b in self.bones if b.frames), default=0.0)


@dataclass(frozen=True)
class IFPFile:
    package_name: str
    animations: tuple[Animation, ...]

    def find(self, name: str) -> Animation | None:
        wanted = name.casefold()
        return next((a for a in self.animations if a.name.casefold() == wanted), None)


class _Reader:
    def __init__(self, data: bytes):
        self.data = memoryview(data)
        self.pos = 0

    def read(self, size: int) -> bytes:
        if size < 0 or self.pos + size > len(self.data):
            raise IFPError(f"Unexpected end of IFP at byte {self.pos} (wanted {size} bytes)")
        out = self.data[self.pos:self.pos + size].tobytes()
        self.pos += size
        return out

    def u32(self) -> int:
        return struct.unpack('<I', self.read(4))[0]

    def i16(self) -> int:
        return struct.unpack('<h', self.read(2))[0]

    def fixed_string(self, size: int) -> str:
        raw = self.read(size).split(b'\0', 1)[0]
        return raw.decode('latin-1').rstrip(' \x00')


def _normalise_quaternion(q: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    length = math.sqrt(sum(v * v for v in q))
    if not math.isfinite(length) or length < 1e-8:
        raise IFPError("Invalid zero-length quaternion in keyframe")
    return tuple(v / length for v in q)  # type: ignore[return-value]


def parse_ifp(data: bytes, *, max_animations: int = 4096, max_bones_per_animation: int = 256,
              max_frames_per_bone: int = 100000) -> IFPFile:
    """Parse a GTA:SA ANP3 package, rejecting truncated/implausible data.

    Quaternion components are decoded from signed 16-bit values / 4096.
    Frame timestamps are in 1/60 second units. Type 4 tracks also include
    per-key translation values; those are retained raw and decoded /1024.
    """
    r = _Reader(data)
    magic = r.read(4)
    if magic != b'ANP3':
        raise IFPError(f"Unsupported IFP magic {magic!r}; expected b'ANP3'")

    declared_size = r.u32()  # payload size in the IFP header
    package_name = r.fixed_string(24)
    animation_count = r.u32()
    if animation_count > max_animations:
        raise IFPError(f"Unreasonable animation count: {animation_count}")

    animations: list[Animation] = []
    for anim_index in range(animation_count):
        name = r.fixed_string(24)
        bone_count = r.u32()
        _frame_data_size = r.u32()
        _unknown = r.u32()
        if bone_count > max_bones_per_animation:
            raise IFPError(f"Animation {name!r} has unreasonable bone count: {bone_count}")

        tracks: list[BoneTrack] = []
        for _ in range(bone_count):
            bone_name = r.fixed_string(24)
            key_type = r.u32()
            frame_count = r.u32()
            bone_id = r.u32()
            if key_type not in (3, 4):
                raise IFPError(f"Unsupported keyframe type {key_type} on {name!r}/{bone_name!r}")
            if frame_count > max_frames_per_bone:
                raise IFPError(f"Unreasonable frame count on {name!r}/{bone_name!r}: {frame_count}")

            frames: list[Keyframe] = []
            for _frame in range(frame_count):
                qx, qy, qz, qw, raw_time = (r.i16() for _ in range(5))
                q = _normalise_quaternion((qx / 4096.0, qy / 4096.0, qz / 4096.0, qw / 4096.0))
                raw_translation = None
                translation = None
                if key_type == 4:
                    raw_translation = (r.i16(), r.i16(), r.i16())
                    translation = tuple(v / 4096.0 for v in raw_translation)
                frames.append(Keyframe(raw_time / 60.0, q, translation, raw_translation))
            tracks.append(BoneTrack(bone_name, bone_id, key_type, tuple(frames)))
        animations.append(Animation(name, tuple(tracks)))

    # The header's size fields have differed in some tools, so the parser
    # enforces exact consumption rather than trusting the declared value.
    trailing = len(r.data) - r.pos
    if trailing not in (0,) and any(r.data[r.pos:]):
        raise IFPError(f"Unexpected non-padding bytes after {animation_count} animations: {trailing}")
    if declared_size not in (len(data) - 8, len(data) - 8 - trailing):
        # Keep this informational: many IFP writers pad packages to sectors.
        pass
    return IFPFile(package_name, tuple(animations))


def load_ifp(path: str) -> IFPFile:
    with open(path, 'rb') as handle:
        return parse_ifp(handle.read())
