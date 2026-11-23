import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from normalize_cs_animation_tables import (  # noqa: E402
    calibrate_text,
    decode_angle,
    encode_angle,
    euler_xyz,
    q_from_euler_xyz,
    qmul,
)


def build_registration(name, rotations, node_count, flags="0"):
    """Build a minimal Lua animation with three translation channels + XYZ per node."""
    channels = [[0], [0], [0]]
    for node_rotations in rotations:
        for axis in range(3):
            channels.append([encode_angle(frame[axis]) for frame in node_rotations])

    values = []
    indices = []
    for channel in channels:
        indices.extend((len(channel), len(values)))
        values.extend(channel)

    def emit(array):
        return "\n".join(
            "        " + ", ".join(f"0x{value:04X}" for value in array[i:i + 8]) + ","
            for i in range(0, len(array), 8)
        )

    last_frame = max(len(node_rotations[0]) for node_rotations in rotations) - 1
    return (
        f'smlua_anim_util_register_animation("{name}", {flags}, 1, 0, 0, {last_frame},\n'
        f'    {{\n{emit(values)}\n    }},\n'
        f'    {{\n{emit(indices)}\n    }}\n)\n'
    )


class AnimationCalibrationTests(unittest.TestCase):
    def test_neutral_idle_pose_is_removed_and_motion_is_preserved(self):
        node_count = 2
        idle_base = [
            q_from_euler_xyz(math.radians(0), math.radians(0), math.radians(90)),
            q_from_euler_xyz(math.radians(180), math.radians(-85), math.radians(90)),
        ]
        motion = [
            q_from_euler_xyz(0, 0, math.radians(10)),
            q_from_euler_xyz(math.radians(7), 0, 0),
        ]
        idle_rotations = []
        walk_rotations = []
        for base, delta in zip(idle_base, motion):
            neutral = euler_xyz(base)
            moved = euler_xyz(qmul(base, delta))
            idle_rotations.append([neutral, neutral])
            walk_rotations.append([moved, moved])

        source = (
            "-- fixture header\n"
            + build_registration("cj64_anim_idle", idle_rotations, node_count)
            + build_registration("cj64_anim_walk", walk_rotations, node_count, "ANIM_FLAG_NOLOOP")
            + 'CJ64_GTA_ANIMATIONS.names["idle"] = "cj64_anim_idle"\n'
        )
        output, report = calibrate_text(source, reference="cj64_anim_idle", nodes=node_count)

        parsed, _ = calibrate_text(output, reference="cj64_anim_idle", nodes=node_count)
        self.assertEqual(output, parsed, "calibration must be idempotent")
        self.assertEqual(report["clip_count"], 2)
        self.assertTrue(report["neutral_reference_identity"])
        self.assertFalse(report["visual_validation"])
        self.assertFalse(report["in_game_validation"])

        for clip_name in ("cj64_anim_idle", "cj64_anim_walk"):
            block = next(item for item in report["clips"] if item["name"] == clip_name)
            self.assertEqual(block["channels"], 3 + node_count * 3)

        walk_lines = output.split('smlua_anim_util_register_animation("cj64_anim_walk"', 1)[1]
        values_block = walk_lines.split("{", 1)[1].split("}", 1)[0]
        values = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{4})", values_block)]
        indices_block = walk_lines.split("{", 2)[2].split("}", 1)[0]
        indices = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{4})", indices_block)]
        rz_count, rz_offset = indices[2 * 5:2 * 5 + 2]
        self.assertGreaterEqual(rz_count, 1)
        self.assertAlmostEqual(
            decode_angle(values[rz_offset]),
            math.radians(10),
            delta=math.radians(0.03),
        )

    def test_rejects_out_of_bounds_channel(self):
        source = build_registration(
            "cj64_anim_idle", [[(0.0, 0.0, 0.0)]], node_count=1
        )
        source = source.replace("0x0001, 0x0003", "0x0001, 0xFFFF")
        with self.assertRaises(ValueError):
            calibrate_text(source, reference="cj64_anim_idle", nodes=1)

    def test_rejects_duplicate_animation_names(self):
        source = build_registration(
            "cj64_anim_idle", [[(0.0, 0.0, 0.0)]], node_count=1
        )
        source += build_registration(
            "cj64_anim_idle", [[(0.0, 0.0, 0.0)]], node_count=1
        )
        with self.assertRaises(ValueError):
            calibrate_text(source, reference="cj64_anim_idle", nodes=1)

    def test_preserves_translation_channels(self):
        source = build_registration(
            "cj64_anim_idle", [[(0.0, 0.0, math.radians(90))]], node_count=1
        )
        output, _ = calibrate_text(source, reference="cj64_anim_idle", nodes=1)
        first_values = output.split("{", 1)[1].split("}", 1)[0]
        self.assertEqual(
            [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{4})", first_values)][:3],
            [0, 0, 0],
        )


if __name__ == "__main__":
    unittest.main()
