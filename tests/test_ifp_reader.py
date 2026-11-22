import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ifp_reader


def fixed(value, size):
    raw = value.encode("latin-1")[:size - 1]
    return raw + b"\x00" * (size - len(raw))


def sample_ifp():
    pelvis = fixed(" Pelvis", 24) + struct.pack("<III", 4, 2, 1)
    pelvis += struct.pack("<5h3h", 0, 0, 0, 4096, 0, 0, 0, 0)
    pelvis += struct.pack("<5h3h", 0, 0, 0, 4096, 60, 0, 1024, 0)
    head = fixed(" Head", 24) + struct.pack("<III", 3, 1, 5)
    head += struct.pack("<5h", 0, 0, 0, 4096, 30)
    tracks = pelvis + head
    body = fixed("PED", 24) + struct.pack("<I", 1)
    body += fixed("WALK_player", 24) + struct.pack("<III", 2, len(tracks), 1) + tracks
    return b"ANP3" + struct.pack("<I", len(body)) + body


class IFPReaderTests(unittest.TestCase):
    def test_valid_clip_and_preserves_gta_bone_name_prefix(self):
        file = ifp_reader.parse_ifp(sample_ifp())
        self.assertEqual(file.package_name, "PED")
        clip = file.find("walk_PLAYER")
        self.assertIsNotNone(clip)
        self.assertEqual(len(clip.bones), 2)
        self.assertEqual(clip.bones[0].name, " Pelvis")
        self.assertAlmostEqual(clip.duration, 1.0)
        self.assertAlmostEqual(clip.bones[0].frames[1].translation[1], 0.25)
        self.assertAlmostEqual(clip.bones[1].frames[0].time_seconds, 0.5)

    def test_bad_magic(self):
        with self.assertRaises(ifp_reader.IFPError):
            ifp_reader.parse_ifp(b"NOPE" + bytes(40))

    def test_truncated_file(self):
        with self.assertRaises(ifp_reader.IFPError):
            ifp_reader.parse_ifp(sample_ifp()[:-3])

    def test_unknown_track_type(self):
        raw = bytearray(sample_ifp())
        struct.pack_into("<I", raw, 36 + 36 + 24, 99)
        with self.assertRaises(ifp_reader.IFPError):
            ifp_reader.parse_ifp(bytes(raw))


if __name__ == "__main__":
    unittest.main()
