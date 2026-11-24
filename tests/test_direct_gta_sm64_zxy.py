import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from convert_direct_gta_to_sm64_zxy import (  # noqa: E402
    APPLIED_MARKER,
    CLIP_NAMES,
    NODE_ORDER,
    convert_direct_table,
    convert_values,
)
from apply_native_cs_idle_pose import (  # noqa: E402
    decode_angle,
    encode_angle,
    q_from_euler_xyz,
    q_from_sm64_zxy,
)


def fixture_angles():
    return [
        (
            math.radians(index * 3 - 22),
            math.radians(55 - index * 2),
            math.radians(index * 5 - 35),
        )
        for index in range(len(NODE_ORDER))
    ]


def fixture_pose(path):
    angles = fixture_angles()
    nodes = []
    for index, (name, euler) in enumerate(zip(NODE_ORDER, angles)):
        nodes.append({
            "node_index": index,
            "node": name,
            "base_rotation_xyzw": list(q_from_euler_xyz(*euler)),
        })
    path.write_text(json.dumps({
        "format": "cj64-gta-idle-source-rest-v1",
        "source": "GTA San Andreas IDLE_stance frame 0",
        "node_count": 20,
        "nodes": nodes,
    }), encoding="utf-8")
    return angles


def emit_animation(name, initial_angles, frames):
    channels = [[0], [0], [0]]
    for base in initial_angles:
        for axis in range(3):
            samples = []
            for frame in range(frames):
                delta = math.radians(frame * (axis + 1) * 0.15)
                samples.append(encode_angle(base[axis] + delta))
            channels.append(samples)
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
        f'smlua_anim_util_register_animation("{name}", 0, 1, 0, 0, {frames - 1},\n'
        "    {\n" + fmt(values) + "\n    },\n"
        "    {\n" + fmt(indices) + "\n    }\n)\n"
    )


def make_lua(initial_angles):
    ordered_names = [
        "cj64_anim_idle", "cj64_anim_walk_start", "cj64_anim_walk", "cj64_anim_run",
        "cj64_anim_sprint_candidate", "cj64_anim_run_stop", "cj64_anim_jump_start",
        "cj64_anim_jump_air", "cj64_anim_jump_land", "cj64_anim_fall", "cj64_anim_fall_air",
        "cj64_anim_fall_land", "cj64_anim_swim_tread",
    ]
    return "\n".join(
        emit_animation(name, initial_angles, 46 if name == "cj64_anim_idle" else 3)
        for name in ordered_names
    )


class DirectGtaSm64ZxyTests(unittest.TestCase):
    def test_preserves_direct_quaternions_when_reencoding(self):
        channels = [[0], [0], [0]]
        original = []
        for node_index in range(len(NODE_ORDER)):
            angles = (
                math.radians(70 + node_index * 0.1),
                math.radians(-45 + node_index * 0.1),
                math.radians(120 - node_index * 0.1),
            )
            original.append(q_from_euler_xyz(*angles))
            for angle in angles:
                channels.append([encode_angle(angle), encode_angle(angle + math.radians(5))])
        values, indices = [], []
        for channel in channels:
            indices.extend((len(channel), len(values)))
            values.extend(channel)
        converted, residual = convert_values(values, indices)
        self.assertLess(residual, math.radians(0.02))
        for index in range(len(NODE_ORDER)):
            angles = [
                decode_angle(converted[indices[(3 + index * 3 + axis) * 2 + 1]])
                for axis in range(3)
            ]
            actual = q_from_sm64_zxy(*angles)
            dot = abs(sum(a * b for a, b in zip(actual, original[index])))
            self.assertGreater(dot, 0.999999)

    def test_build_marks_no_mario_pose_overlay_and_refuses_double_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pose_path = tmp / "pose.json"
            angles = fixture_pose(pose_path)
            source = make_lua(angles)
            output, report = convert_direct_table(source, pose_path)
            self.assertIn(APPLIED_MARKER, output)
            self.assertNotIn("CJ64_NATIVE_MARIO_IDLE_POSE_ANCHOR_APPLIED", output)
            self.assertNotIn("MARIO_ANIM_IDLE_HEAD_CENTER", output)
            self.assertFalse(report["mario_pose_anchor_applied"])
            self.assertEqual(report["clip_count"], 13)
            self.assertLess(report["gta_idle_frame_zero_max_error_radians"], math.radians(0.02))
            self.assertLess(report["max_frame_quantization_error_radians"], math.radians(0.02))
            with self.assertRaisesRegex(ValueError, "already been applied"):
                convert_direct_table(output, pose_path)

    def test_rejects_nonzero_root_translation(self):
        channels = [[0], [0], [0]]
        for _ in NODE_ORDER:
            channels.extend([[0], [0], [0]])
        values, indices = [], []
        for channel in channels:
            indices.extend((len(channel), len(values)))
            values.extend(channel)
        values[indices[1]] = 1
        with self.assertRaisesRegex(ValueError, "Root translation"):
            convert_values(values, indices)

    def test_rejects_declared_frame_count_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pose_path = tmp / "pose.json"
            angles = fixture_pose(pose_path)
            source = make_lua(angles)
            source = source.replace(
                'smlua_anim_util_register_animation("cj64_anim_run", 0, 1, 0, 0, 2,',
                'smlua_anim_util_register_animation("cj64_anim_run", 0, 1, 0, 0, 1,',
                1,
            )
            with self.assertRaisesRegex(ValueError, "declared 2 frames"):
                convert_direct_table(source, pose_path)

    def test_expected_clip_set_is_exact(self):
        self.assertEqual(len(CLIP_NAMES), 13)


if __name__ == "__main__":
    unittest.main()
