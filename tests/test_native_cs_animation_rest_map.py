import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from generate_cj_sm64_animations import native_target_parent_rest_from_map


class NativeCSAnimationRestMapTests(unittest.TestCase):
    def test_selects_native_mario_parent_frames(self):
        mapping = {
            "animation_target_profile": "native_mario_cs_actor",
            "native_mario_parent_rest_rotation_wxyz": {
                "Body": [1.0, 0.0, 0.0, 0.0],
                "Butt": [0.0, 1.0, 0.0, 0.0],
            },
        }
        result = native_target_parent_rest_from_map(mapping, ["Body", "Butt"])
        self.assertAlmostEqual(result["Body"][3], 1.0)
        self.assertAlmostEqual(result["Butt"][0], 1.0)

    def test_rejects_fbx_transferred_rest_profile(self):
        mapping = {
            "animation_target_profile": "fbx_transferred_rest",
            "native_mario_parent_rest_rotation_wxyz": {
                "Body": [1.0, 0.0, 0.0, 0.0],
            },
        }
        with self.assertRaisesRegex(ValueError, "native Mario/CS actor"):
            native_target_parent_rest_from_map(mapping, ["Body"])

    def test_rejects_incomplete_native_parent_map(self):
        mapping = {
            "animation_target_profile": "native_mario_cs_actor",
            "native_mario_parent_rest_rotation_wxyz": {
                "Body": [1.0, 0.0, 0.0, 0.0],
            },
        }
        with self.assertRaisesRegex(ValueError, "all 20 nodes"):
            native_target_parent_rest_from_map(mapping, ["Body", "Butt"])

    def test_rejects_non_finite_quaternion(self):
        mapping = {
            "animation_target_profile": "native_mario_cs_actor",
            "native_mario_parent_rest_rotation_wxyz": {
                "Body": [1.0, 0.0, 0.0, 0.0],
            },
        }
        mapping["native_mario_parent_rest_rotation_wxyz"]["Body"] = [
            float("nan"), 0.0, 0.0, 0.0
        ]
        with self.assertRaisesRegex(ValueError, "non-finite"):
            native_target_parent_rest_from_map(mapping, ["Body"])


if __name__ == "__main__":
    unittest.main()
