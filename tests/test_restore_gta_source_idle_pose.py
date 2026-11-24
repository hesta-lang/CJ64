import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from restore_gta_source_idle_pose import (
    RESTORED_MARKER, encode_angle, q_from_euler_xyz, qmul, restore_pose,
    decode_angle, quat_error, read_node_quaternion, parse_registrations,
)

POSE = ROOT / "tools" / "gta_idle_source_pose.json"


def make_lua():
    data = json.loads(POSE.read_text(encoding="utf-8"))
    bases = [node["base_rotation_xyzw"] for node in data["nodes"]]
    registrations = []
    for name, walk in (("cj64_anim_idle", False), ("cj64_anim_walk", True)):
        channels = [[0], [0], [0]]
        for base in bases:
            q_base = tuple(base)
            for frame in range(2):
                delta = q_from_euler_xyz(
                    math.radians(4 if walk and frame else 0),
                    math.radians(-2 if walk and frame else 0),
                    math.radians(3 if walk and frame else 0),
                )
                absolute = qmul(q_base, delta)
                # Fixture is neutral-relative: q_delta = inverse(base) * q_absolute.
                # With idle, q_delta is identity; walk contains a motion delta.
                if frame == 0:
                    delta = (0.0, 0.0, 0.0, 1.0)
                for axis in range(3):
                    angles = (0.0, 0.0, 0.0)
                    q = delta
                    x, y, z, w = q
                    sin_y = 2 * (w * y - z * x)
                    if sin_y >= 1 - 1e-7:
                        euler = (2 * math.atan2(x, w), math.pi / 2, 0.0)
                    elif sin_y <= -1 + 1e-7:
                        euler = (2 * math.atan2(-z, w), -math.pi / 2, 0.0)
                    else:
                        euler = (
                            math.atan2(2 * (w*x + y*z), 1 - 2 * (x*x + y*y)),
                            math.asin(max(-1.0, min(1.0, sin_y))),
                            math.atan2(2 * (w*z + x*y), 1 - 2 * (y*y + z*z)),
                        )
                    channels.append([encode_angle(euler[axis])])
                # Replace the just-appended one-sample channels with 2-frame tracks.
                # All clip samples share the same reference base.
        # Rebuild table cleanly using two samples per rotation channel.
        channels = [[0], [0], [0]]
        for base in bases:
            for axis in range(3):
                # A zero-relative idle pose, then a small local motion for walk.
                first = 0
                second = encode_angle(math.radians((4, -2, 3)[axis])) if walk else 0
                channels.append([first, second])
        values, indices = [], []
        for channel in channels:
            indices.extend((len(channel), len(values)))
            values.extend(channel)
        def fmt(items):
            return "\n".join(
                "        " + ", ".join(f"0x{v:04X}" for v in items[i:i+12]) + ","
                for i in range(0, len(items), 12)
            )
        registrations.append(
            f'smlua_anim_util_register_animation("{name}", 0, 1, 0, 0, 1,\n'
            "    {\n" + fmt(values) + "\n    },\n"
            "    {\n" + fmt(indices) + "\n    }\n)\n"
        )
    return "\n".join(registrations)


class RestoreGtaSourcePoseTests(unittest.TestCase):
    def test_restores_all_twenty_original_gta_idle_rotations(self):
        source = make_lua()
        output, report = restore_pose(source, POSE)
        self.assertIn(RESTORED_MARKER, output)
        self.assertNotIn("CJ64_NATIVE_MARIO_IDLE_POSE_ANCHOR_APPLIED", output)
        self.assertFalse(report["native_mario_anim_C5_used"])
        self.assertEqual(report["target_animation_nodes"], 20)
        self.assertEqual(report["clip_count"], 2)
        raw = parse_registrations(output)
        restored_idle = next(item for item in raw if item["name"] == "cj64_anim_idle")
        pose = json.loads(POSE.read_text(encoding="utf-8"))
        for node_index, entry in enumerate(pose["nodes"]):
            actual = read_node_quaternion(restored_idle["values"], restored_idle["indices"], node_index, 0)
            expected = tuple(entry["base_rotation_xyzw"])
            self.assertLess(quat_error(actual, expected), math.radians(0.02))
        self.assertLess(report["max_quantized_rotation_error_radians"], math.radians(0.02))

    def test_keeps_root_translation_zero(self):
        output, _ = restore_pose(make_lua(), POSE)
        for item in parse_registrations(output):
            for axis in range(3):
                count, offset = item["indices"][axis*2:axis*2+2]
                self.assertEqual(count, 1)
                self.assertEqual(item["values"][offset], 0)

    def test_refuses_double_restore_or_mario_anchor(self):
        with self.assertRaisesRegex(ValueError, "already restored"):
            restore_pose(RESTORED_MARKER + "\n" + make_lua(), POSE)
        with self.assertRaisesRegex(ValueError, "Mario anim_C5"):
            restore_pose("CJ64_NATIVE_MARIO_IDLE_POSE_ANCHOR_APPLIED\n" + make_lua(), POSE)


if __name__ == "__main__":
    unittest.main()
