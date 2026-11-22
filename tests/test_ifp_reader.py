import sys
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import ifp_reader as module


def fixed(value: str, size: int) -> bytes:
    raw = value.encode('latin-1')[:size - 1]
    return raw + b'\0' * (size - len(raw))


def make_ifp() -> bytes:
    # One clip, two tracks: pelvis with translation (type 4), head rotation (type 3).
    tracks = bytearray()
    pelvis = fixed(' Pelvis', 24) + struct.pack('<III', 4, 2, 1)
    pelvis += struct.pack('<5h3h', 0, 0, 0, 4096, 0, 0, 0, 0)
    pelvis += struct.pack('<5h3h', 0, 0, 0, 4096, 60, 0, 1024, 0)
    head = fixed(' Head', 24) + struct.pack('<III', 3, 1, 5)
    head += struct.pack('<5h', 0, 0, 0, 4096, 30)
    tracks += pelvis + head
    body = fixed('PED', 24) + struct.pack('<I', 1)
    body += fixed('WALK_player', 24) + struct.pack('<III', 2, 2 * 2 * 16 + 10, 1) + tracks
    return b'ANP3' + struct.pack('<I', len(body)) + body


class IFPReaderTests(unittest.TestCase):
    def test_parses_package_animation_and_tracks(self):
        parsed = module.parse_ifp(make_ifp())
        self.assertEqual(parsed.package_name, 'PED')
        walk = parsed.find('walk_PLAYER')
        self.assertIsNotNone(walk)
        self.assertAlmostEqual(walk.duration, 1.0)
        self.assertEqual(len(walk.bones), 2)
        self.assertEqual(walk.bones[0].name, ' Pelvis')  # preserve semantic leading space
        self.assertAlmostEqual(walk.bones[0].frames[1].translation[1], 0.25)
        self.assertAlmostEqual(walk.bones[1].frames[0].time_seconds, 0.5)

    def test_rejects_wrong_magic(self):
        with self.assertRaises(module.IFPError):
            module.parse_ifp(b'NOPE' + bytes(40))

    def test_rejects_truncated_keyframe(self):
        with self.assertRaises(module.IFPError):
            module.parse_ifp(make_ifp()[:-3])

    def test_rejects_unknown_key_type(self):
        raw = bytearray(make_ifp())
        # package/header (36), anim header (36), then bone name (24)
        struct.pack_into('<I', raw, 36 + 36 + 24, 99)
        with self.assertRaises(module.IFPError):
            module.parse_ifp(bytes(raw))

if __name__ == '__main__':
    unittest.main()
