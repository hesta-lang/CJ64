import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from inspect_cs_actor_transform_hierarchy import analyze_words, resolve_reference_parent_indices


class ActorTransformDiagnosticTests(unittest.TestCase):
    @staticmethod
    def fixture(root_rotation=0):
        words = [
            ("WORD", 0x0000000B), ("WORD", 0x00000004),
            ("WORD", 0x00000016), ("WORD", 0), ("WORD", 0x00000004),
            ("WORD", 0x0000001D), ("WORD", 0x00010000), ("WORD", 0x00000004),
        ]
        if root_rotation:
            words += [("WORD", ((root_rotation & 0xFFFF) << 16) | 0x12),
                      ("WORD", 0), ("WORD", 0x00000004)]
        words += [
            ("WORD", 0x00000113), ("WORD", 0), ("PTR", "body_dl", 0),
            ("WORD", 0x00000004), ("WORD", 0x00460113), ("WORD", 0),
            ("PTR", "butt_dl", 0), ("WORD", 0x00000005),
        ]
        if root_rotation: words.append(("WORD", 0x00000005))
        words += [("WORD", 0x00000005), ("WORD", 0x00000005),
                  ("WORD", 0x00000005), ("WORD", 0x00000001)]
        return words

    def test_recovers_parent_hierarchy_and_root_scale(self):
        report = analyze_words(self.fixture(), ["Body", "Butt"], [None, 0])
        self.assertEqual(report["animated_part_count"], 2)
        self.assertEqual(report["actual_parent_indices"], [None, 0])
        self.assertTrue(report["animated_parent_hierarchy_matches_reference"])
        self.assertEqual(report["body_root_translation"], [0, 0, 0])
        self.assertAlmostEqual(report["root_scale"], 1.0)
        self.assertFalse(report["root_static_rotation_detected"])

    def test_detects_static_rotation_above_body_root(self):
        report = analyze_words(self.fixture(0x4000), ["Body", "Butt"], [None, 0])
        self.assertTrue(report["root_static_rotation_detected"])
        self.assertGreater(report["root_static_rotation_degrees"][0]["rotation_degrees"][0], 89.9)

    def test_resolves_reference_helper_nodes(self):
        pairs = [
            ("Body","Cap State Switch"), ("Butt","Body"), ("Torso","2 Torso Rotation"),
            ("Head","Torso"), ("Left Arm","Torso"), ("Left Arm Color","Left Arm"),
            ("Left Forearm","Left Arm Color"), ("Left Hand","Left Hand Switch"),
            ("Right Arm","Torso"), ("Right Arm Color","Right Arm"),
            ("Right Forearm","Right Arm Color"), ("Right Hand","Right Hand Switch"),
            ("Left Thigh","Butt"), ("Left Thigh Color","Left Thigh"),
            ("Left Leg","Left Thigh Color"), ("Left Shoe","Left Leg"),
            ("Right Thigh","Butt"), ("Right Thigh Color","Right Thigh"),
            ("Right Leg","Right Thigh Color"), ("Right Shoe","Right Leg"),
        ]
        nodes = [{"name": name, "parent": parent} for name, parent in pairs]
        self.assertEqual(resolve_reference_parent_indices(nodes),
            [None,0,1,2,2,4,5,6,2,8,9,10,1,12,13,14,1,16,17,18])

    def test_reports_parent_hierarchy_mismatch(self):
        report = analyze_words(self.fixture(), ["Body", "Butt"], [None, None])
        self.assertFalse(report["animated_parent_hierarchy_matches_reference"])
        self.assertEqual(report["parent_mismatches"][0]["index"], 1)


if __name__ == "__main__":
    unittest.main()
