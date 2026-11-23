# CJ original animations: extraction and integration status

## Source package

The owner supplied the original GTA: San Andreas `anim/ped.ifp` package.
It parses as ANP3 package `ped`, with 294 clips and 1,433,248 bytes. The
13 selected candidates contain 5,097 source keyframes:

- `IDLE_stance`
- `WALK_start`, `WALK_player`
- `run_player`, `sprint_civi`, `Run_stop`
- `JUMP_launch`, `JUMP_glide`, `JUMP_land`
- `FALL_fall`, `FALL_glide`, `FALL_land`
- `Swim_Tread`

`sprint_civi` is a generic civilian sprint candidate, not confirmed as a
CJ-exclusive animation. The IFP and keyframe-derived Lua output are not stored
in this public repository.

## First-pass retarget target

The experimental FBX/Fast64 transfer inspected the Mario character template and
generated a 20-node animation target in this order:

`Body`, `Butt`, `Torso`, `Head`, `Left Arm`, `Left Arm Color`,
`Left Forearm`, `Left Hand`, `Right Arm`, `Right Arm Color`,
`Right Forearm`, `Right Hand`, `Left Thigh`, `Left Thigh Color`,
`Left Leg`, `Left Shoe`, `Right Thigh`, `Right Thigh Color`,
`Right Leg`, `Right Shoe`.

The private Lua tables have 63 channels per clip: three zeroed root translation
channels and three rotation channels for each of those 20 Fast64/Mario nodes.
They were generated using the FBX-to-Mario rest-space map in
`tools/cj64_sm64_animation_retarget_map.json`. Their structural report says
`STRUCTURAL_GENERATION_ONLY_NOT_VISUALLY_OR_IN_GAME_VALIDATED`.

## Why the CS actor was lying down

The current Character Select model is a compiled DynOS binary with 20
`GEO_ANIMATED_PART` commands. The binary's animated-part count is known, but
its node order, parent hierarchy and rest rotations have not been demonstrated
to match the FBX/Fast64 target above. It was incorrect to infer compatibility
from the count alone.

Inspection of the actual private `cj64_gta_animations.lua` file showed that
the first frame of `cj64_anim_idle` contains approximately:

- `Body`: X 0.6°, Y -0.6°, Z 90.1°.
- `Butt`: X -180.0°, Y -85.4°, Z 90.0°.

These are channel values generated for the FBX/Fast64 Mario rig. When interpreted
as if they belonged to the unverified CS node layout, they can rotate the body
onto its side and place animated parts over one another. The supplied screenshot
is consistent with this failure.

## Current runtime safeguard

Version `0.1.3-alpha` sets `CJ64.useGTAAnimations = false` by default.
The controller does not load or apply the private GTA tables in this mode.
SM64CoopDX's native player animation handling remains in control while the CS
model is isolated for an orientation/mesh test.

The previous helper `tools/normalize_cs_animation_tables.py` applies the inverse
of the first reference quaternion to each numbered channel. That operation does
not discover the CS node order, validate its hierarchy, or prove that source and
target channels refer to the same body parts. Running it alone cannot establish
a correct CS retarget, so its output is still experimental.

## Required work before re-enabling GTA clips

1. Inspect the CS actor's actual animated-part hierarchy and rest transforms,
   not just the number of nodes.
2. Establish a verified mapping from each CS node to its intended GTA source
   bone and compare the neutral pose.
3. Retarget the IFP tracks using that mapping and render pose previews for idle,
   walk, run, jump, fall, landing and swimming.
4. Enable the clips only after the previews and in-game tests match the model.

The CS actor has only 20 animated parts, not the complete GTA skeleton. It
cannot independently animate every source track (for example, separate finger
and toe tracks) unless the model is rebuilt with an expanded skeleton and
matching geometry weights.
