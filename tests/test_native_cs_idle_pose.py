import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from apply_native_cs_idle_pose import (
    apply_native_pose,
    apply_pose_to_values,
    load_native_pose,
    q_from_euler_xyz,
    decode_angle,
    euler_xyz,
)


def build_identity_channels(node_count):
    channels = [[0], [0], [0]]
    for _ in range(node_count):
        channels.extend([[0], [0], [0]])
    values = []
    indices = []
    for channel in channels:
        indices.extend((len(channel), len(values)))
        values.extend(channel)
    return values, indices


class NativeCSIdlePoseTests(unittest.TestCase):
    def test_real_native_pose_anchor_has_upright_body_root(self):
        names, rotations = load_native_pose(ROOT / "tools/native_mario_idle_pose.json")
        self.assertEqual(len(names), 20)
        self.assertAlmostEqual(rotations["Body"][1], math.sin(math.pi / 4), delta=0.001)
        self.assertAlmostEqual(rotations["Body"][3], math.cos(math.pi / 4), delta=0.001)

    def test_reference_pose_is_default_game_idle_not_head_center_idle(self):
        import json
        data = json.loads((ROOT / "tools/native_mario_idle_pose.json").read_text(encoding="utf-8"))
        self.assertEqual(data["source_animation"], "MARIO_ANIM_IDLE (anim_00)")
        self.assertEqual(data["source_file"], "assets/anims/anim_00.inc.c")
        self.assertEqual(data["nodes"][0]["first_frame_euler16"], ["0000", "3FFF", "0000"])

    def test_identity_motion_restores_native_body_root_rotation(self):
        base = q_from_euler_xyz(0.0, math.radians(89.994507), 0.0)
        values, indices = build_identity_channels(1)
        output, residual = apply_pose_to_values(
            values, indices, ["Body"], {"Body": base}
        )
        self.assertEqual(output[:3], [0, 0, 0])
        decoded = euler_xyz(q_from_euler_xyz(
            decode_angle(output[3]), decode_angle(output[4]), decode_angle(output[5])
        ))
        actual = q_from_euler_xyz(*decoded)
        dot = abs(sum(a * b for a, b in zip(base, actual)))
        self.assertGreater(dot, 0.999999)
        self.assertLess(residual, math.radians(0.02))
        self.assertAlmostEqual(decode_angle(output[4]), math.radians(89.994507), delta=math.radians(0.02))

    def test_gta_motion_is_composed_on_native_idle_pose(self):
        base = q_from_euler_xyz(0.0, math.radians(90.0), 0.0)
        delta = q_from_euler_xyz(math.radians(10.0), 0.0, 0.0)
        values, indices = build_identity_channels(1)
        # X channel for the node is values[3]; remaining node channels stay zero.
        values[3] = int(round(math.radians(10.0) * 65536.0 / (2.0 * math.pi))) & 0xFFFF
        output, _ = apply_pose_to_values(
            values, indices, ["Body"], {"Body": base}
        )
        angles = [decode_angle(output[3]), decode_angle(output[4]), decode_angle(output[5])]
        expected = q_from_euler_xyz(0.0, math.radians(90.0), 0.0)
        # The base pose and the GTA local delta are both retained; compare the
        # encoded output against the exact same Hamilton composition.
        from apply_native_cs_idle_pose import qmul
        expected = qmul(base, delta)
        actual = q_from_euler_xyz(*angles)
        dot = abs(sum(a * b for a, b in zip(expected, actual)))
        self.assertGreater(dot, 0.999999)

    def test_pose_application_refuses_double_composition(self):
        pose_path = ROOT / "tools/native_mario_idle_pose.json"
        names, rotations = load_native_pose(pose_path)
        values, indices = build_identity_channels(20)
        emitted = []
        for start in range(0, len(values), 12):
            emitted.append("        " + ", ".join(f"0x{x:04X}" for x in values[start:start + 12]) + ",")
        idx = []
        for start in range(0, len(indices), 12):
            idx.append("        " + ", ".join(f"0x{x:04X}" for x in indices[start:start + 12]) + ",")
        source = (
            'smlua_anim_util_register_animation("cj64_anim_idle", 0, 1, 0, 0, 0,\n'
            '    {\n' + "\n".join(emitted) + '\n    },\n'
            '    {\n' + "\n".join(idx) + '\n    }\n)\n'
        )
        output, report = apply_native_pose(source, pose_path)
        self.assertIn("CJ64_CS_DEFAULT_IDLE_POSE_ANCHOR_APPLIED", output)
        self.assertEqual(report["clip_count"], 1)
        self.assertLess(report["neutral_idle_first_frame_residual_radians"], math.radians(0.02))
        with self.assertRaisesRegex(ValueError, "already been applied"):
            apply_native_pose(output, pose_path)


if __name__ == "__main__":
    unittest.main()
