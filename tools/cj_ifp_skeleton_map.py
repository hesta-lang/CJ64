"""Canonical GTA: San Andreas IFP bone hierarchy mapped to CJ FBX bone names.

The imported FBX carries helper-bone parenting that is not identical to the
ped.ifp/HAnim parent tree. IFP rotations are local to the canonical GTA
skeleton, so use this logical hierarchy while retaining each bone's actual
FBX bind/rest matrix as the source transform.
"""

GTA_IFP_SOURCE_PARENTS = {
    "root ground": None,
    "pelvis": "root ground",
    "spine lower": "pelvis",
    "spine middle": "spine lower",
    # The FBX includes a static upper-spine joint not represented by a
    # separate ped.ifp track; it remains in the rest chain.
    "spine upper": "spine middle",
    "head neck lower": "spine upper",
    "head neck upper": "head neck lower",
    "arm left shoulder 1": "head neck lower",
    "arm left shoulder 2": "arm left shoulder 1",
    "arm left elbow": "arm left shoulder 2",
    "arm left wrist": "arm left elbow",
    "arm right shoulder 1": "head neck lower",
    "arm right shoulder 2": "arm right shoulder 1",
    "arm right elbow": "arm right shoulder 2",
    "arm right wrist": "arm right elbow",
    "leg left thigh": "pelvis",
    "leg left knee": "leg left thigh",
    "leg left ankle": "leg left knee",
    "leg right thigh": "pelvis",
    "leg right knee": "leg right thigh",
    "leg right ankle": "leg right knee",
}


def build_ifp_parent_map(available_bones):
    available = set(available_bones)
    missing = sorted(set(GTA_IFP_SOURCE_PARENTS) - available)
    if missing:
        raise ValueError(
            "The imported CJ armature is missing required GTA IFP bones: "
            + ", ".join(missing)
        )
    return dict(GTA_IFP_SOURCE_PARENTS)
