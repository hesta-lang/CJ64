"""Skin-weight mapping corrections for CJ's separated shoulder joints."""

SHOULDER_WEIGHT_OVERRIDES = {
    "arm left shoulder 1": "Left Arm",
    "arm left shoulder 2": "Left Arm Color",
    "arm right shoulder 1": "Right Arm",
    "arm right shoulder 2": "Right Arm Color",
}


def apply_shoulder_weight_retarget(mapping):
    """Keep clavicle/shoulder and upper-arm source weights on separate nodes."""
    result = dict(mapping)
    result.update(SHOULDER_WEIGHT_OVERRIDES)
    return result


def required_shoulder_deform_groups():
    return tuple(SHOULDER_WEIGHT_OVERRIDES.values())
