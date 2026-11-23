import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from animation_hierarchy import (  # noqa: E402
    IDENTITY,
    build_source_global_deltas,
    retarget_global_deltas_to_mario,
    q_from_axis_angle,
    qmul,
    qinv,
    qnorm,
)


def assert_quat_close(test, actual, expected, places=6):
    actual = qnorm(actual)
    expected = qnorm(expected)
    # q and -q encode the same rotation.
    direct = max(abs(a - b) for a, b in zip(actual, expected))
    opposite = max(abs(a + b) for a, b in zip(actual, expected))
    test.assertLessEqual(min(direct, opposite), 10 ** (-places))


class AnimationHierarchyRetargetTests(unittest.TestCase):
    def test_identity_source_pose_produces_identity_mario_channels(self):
        source_parents = {
            "root": None,
            "pelvis": "root",
            "spine": "pelvis",
            "neck": "spine",
            "shoulder": "neck",
            "upperarm": "shoulder",
        }
        source_rest = {
            "root": IDENTITY,
            "pelvis": q_from_axis_angle((0, 0, 1), 0.2),
            "spine": q_from_axis_angle((0, 1, 0), -0.3),
            "neck": q_from_axis_angle((1, 0, 0), 0.4),
            "shoulder": q_from_axis_angle((0, 0, 1), -0.5),
            "upperarm": q_from_axis_angle((0, 1, 0), 0.6),
        }
        source_deltas = build_source_global_deltas(
            source_parents, source_rest, {}, root_bone="root"
        )
        target_nodes = ["Body", "Butt", "Torso", "Head", "Left Arm", "Left Arm Color"]
        target_parent_nodes = {
            "Body": None,
            "Butt": "Body",
            "Torso": "Butt",
            "Head": "Torso",
            # Deliberately differs from GTA: shoulder's source parent is Neck.
            "Left Arm": "Torso",
            "Left Arm Color": "Left Arm",
        }
        target_parent_rest = {
            "Body": IDENTITY,
            "Butt": q_from_axis_angle((1, 0, 0), 0.1),
            "Torso": q_from_axis_angle((0, 1, 0), 0.2),
            "Head": q_from_axis_angle((0, 0, 1), 0.3),
            "Left Arm": q_from_axis_angle((0, 0, 1), -0.2),
            "Left Arm Color": q_from_axis_angle((1, 0, 0), 0.25),
        }
        node_source_bone = {
            "Body": None,
            "Butt": "pelvis",
            "Torso": "spine",
            "Head": "neck",
            "Left Arm": "shoulder",
            "Left Arm Color": "upperarm",
        }
        channels, target_globals = retarget_global_deltas_to_mario(
            target_nodes,
            target_parent_nodes,
            target_parent_rest,
            node_source_bone,
            source_deltas,
            IDENTITY,
            root_node="Body",
        )
        for node in target_nodes:
            assert_quat_close(self, channels[node], IDENTITY)
            assert_quat_close(self, target_globals[node], IDENTITY)

    def test_parent_motion_is_compensated_when_source_and_target_hierarchies_differ(self):
        source_parents = {
            "root": None,
            "pelvis": "root",
            "spine": "pelvis",
            "neck": "spine",
            "shoulder": "neck",
            "upperarm": "shoulder",
        }
        source_rest = {
            "root": IDENTITY,
            "pelvis": q_from_axis_angle((0, 0, 1), 0.15),
            "spine": q_from_axis_angle((0, 1, 0), -0.2),
            "neck": q_from_axis_angle((1, 0, 0), 0.25),
            "shoulder": q_from_axis_angle((0, 0, 1), -0.1),
            "upperarm": q_from_axis_angle((0, 1, 0), 0.3),
        }
        animated = {
            "pelvis": q_from_axis_angle((0, 0, 1), 0.12),
            "spine": q_from_axis_angle((0, 1, 0), 0.18),
            "neck": q_from_axis_angle((1, 0, 0), 0.55),
            "shoulder": q_from_axis_angle((0, 0, 1), -0.22),
            "upperarm": q_from_axis_angle((0, 1, 0), 0.31),
        }
        source_deltas = build_source_global_deltas(
            source_parents, source_rest, animated, root_bone="root"
        )
        target_nodes = ["Body", "Butt", "Torso", "Head", "Left Arm", "Left Arm Color"]
        target_parent_nodes = {
            "Body": None,
            "Butt": "Body",
            "Torso": "Butt",
            "Head": "Torso",
            "Left Arm": "Torso",
            "Left Arm Color": "Left Arm",
        }
        target_parent_rest = {
            "Body": IDENTITY,
            "Butt": q_from_axis_angle((1, 0, 0), 0.4),
            "Torso": q_from_axis_angle((0, 1, 0), -0.35),
            "Head": q_from_axis_angle((0, 0, 1), 0.2),
            "Left Arm": q_from_axis_angle((0, 0, 1), -0.3),
            "Left Arm Color": q_from_axis_angle((1, 0, 0), 0.25),
        }
        node_source_bone = {
            "Body": None,
            "Butt": "pelvis",
            "Torso": "spine",
            "Head": "neck",
            "Left Arm": "shoulder",
            "Left Arm Color": "upperarm",
        }
        axis_align = q_from_axis_angle((0, 0, 1), -math.pi / 2)
        channels, target_globals = retarget_global_deltas_to_mario(
            target_nodes,
            target_parent_nodes,
            target_parent_rest,
            node_source_bone,
            source_deltas,
            axis_align,
            root_node="Body",
        )

        # The shoulder is under Neck in GTA but under Torso in Mario.
        # The output channel must therefore include Neck's motion relative
        # to Torso, rather than using only the local shoulder track.
        desired_shoulder_global = qmul(
            qmul(axis_align, source_deltas["shoulder"]),
            qinv(axis_align),
        )
        assert_quat_close(self, target_globals["Left Arm"], desired_shoulder_global)

        # Every mapped node must reconstruct the source's global pose after
        # applying the generated local channel through its destination parent.
        for node in target_nodes:
            source_name = node_source_bone[node]
            if source_name is None:
                continue
            desired = qmul(qmul(axis_align, source_deltas[source_name]), qinv(axis_align))
            assert_quat_close(self, target_globals[node], desired)

        # The shoulder channel itself is not just the raw shoulder track:
        # parent-axis and hierarchy compensation are both applied.
        self.assertGreater(
            max(abs(a - b) for a, b in zip(channels["Left Arm"], animated["shoulder"])),
            0.02,
        )


if __name__ == "__main__":
    unittest.main()
