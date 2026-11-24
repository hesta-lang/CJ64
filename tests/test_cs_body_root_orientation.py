import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from apply_cs_body_root_orientation import (
    MARKER,
    apply_body_root_orientation,
    parse_registrations,
)

BODY_ORIENTATION = (0x0000, 0x3FFF, 0x0000)


def fixture_pose(path, body=BODY_ORIENTATION):
    path.write_text(json.dumps({
        "format": "cj64-native-cs-pose-anchor-sm64-zxy-v2",
        "node_count": 20,
        "nodes": [
            {
                "index": index,
                "node": "Body" if index == 0 else f"Node {index}",
                "first_frame_euler16": [f"{value:04X}" for value in (body if index == 0 else (0, 0, 0))],
            }
            for index in range(20)
        ],
    }), encoding="utf-8")


def make_animation(name, frames):
    channels = [[0], [0], [0]]
    # Deliberately give the GTA Body node a non-CS orientation. This is the
    # source-root track that made the compiled actor appear laid down.
    channels.extend([
        [0x2000 + frame for frame in range(frames)],
        [0x6000 + frame for frame in range(frames)],
        [0xE000 + frame for frame in range(frames)],
    ])
    # Give multiple child channels non-zero motion so accidental changes are caught.
    for node in range(1, 20):
        for axis in range(3):
            channels.append([
                ((node * 0x321 + axis * 0x111 + frame * 0x21) & 0xFFFF)
                if (node in (1, 4, 7, 12, 19) or frame == 0)
                else 0
                for frame in range(frames)
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
        f'smlua_anim_util_register_animation("{name}", 0, 1, 0, 0, {frames - 1},\n'
        "    {\n" + fmt(values) + "\n    },\n"
        "    {\n" + fmt(indices) + "\n    }\n)\n"
    )


def fixture_source():
    names = [
        "cj64_anim_idle", "cj64_anim_walk_start", "cj64_anim_walk",
        "cj64_anim_run", "cj64_anim_sprint_candidate", "cj64_anim_run_stop",
        "cj64_anim_jump_start", "cj64_anim_jump_air", "cj64_anim_jump_land",
        "cj64_anim_fall", "cj64_anim_fall_air", "cj64_anim_fall_land",
        "cj64_anim_swim_tread",
    ]
    return "\n".join(
        make_animation(name, 46 if name == "cj64_anim_idle" else 5)
        for name in names
    )


class CSBodyRootOrientationTests(unittest.TestCase):
    def test_only_body_root_is_aligned_and_all_other_channels_are_unchanged(self):
        source = fixture_source()
        with tempfile.TemporaryDirectory() as tmp:
            pose = Path(tmp) / "native-pose.json"
            fixture_pose(pose)
            output, report = apply_body_root_orientation(source, pose_path=pose)

        self.assertTrue(output.startswith("-- " + MARKER))
        self.assertEqual(report["clip_count"], 13)
        self.assertEqual(report["node_count"], 20)
        self.assertTrue(report["gta_body_root_orientation_replaced"])
        self.assertEqual(report["articulated_nodes_modified"], 0)
        self.assertTrue(report["non_body_animation_channels"], "preserved exactly")
        self.assertEqual(report["body_root_xyz_euler16"], ["0000", "3FFF", "0000"])

        before = parse_registrations(source)
        after = parse_registrations(output)
        self.assertEqual(len(before), 13)
        self.assertEqual(len(after), 13)

        for original, fixed in zip(before, after):
            self.assertEqual(original["name"], fixed["name"])
            self.assertEqual(original["indices"], fixed["indices"])
            old_values, new_values = original["values"], fixed["values"]
            indices = fixed["indices"]

            # Game-owned player translation is unchanged and zero.
            for axis in range(3):
                count, offset = indices[axis * 2:axis * 2 + 2]
                self.assertEqual(old_values[offset:offset + count], [0])
                self.assertEqual(new_values[offset:offset + count], [0])

            # Body is the sole corrected node: X=0, Y=the CS anim_00 pose,
            # Z=0 on every frame, replacing the GTA Normal/root transform.
            body_counts = []
            for axis, expected in enumerate(BODY_ORIENTATION):
                channel = 3 + axis
                count, offset = indices[channel * 2:channel * 2 + 2]
                body_counts.append(count)
                self.assertEqual(
                    new_values[offset:offset + count],
                    [expected] * count,
                    (fixed["name"], "Body", axis),
                )
            self.assertEqual(len(set(body_counts)), 1)

            # Every channel of the other 19 animated parts stays byte-for-byte
            # the same, including the movement samples across all frames.
            for node in range(1, 20):
                for axis in range(3):
                    channel = 3 + node * 3 + axis
                    count, offset = indices[channel * 2:channel * 2 + 2]
                    self.assertEqual(
                        new_values[offset:offset + count],
                        old_values[offset:offset + count],
                        (fixed["name"], node, axis),
                    )

    def test_refuses_double_application(self):
        with tempfile.TemporaryDirectory() as tmp:
            pose = Path(tmp) / "native-pose.json"
            fixture_pose(pose)
            output, _ = apply_body_root_orientation(fixture_source(), pose_path=pose)
            with self.assertRaisesRegex(ValueError, "already been applied"):
                apply_body_root_orientation(output, pose_path=pose)

    def test_rejects_wrong_native_body_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            pose = Path(tmp) / "bad-pose.json"
            fixture_pose(pose, body=(0x0100, 0x3FFF, 0))
            with self.assertRaisesRegex(ValueError, "expected XYZ"):
                apply_body_root_orientation(fixture_source(), pose_path=pose)

    def test_rejects_nonzero_player_root_translation(self):
        source = fixture_source()
        first = re.search(
            r'(smlua_anim_util_register_animation\(\s*"cj64_anim_idle".*?\{\s*)(.*?)(\s*\},\s*\{\s*)',
            source, re.S
        )
        values = [int(value, 16) for value in re.findall(r"0x([0-9A-Fa-f]{1,4})", first.group(2))]
        values[0] = 1
        rendered = "\n".join(
            "        " + ", ".join(f"0x{x:04X}" for x in values[i:i + 12]) + ","
            for i in range(0, len(values), 12)
        )
        source = source[:first.start(2)] + rendered + source[first.end(2):]
        with tempfile.TemporaryDirectory() as tmp:
            pose = Path(tmp) / "native-pose.json"
            fixture_pose(pose)
            with self.assertRaisesRegex(ValueError, "root translation"):
                apply_body_root_orientation(source, pose_path=pose)


if __name__ == "__main__":
    unittest.main()
