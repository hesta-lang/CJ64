import json
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from convert_direct_gta_to_sm64_xyz import (  # noqa: E402
    APPLIED_MARKER,
    CLIP_NAMES,
    NODE_ORDER,
    convert_direct_table,
    decode_angle,
    encode_angle,
    parse_tables,
    q_from_euler_xyz,
    q_to_matrix,
    quaternion_error,
    sm64_mtxf_rotate_xyz,
    validate_engine_xyz_convention,
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
    nodes = []
    for index, (name, angles) in enumerate(zip(NODE_ORDER, fixture_angles())):
        nodes.append({
            "node_index": index,
            "node": name,
            "base_rotation_xyzw": list(q_from_euler_xyz(*angles)),
        })
    path.write_text(json.dumps({
        "format": "cj64-gta-idle-source-rest-v1",
        "source": "GTA San Andreas IDLE_stance frame 0",
        "node_count": 20,
        "nodes": nodes,
    }), encoding="utf-8")


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


def make_lua():
    ordered_names = [
        "cj64_anim_idle", "cj64_anim_walk_start", "cj64_anim_walk", "cj64_anim_run",
        "cj64_anim_sprint_candidate", "cj64_anim_run_stop", "cj64_anim_jump_start",
        "cj64_anim_jump_air", "cj64_anim_jump_land", "cj64_anim_fall", "cj64_anim_fall_air",
        "cj64_anim_fall_land", "cj64_anim_swim_tread",
    ]
    return "\n".join(
        emit_animation(name, fixture_angles(), 46 if name == "cj64_anim_idle" else 3)
        for name in ordered_names
    )


class DirectGtaSm64XyzTests(unittest.TestCase):
    def test_engine_xyz_matrix_matches_quaternion_xyz(self):
        samples = (
            (0.0, 0.0, 0.0),
            (math.pi / 2.0, 0.0, 0.0),
            (0.0, -math.pi / 2.0, 0.0),
            (0.0, 0.0, math.pi / 2.0),
            (0.43, -0.71, 1.12),
            (-1.03, 0.62, -0.87),
        )
        for angles in samples:
            q_matrix = q_to_matrix(q_from_euler_xyz(*angles))
            expected = tuple(
                tuple(q_matrix[col][row] for col in range(3))
                for row in range(3)
            )
            actual = sm64_mtxf_rotate_xyz(*angles)
            error = max(
                abs(actual[row][col] - expected[row][col])
                for row in range(3) for col in range(3)
            )
            self.assertLess(error, 1e-10)
        self.assertLess(validate_engine_xyz_convention(), 1e-10)

    def test_preserves_every_original_xyz_channel_value_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pose_path = tmp / "pose.json"
            fixture_pose(pose_path)
            source = make_lua()
            output, report = convert_direct_table(source, pose_path)
            self.assertTrue(output.startswith("-- " + APPLIED_MARKER))
            before = parse_tables(source)
            after = parse_tables(output)
            self.assertEqual(len(before), 13)
            self.assertEqual(len(after), 13)
            for old, new in zip(before, after):
                self.assertEqual(old["name"], new["name"])
                self.assertEqual(old["values"], new["values"])
                self.assertEqual(old["indices"], new["indices"])
            self.assertTrue(report["source_channel_values_preserved"])
            self.assertEqual(report["rotation_channel_order"], "XYZ")
            self.assertEqual(report["rotation_conversion"], "none; original 16-bit XYZ values preserved")
            self.assertFalse(report["mario_pose_anchor_applied"])
            self.assertEqual(report["clip_count"], 13)
            self.assertLess(report["gta_idle_frame_zero_max_error_radians"], math.radians(0.02))
            self.assertEqual(
                report["rotation_basis_validation"],
                "NOT_VALIDATED_FOR_COMPILED_CS_MESH",
            )

    def test_rejects_nonzero_root_translation(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pose_path = tmp / "pose.json"
            fixture_pose(pose_path)
            source, replacements = re.subn(
                r'(smlua_anim_util_register_animation\(\s*"cj64_anim_idle".*?\{\s*)0x0000',
                r'\g<1>0x0001',
                make_lua(),
                count=1,
                flags=re.S,
            )
            self.assertEqual(replacements, 1)
            with self.assertRaisesRegex(ValueError, "root translation"):
                convert_direct_table(source, pose_path)

    def test_rejects_declared_frame_count_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pose_path = tmp / "pose.json"
            fixture_pose(pose_path)
            source = make_lua().replace(
                'smlua_anim_util_register_animation("cj64_anim_run", 0, 1, 0, 0, 2,',
                'smlua_anim_util_register_animation("cj64_anim_run", 0, 1, 0, 0, 1,',
                1,
            )
            with self.assertRaisesRegex(ValueError, "declared 2 frames"):
                convert_direct_table(source, pose_path)

    def test_refuses_a_previous_zxy_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pose_path = tmp / "pose.json"
            fixture_pose(pose_path)
            source = "-- CJ64_CS_GTA_DIRECT_SM64_ZXY_CHANNEL_ORDER_APPLIED\n" + make_lua()
            with self.assertRaisesRegex(ValueError, "Rejected ZXY-converted"):
                convert_direct_table(source, pose_path)

    def test_refuses_duplicate_packaging(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pose_path = tmp / "pose.json"
            fixture_pose(pose_path)
            output, _report = convert_direct_table(make_lua(), pose_path)
            with self.assertRaisesRegex(ValueError, "marker is already present"):
                convert_direct_table(output, pose_path)

    def test_expected_clip_set_is_exact(self):
        self.assertEqual(len(CLIP_NAMES), 13)


if __name__ == "__main__":
    unittest.main()
