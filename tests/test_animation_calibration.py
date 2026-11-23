import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from normalize_cs_animation_tables import calibrate_text, decode_angle, encode_angle, euler_xyz, q_from_euler_xyz, qmul  # noqa: E402


def build_registration(name, rotations, flags="0"):
    channels = [[0], [0], [0]]
    for node_rotations in rotations:
        for axis in range(3):
            channels.append([encode_angle(frame[axis]) for frame in node_rotations])
    values, indices = [], []
    for channel in channels:
        indices.extend((len(channel), len(values)))
        values.extend(channel)

    def emit(array):
        return "\n".join(
            "        " + ", ".join(f"0x{value:04X}" for value in array[i:i + 8]) + ","
            for i in range(0, len(array), 8)
        )

    last_frame = max(len(node_rotations) for node_rotations in rotations) - 1
    return (
        f'smlua_anim_util_register_animation("{name}", {flags}, 1, 0, 0, {last_frame},\n'
        f'    {{\n{emit(values)}\n    }},\n'
        f'    {{\n{emit(indices)}\n    }}\n)\n'
    )


class AnimationCalibrationTests(unittest.TestCase):
    def test_neutral_idle_pose_is_removed_and_motion_is_preserved(self):
        bases = [
            q_from_euler_xyz(0, 0, math.radians(90)),
            q_from_euler_xyz(math.radians(180), math.radians(-85), math.radians(90)),
        ]
        deltas = [
            q_from_euler_xyz(0, 0, math.radians(10)),
            q_from_euler_xyz(math.radians(7), 0, 0),
        ]
        idle, walk = [], []
        for base, delta in zip(bases, deltas):
            neutral = euler_xyz(base)
            moved = euler_xyz(qmul(base, delta))
            idle.append([neutral, neutral])
            walk.append([moved, moved])
        source = (
            "-- fixture\n"
            + build_registration("cj64_anim_idle", idle)
            + build_registration("cj64_anim_walk", walk, "ANIM_FLAG_NOLOOP")
        )
        output, report = calibrate_text(source, nodes=2)
        second_output, _ = calibrate_text(output, nodes=2)
        self.assertEqual(output, second_output, "calibration must be idempotent")
        self.assertTrue(report["neutral_reference_identity"])
        self.assertFalse(report["visual_validation"])
        self.assertFalse(report["in_game_validation"])
        walk_text = output.split('smlua_anim_util_register_animation("cj64_anim_walk"', 1)[1]
        arrays = walk_text.split("{", 2)
        values = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{4})", arrays[1].split("}", 1)[0])]
        indices = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{4})", arrays[2].split("}", 1)[0])]
        count, offset = indices[10:12]  # node 0's Z-rotation channel
        self.assertGreater(count, 0)
        self.assertAlmostEqual(decode_angle(values[offset]), math.radians(10), delta=math.radians(0.03))

    def test_preserves_fixed_zero_translation_channels(self):
        source = build_registration("cj64_anim_idle", [[(0, 0, math.radians(90))]])
        output, _ = calibrate_text(source, nodes=1)
        first_values = output.split("{", 1)[1].split("}", 1)[0]
        decoded = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{4})", first_values)]
        self.assertEqual(decoded[:3], [0, 0, 0])

    def test_rejects_out_of_bounds_channel(self):
        source = build_registration("cj64_anim_idle", [[(0.0, 0.0, 0.0)]])
        source = source.replace("0x0001, 0x0003", "0x0001, 0xFFFF")
        with self.assertRaises(ValueError):
            calibrate_text(source, nodes=1)

    def test_rejects_duplicate_animation_names(self):
        source = build_registration("cj64_anim_idle", [[(0.0, 0.0, 0.0)]])
        source += build_registration("cj64_anim_idle", [[(0.0, 0.0, 0.0)]])
        with self.assertRaises(ValueError):
            calibrate_text(source, nodes=1)

    def test_rejects_header_frame_count_mismatch(self):
        source = build_registration("cj64_anim_idle", [[(0.0, 0.0, 0.0)]])
        source = source.replace(", 0, 0, 0,\n", ", 0, 0, 1,\n", 1)
        with self.assertRaises(ValueError):
            calibrate_text(source, nodes=1)


if __name__ == "__main__":
    unittest.main()
