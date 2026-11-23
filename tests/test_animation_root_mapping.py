import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from generate_cj_sm64_animations import mapped_mario_node_rotation  # noqa: E402


class MarioRootRetargetTests(unittest.TestCase):
    def test_gta_normal_root_does_not_rotate_mario_body(self):
        # A large GTA Normal/root rotation must never become a world tilt on Mario.
        source = (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5))
        result = mapped_mario_node_rotation(
            "Body", [source], ["root ground"], {("Body", "root ground"): source}
        )
        self.assertEqual(result, (0.0, 0.0, 0.0, 1.0))

    def test_child_parts_still_receive_retargeted_rotations(self):
        source = (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5))
        result = mapped_mario_node_rotation(
            "Butt", [source], ["pelvis"], {("Butt", "pelvis"): (0.0, 0.0, 0.0, 1.0)}
        )
        self.assertAlmostEqual(abs(result[2]), abs(source[2]), places=6)
        self.assertAlmostEqual(abs(result[3]), abs(source[3]), places=6)


if __name__ == "__main__":
    unittest.main()
