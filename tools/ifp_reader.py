#!/usr/bin/env python3
"""Dependency-free reader for GTA:SA ANP3 IFP animation packages."""
from __future__ import annotations
from dataclasses import dataclass
import math
import struct


class IFPError(ValueError):
    pass


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
        return next((clip for clip in self.animations if clip.name.casefold() == wanted), None)


class _Reader:
    def __init__(self, data: bytes):
        self.data = memoryview(data)
        self.pos = 0

    def read(self, count: int) -> bytes:
        if count < 0 or self.pos + count > len(self.data):
            raise IFPError(f"Unexpected end of IFP at byte {self.pos}; wanted {count} bytes")
        value = self.data[self.pos:self.pos + count].tobytes()
        self.pos += count
        return value

    def u32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def i16(self) -> int:
        return struct.unpack("<h", self.read(2))[0]

    def fixed_string(self, count: int) -> str:
        # Preserve initial spaces: GTA IFP bone names use them in some tracks.
        return self.read(count).split(b"\x00", 1)[0].decode("latin-1").rstrip()


def _normalise(q: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    length = math.sqrt(sum(v * v for v in q))
    if not math.isfinite(length) or length < 1e-8:
        raise IFPError("Invalid zero-length quaternion")
    return tuple(v / length for v in q)


def parse_ifp(data: bytes, max_animations: int = 4096,
              max_bones: int = 256, max_frames: int = 100000) -> IFPFile:
    r = _Reader(data)
    if r.read(4) != b"ANP3":
        raise IFPError("Unsupported IFP header; expected ANP3")
    _declared_size = r.u32()
    package = r.fixed_string(24)
    count = r.u32()
    if count > max_animations:
        raise IFPError(f"Unreasonable animation count: {count}")

    clips = []
    for _ in range(count):
        name = r.fixed_string(24)
        bone_count = r.u32()
        _frame_data_size = r.u32()
        _unknown = r.u32()
        if bone_count > max_bones:
            raise IFPError(f"Unreasonable bone count in {name!r}: {bone_count}")
        tracks = []
        for _ in range(bone_count):
            bone_name = r.fixed_string(24)
            kind, frame_count, bone_id = r.u32(), r.u32(), r.u32()
            if kind not in (3, 4):
                raise IFPError(f"Unsupported keyframe type {kind} in {name!r}/{bone_name!r}")
            if frame_count > max_frames:
                raise IFPError(f"Unreasonable frame count in {name!r}/{bone_name!r}")
            frames = []
            for _ in range(frame_count):
                qx, qy, qz, qw, raw_time = (r.i16() for _ in range(5))
                quaternion = _normalise((qx / 4096.0, qy / 4096.0, qz / 4096.0, qw / 4096.0))
                raw_pos = pos = None
                if kind == 4:
                    raw_pos = (r.i16(), r.i16(), r.i16())
                    pos = tuple(v / 1024.0 for v in raw_pos)
                frames.append(Keyframe(raw_time / 60.0, quaternion, pos, raw_pos))
            tracks.append(BoneTrack(bone_name, bone_id, kind, tuple(frames)))
        clips.append(Animation(name, tuple(tracks)))

    # Archive tools may pad packages with zeroes; reject non-zero trailing data.
    if any(r.data[r.pos:]):
        raise IFPError(f"Unexpected non-padding data at byte {r.pos}")
    return IFPFile(package, tuple(clips))


def load_ifp(path: str) -> IFPFile:
    with open(path, "rb") as handle:
        return parse_ifp(handle.read())
