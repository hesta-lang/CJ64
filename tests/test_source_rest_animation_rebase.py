import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from rebase_gta_animation_rest_pose import encode_angle, parse_lua, q_from_euler_xyz, rebase

NODES = [
    "Body", "Butt", "Torso", "Head", "Left Arm", "Left Arm Color",
    "Left Forearm", "Left Hand", "Right Arm", "Right Arm Color",
    "Right Forearm", "Right Hand", "Left Thigh", "Left Thigh Color",
    "Left Leg", "Left Shoe", "Right Thigh", "Right Thigh Color",
    "Right Leg", "Right Shoe",
]


def make_map(path, include_old_profile=True):
    parents = {"Body": None}
    for i, node in enumerate(NODES[1:], start=1):
        parents[node] = NODES[i - 1]
    old, new = {}, {}
    for i, node in enumerate(NODES):
        a = q_from_euler_xyz(math.radians(i * 2), math.radians(-i), math.radians(i * 0.5))
        b = q_from_euler_xyz(math.radians(-i), math.radians(i * 1.5), math.radians(-i * 2))
        old[node] = [a[3], a[0], a[1], a[2]]
        new[node] = [b[3], b[0], b[1], b[2]]
    data = {
        "generated_from_actual_rig": True,
        "target_animation_node_count": 20,
        "target_node_order": NODES,
        "target_parent_animation_node": parents,
        "target_parent_rest_rotation_wxyz": new,
    }
    if include_old_profile:
        data["native_mario_parent_rest_rotation_wxyz"] = old
    path.write_text(json.dumps(data), encoding="utf-8")


def make_lua(name="cj64_anim_idle"):
    channels = [[0], [0], [0]]
    for node_index in range(20):
        if node_index == 0:
            channels.extend([[0, 0], [0, 0], [0, 0]])
            continue
        angle = math.radians(7 if node_index == 4 else 0)
        channels.extend([
            [encode_angle(angle), encode_angle(-angle)],
            [encode_angle(-angle / 2), encode_angle(angle / 2)],
            [encode_angle(angle / 3), encode_angle(-angle / 3)],
        ])
    values, indices = [], []
    for channel in channels:
        indices.extend((len(channel), len(values)))
        values.extend(channel)

    def fmt(items):
        return "\n".join(
            "        " + ", ".join(f"0x{x:04X}" for x in items[i:i + 12]) + ","
            for i in range(0, len(items), 12)
        )
    return (
        f'smlua_anim_util_register_animation("{name}", 0, 1, 0, 0, 1,\n'
        "    {\n" + fmt(values) + "\n    },\n"
        "    {\n" + fmt(indices) + "\n    }\n)\n"
    )


class SourceRestAnimationRebaseTests(unittest.TestCase):
    def test_rebases_all_nodes_without_mario_idle_pose_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            mapping = Path(tmp) / "map.json"
            make_map(mapping)
            output, report = rebase(make_lua(), mapping)
        self.assertIn("CJ64_REBASED_TO_CJ_FBX_SOURCE_REST_V1", output)
        self.assertNotIn("CJ64_NATIVE_MARIO_IDLE_POSE_ANCHOR_APPLIED", output)
        self.assertEqual(report["target_node_count"], 20)
        self.assertEqual(report["clip_count"], 1)
        self.assertFalse(report["uses_native_mario_idle_animation_as_pose_anchor"])
        self.assertLess(report["max_pre_encode_global_delta_error_radians"], 1e-6)
        self.assertLess(report["max_quantized_global_delta_error_radians"], 0.001)
        self.assertEqual(len(parse_lua(output)[0]["indices"]), 126)

    def test_rejects_map_without_native_cs_parent_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            mapping = Path(tmp) / "map.json"
            make_map(mapping, include_old_profile=False)
            with self.assertRaisesRegex(ValueError, "native CS parent rest"):
                rebase(make_lua(), mapping)

    def test_rejects_mario_anchored_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            mapping = Path(tmp) / "map.json"
            make_map(mapping)
            with self.assertRaisesRegex(ValueError, "raw/unanchored"):
                rebase("-- CJ64_NATIVE_MARIO_IDLE_POSE_ANCHOR_APPLIED\n" + make_lua(), mapping)


if __name__ == "__main__":
    unittest.main()
