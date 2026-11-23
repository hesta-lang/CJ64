import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from cj_skin_weight_map import (  # noqa: E402
    apply_shoulder_weight_retarget,
    required_shoulder_deform_groups,
)


class CJShoulderWeightMappingTests(unittest.TestCase):
    def test_shoulder_and_upper_arm_weights_use_separate_animated_nodes(self):
        mapping = apply_shoulder_weight_retarget({})
        self.assertEqual(mapping["arm left shoulder 1"], "Left Arm")
        self.assertEqual(mapping["arm left shoulder 2"], "Left Arm Color")
        self.assertEqual(mapping["arm right shoulder 1"], "Right Arm")
        self.assertEqual(mapping["arm right shoulder 2"], "Right Arm Color")
        self.assertEqual(
            len({mapping["arm left shoulder 1"], mapping["arm left shoulder 2"],
                 mapping["arm right shoulder 1"], mapping["arm right shoulder 2"]}),
            4,
            "four separate source joints must not collapse into two child groups",
        )

    def test_both_shoulder_pivots_must_be_deformable(self):
        self.assertEqual(
            set(required_shoulder_deform_groups()),
            {"Left Arm", "Left Arm Color", "Right Arm", "Right Arm Color"},
        )


if __name__ == "__main__":
    unittest.main()
