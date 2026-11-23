import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from cj_ifp_skeleton_map import build_ifp_parent_map  # noqa: E402


class CanonicalIFPHierarchyTests(unittest.TestCase):
    def test_clavicles_are_children_of_gta_neck_not_fbx_spine_helper(self):
        names = {
            "root ground", "pelvis", "spine lower", "spine middle", "spine upper",
            "head neck lower", "head neck upper",
            "arm left shoulder 1", "arm left shoulder 2", "arm left elbow", "arm left wrist",
            "arm right shoulder 1", "arm right shoulder 2", "arm right elbow", "arm right wrist",
            "leg left thigh", "leg left knee", "leg left ankle",
            "leg right thigh", "leg right knee", "leg right ankle",
        }
        parents = build_ifp_parent_map(names)
        self.assertIsNone(parents["root ground"])
        self.assertEqual(parents["pelvis"], "root ground")
        self.assertEqual(parents["spine lower"], "pelvis")
        self.assertEqual(parents["spine middle"], "spine lower")
        self.assertEqual(parents["head neck lower"], "spine upper")
        self.assertEqual(parents["arm left shoulder 1"], "head neck lower")
        self.assertEqual(parents["arm right shoulder 1"], "head neck lower")
        self.assertEqual(parents["arm left shoulder 2"], "arm left shoulder 1")
        self.assertEqual(parents["arm right shoulder 2"], "arm right shoulder 1")

    def test_rejects_missing_required_ifp_bones(self):
        with self.assertRaisesRegex(ValueError, "missing required GTA IFP bones"):
            build_ifp_parent_map({"root ground", "pelvis"})


if __name__ == "__main__":
    unittest.main()
