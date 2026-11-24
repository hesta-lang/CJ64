import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from apply_native_cs_idle_pose import (
    apply_native_pose,
    apply_pose_to_values,
    decode_angle,
    encode_angle,
    euler_sm64_zxy_near,
    load_native_pose,
    q_from_euler_xyz,
    q_from_sm64_zxy,
    q_to_matrix,
    qmul,
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


def quaternion_dot(a, b):
    return abs(sum(x * y for x, y in zip(a, b)))


def sm64_engine_zxy_matrix(rx, ry, rz):
    sx, cx = math.sin(rx), math.cos(rx)
    sy, cy = math.sin(ry), math.cos(ry)
    sz, cz = math.sin(rz), math.cos(rz)
    # Direct transcription of mtxf_rotate_zxy_and_translate in SM64 math_util.c.
    return (
        (cy * cz + sx * sy * sz, -cy * sz + sx * sy * cz, cx * sy),
        (cx * sz, cx * cz, -sx),
        (-sy * cz + sx * cy * sz, sy * sz + cx * cy * 0.0 + sx * cy * cz, cx * cy),
    )


class NativeCSIdlePoseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pose_path = ROOT / "tools/native_mario_idle_pose.json"
        cls.names, cls.rotations, cls.reference_angles = load_native_pose(cls.pose_path)
        cls.pose_data = json.loads(cls.pose_path.read_text(encoding="utf-8"))

    def test_pose_metadata_declares_actual_sm64_engine_order(self):
        self.assertEqual(self.pose_data["format"], "cj64-native-cs-pose-anchor-sm64-zxy-v2")
        self.assertEqual(
            self.pose_data["rotation_order"],
            "SM64_ZXY_APPLIES_Z_THEN_X_THEN_Y",
        )
        self.assertEqual(len(self.names), 20)

    def test_quaternion_matches_sm64_engine_zxy_matrix(self):
        for angles in (
            (0.0, math.pi / 2.0, 0.0),
            (math.pi, math.pi, math.radians(92.026978)),
            (math.radians(35.0), math.radians(-70.0), math.radians(132.0)),
            (math.pi / 2.0, math.radians(42.0), math.radians(-71.0)),
            (-math.pi / 2.0, 1.2, 0.3),
        ):
            actual = q_to_matrix(q_from_sm64_zxy(*angles))
            expected = sm64_engine_zxy_matrix(*angles)
            for row in range(3):
                for column in range(3):
                    self.assertAlmostEqual(
                        actual[row][column], expected[row][column], delta=1e-6
                    )

    def test_all_twenty_native_anim00_channels_round_trip_exactly(self):
        self.assertEqual(len(self.names), 20)
        for item in self.pose_data["nodes"]:
            name = item["node"]
            raw = [int(value, 16) for value in item["first_frame_euler16"]]
            angles = self.reference_angles[name]
            reconstructed = q_from_sm64_zxy(
                *euler_sm64_zxy_near(self.rotations[name], angles)
            )
            self.assertGreater(quaternion_dot(self.rotations[name], reconstructed), 0.999999)
            self.assertEqual([encode_angle(value) for value in angles], raw)

    def test_native_idle_pose_restores_body_orientation(self):
        body = self.rotations["Body"]
        self.assertAlmostEqual(body[1], math.sin(math.pi / 4.0), delta=0.001)
        self.assertAlmostEqual(body[3], math.cos(math.pi / 4.0), delta=0.001)
        self.assertAlmostEqual(
            math.degrees(self.reference_angles["Body"][1]),
            89.994507,
            delta=0.02,
        )

    def test_identity_motion_preserves_every_native_cs_joint_channel(self):
        values, indices = build_identity_channels(20)
        output, first_residual, max_residual = apply_pose_to_values(
            values, indices, self.names, self.rotations, self.reference_angles
        )
        self.assertEqual(output[:3], [0, 0, 0])
        for node_index, node in enumerate(self.pose_data["nodes"]):
            for axis in range(3):
                channel = 3 + node_index * 3 + axis
                count, offset = indices[channel * 2:channel * 2 + 2]
                self.assertEqual(count, 1)
                self.assertEqual(output[offset], int(node["first_frame_euler16"][axis], 16))
        self.assertLess(first_residual, math.radians(0.02))
        self.assertLess(max_residual, math.radians(0.02))

    def test_gta_quaternion_delta_is_emitted_in_sm64_zxy_channels(self):
        name = "Left Arm"
        base = self.rotations[name]
        reference = self.reference_angles[name]
        delta = q_from_euler_xyz(
            math.radians(18.0), math.radians(-11.0), math.radians(27.0)
        )
        values, indices = build_identity_channels(1)
        values[3] = encode_angle(math.radians(18.0))
        values[4] = encode_angle(math.radians(-11.0))
        values[5] = encode_angle(math.radians(27.0))
        output, first_residual, max_residual = apply_pose_to_values(
            values, indices, [name], {name: base}, {name: reference}
        )
        actual_angles = [
            decode_angle(output[3]),
            decode_angle(output[4]),
            decode_angle(output[5]),
        ]
        actual = q_from_sm64_zxy(*actual_angles)
        expected = qmul(base, delta)
        self.assertGreater(quaternion_dot(actual, expected), 0.999999)
        self.assertLess(first_residual, math.radians(0.02))
        self.assertLess(max_residual, math.radians(0.02))

    def test_pose_application_refuses_double_composition(self):
        values, indices = build_identity_channels(20)

        def emit(array):
            return "\n".join(
                "        " + ", ".join(f"0x{x:04X}" for x in array[i:i + 12]) + ","
                for i in range(0, len(array), 12)
            )

        source = (
            'smlua_anim_util_register_animation("cj64_anim_idle", 0, 1, 0, 0, 0,\n'
            '    {\n' + emit(values) + '\n    },\n'
            '    {\n' + emit(indices) + '\n    }\n)\n'
        )
        output, report = apply_native_pose(source, self.pose_path)
        self.assertIn("CJ64_CS_SM64_ZXY_CHANNEL_ORDER_APPLIED", output)
        self.assertIn("CJ64_CS_DEFAULT_IDLE_POSE_ANCHOR_APPLIED", output)
        self.assertEqual(report["clip_count"], 1)
        self.assertEqual(
            report["native_engine_rotation_order"],
            "SM64 ZXY (apply Z then X then Y; matrix Ry * Rx * Rz)",
        )
        self.assertLess(report["neutral_idle_first_frame_residual_radians"], math.radians(0.02))
        with self.assertRaisesRegex(ValueError, "already been applied"):
            apply_native_pose(output, self.pose_path)


if __name__ == "__main__":
    unittest.main()
