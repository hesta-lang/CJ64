import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from apply_cs_body_root_orientation import (
    MARKER,
    apply_body_root_orientation,
    parse_registrations,
)

EXPECTED_BODY_Y = 0x3FFF


def fixture():
    blocks = []
    for name in ("cj64_anim_idle", "cj64_anim_fall"):
        channels = [[0], [0], [0]]
        for node in range(20):
            for axis in range(3):
                if node == 2 and axis == 0:
                    channels.append([0x0100, 0x0200])
                elif node == 7 and axis == 2:
                    channels.append([0x0300, 0x0400])
                else:
                    channels.append([0, 0])
        values, indices = [], []
        for channel in channels:
            indices.extend((len(channel), len(values)))
            values.extend(channel)

        def fmt(items):
            return "\n".join(
                "        " + ", ".join(f"0x{x:04X}" for x in items[i:i + 12]) + ","
                for i in range(0, len(items), 12)
            )

        blocks.append(
            f'smlua_anim_util_register_animation("{name}", 0, 1, 0, 0, 1,\n'
            "    {\n" + fmt(values) + "\n    },\n"
            "    {\n" + fmt(indices) + "\n    }\n)\n"
        )
    return "\n".join(blocks)


class CSBodyRootOrientationTests(unittest.TestCase):
    def test_only_body_y_is_rotated_for_every_frame_and_clip(self):
        source = fixture()
        output, report = apply_body_root_orientation(source, expected_clips=2)
        self.assertIn(MARKER, output)
        self.assertEqual(report["clip_count"], 2)
        self.assertFalse(report["native_mario_pose_applied_to_limbs"])
        self.assertEqual(report["limb_nodes_modified"], 0)

        before = parse_registrations(source)
        after = parse_registrations(output)
        self.assertEqual(len(before), 2)
        self.assertEqual(len(after), 2)

        for original, fixed in zip(before, after):
            self.assertEqual(original["name"], fixed["name"])
            self.assertEqual(original["indices"], fixed["indices"])
            old_values, new_values = original["values"], fixed["values"]
            for axis in range(3):
                count, offset = fixed["indices"][3 + axis * 2:3 + axis * 2 + 2]
                samples = new_values[offset:offset + count]
                if axis == 1:
                    self.assertEqual(samples, [EXPECTED_BODY_Y, EXPECTED_BODY_Y])
                else:
                    self.assertEqual(samples, old_values[offset:offset + count])
            # All remaining 19 nodes are unchanged, including representative
            # non-zero shoulder and forearm samples in the fixture.
            for node in range(1, 20):
                for axis in range(3):
                    channel = 3 + node * 3 + axis
                    count, offset = fixed["indices"][channel * 2:channel * 2 + 2]
                    self.assertEqual(
                        new_values[offset:offset + count],
                        old_values[offset:offset + count],
                        (fixed["name"], node, axis),
                    )

    def test_refuses_double_application(self):
        output, _ = apply_body_root_orientation(fixture(), expected_clips=2)
        with self.assertRaisesRegex(ValueError, "already been applied"):
            apply_body_root_orientation(output, expected_clips=2)

    def test_refuses_a_pre_rotated_body(self):
        source = fixture()
        record = parse_registrations(source)[0]
        # Set an existing Body X sample to a non-zero value.
        start, end = record["span"]
        body_x_offset = record["indices"][6 + 1]
        values = record["values"]
        values[body_x_offset] = 0x0100
        # Rebuild only the fixture's first values array to simulate a source
        # that already contains Body motion; the parser must reject it.
        import re
        first = re.search(
            r'(smlua_anim_util_register_animation\(\s*"cj64_anim_idle".*?\{\s*)(.*?)(\s*\},\s*\{\s*)',
            source, re.S
        )
        rendered = "\n".join(
            "        " + ", ".join(f"0x{x:04X}" for x in values[i:i + 12]) + ","
            for i in range(0, len(values), 12)
        )
        source = source[:first.start(2)] + rendered + source[first.end(2):]
        with self.assertRaisesRegex(ValueError, "already contains motion"):
            apply_body_root_orientation(source, expected_clips=2)


if __name__ == "__main__":
    unittest.main()
