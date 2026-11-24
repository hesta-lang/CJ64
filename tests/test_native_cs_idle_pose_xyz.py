import json
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from apply_native_cs_idle_pose_xyz import (
    apply_native_pose,
    decode_angle,
    encode_angle,
    q_from_euler_xyz,
    qmul,
    quaternion_error,
)

NODE_ORDER = [
    "Body", "Butt", "Torso", "Head", "Left Arm", "Left Arm Color",
    "Left Forearm", "Left Hand", "Right Arm", "Right Arm Color",
    "Right Forearm", "Right Hand", "Left Thigh", "Left Thigh Color",
    "Left Leg", "Left Shoe", "Right Thigh", "Right Thigh Color",
    "Right Leg", "Right Shoe",
]
POSE_PATH = ROOT / "tools/native_mario_idle_pose_xyz.json"


def registration(name, frames=3, body_motion=False, limb_motion=False):
    channels = [[0], [0], [0]]
    for node in range(20):
        for axis in range(3):
            samples = []
            for frame in range(frames):
                value = 0
                if node == 0 and body_motion:
                    value = encode_angle(math.radians(30 + frame * 5))
                elif node == 4 and limb_motion:
                    value = encode_angle(math.radians(8 + frame * 2)) if axis == 2 else 0
                samples.append(value)
            channels.append(samples)

    values, indices = [], []
    for channel in channels:
        indices.extend((len(channel), len(values)))
        values.extend(channel)

    def emit(items):
        return "\n".join(
            "        " + ", ".join(f"0x{x:04X}" for x in items[i:i + 12]) + ","
            for i in range(0, len(items), 12)
        )

    return (
        f'smlua_anim_util_register_animation("{name}", 0, 1, 0, 0, {frames - 1},\n'
        "    {\n" + emit(values) + "\n    },\n"
        "    {\n" + emit(indices) + "\n    }\n)\n"
    )


def all_clips():
    names = [
        "cj64_anim_idle", "cj64_anim_walk_start", "cj64_anim_walk",
        "cj64_anim_run", "cj64_anim_sprint_candidate", "cj64_anim_run_stop",
        "cj64_anim_jump_start", "cj64_anim_jump_air", "cj64_anim_jump_land",
        "cj64_anim_fall", "cj64_anim_fall_air", "cj64_anim_fall_land",
        "cj64_anim_swim_tread",
    ]
    return "\n".join(
        registration(
            name,
            frames=46 if name == "cj64_anim_idle" else 3,
            body_motion=True,
            limb_motion=(name != "cj64_anim_idle"),
        )
        for name in names
    )


def extract_values(source, name):
    match = re.search(
        rf'smlua_anim_util_register_animation\(\s*"{re.escape(name)}".*?\{{\s*(.*?)\s*\}},\s*\{{',
        source, re.S
    )
    if match is None:
        raise AssertionError(f"missing animation {name}")
    return [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{1,4})", match.group(1))]


class NativeCSIdlePoseXYZTests(unittest.TestCase):
    def test_identity_motion_reproduces_all_twenty_native_anim00_joints(self):
        source = all_clips()
        with tempfile.TemporaryDirectory() as tmp:
            # The checked-in pose file is used so this test validates the exact package anchor.
            output, report = apply_native_pose(source, POSE_PATH)

        pose = json.loads(POSE_PATH.read_text(encoding="utf-8"))
        out_values = extract_values(output, "cj64_anim_idle")
        out_indices = re.search(
            r'smlua_anim_util_register_animation\(\s*"cj64_anim_idle".*?\},\s*\{(.*?)\}\s*\)',
            output, re.S
        )
        indices = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{1,4})", out_indices.group(1))]
        for node_index, node in enumerate(pose["nodes"]):
            actual = [
                decode_angle(out_values[indices[(3 + node_index * 3 + axis) * 2 + 1]])
                for axis in range(3)
            ]
            expected = [decode_angle(int(value, 16)) for value in node["first_frame_euler16"]]
            self.assertLess(quaternion_error(q_from_euler_xyz(*actual), q_from_euler_xyz(*expected)),
                            math.radians(0.02), node["node"])
        self.assertFalse(report["model_or_skeleton_modified"])
        self.assertLess(report["all_20_idle_first_frame_pose_error_degrees"], 0.02)

    def test_body_root_ignores_gta_normal_rotation(self):
        source = all_clips()
        output, _ = apply_native_pose(source, POSE_PATH)
        pose = json.loads(POSE_PATH.read_text(encoding="utf-8"))
        values = extract_values(output, "cj64_anim_walk")
        indices_match = re.search(
            r'smlua_anim_util_register_animation\(\s*"cj64_anim_walk".*?\},\s*\{(.*?)\}\s*\)',
            output, re.S
        )
        indices = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{1,4})", indices_match.group(1))]
        expected = [decode_angle(int(v, 16)) for v in pose["nodes"][0]["first_frame_euler16"]]
        for frame in range(3):
            actual = [
                decode_angle(values[indices[(3 + axis) * 2 + 1] + frame])
                for axis in range(3)
            ]
            self.assertLess(quaternion_error(q_from_euler_xyz(*actual), q_from_euler_xyz(*expected)),
                            math.radians(0.02))

    def test_articulated_motion_is_composed_over_the_native_pose(self):
        source = all_clips()
        output, _ = apply_native_pose(source, POSE_PATH)
        pose = json.loads(POSE_PATH.read_text(encoding="utf-8"))
        values = extract_values(output, "cj64_anim_walk")
        match = re.search(
            r'smlua_anim_util_register_animation\(\s*"cj64_anim_walk".*?\},\s*\{(.*?)\}\s*\)',
            output, re.S
        )
        indices = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{1,4})", match.group(1))]
        node_index = 4
        expected_base = q_from_euler_xyz(*[
            decode_angle(int(v, 16)) for v in pose["nodes"][node_index]["first_frame_euler16"]
        ])
        delta = q_from_euler_xyz(0.0, 0.0, math.radians(8.0))
        expected = qmul(expected_base, delta)
        actual_angles = [
            decode_angle(values[indices[(3 + node_index * 3 + axis) * 2 + 1]])
            for axis in range(3)
        ]
        actual = q_from_euler_xyz(*actual_angles)
        self.assertLess(quaternion_error(actual, expected), math.radians(0.02))

    def test_rejects_double_application(self):
        output, _ = apply_native_pose(all_clips(), POSE_PATH)
        with self.assertRaisesRegex(ValueError, "already been applied"):
            apply_native_pose(output, POSE_PATH)

    def test_rejects_old_zxy_input(self):
        with self.assertRaisesRegex(ValueError, "Rejected ZXY"):
            apply_native_pose(
                "-- CJ64_CS_SM64_ZXY_CHANNEL_ORDER_APPLIED\n" + all_clips(),
                POSE_PATH,
            )


if __name__ == "__main__":
    unittest.main()
