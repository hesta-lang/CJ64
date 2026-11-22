# CJ original animations: extraction and integration status

## Source package

The owner supplied the original GTA: San Andreas `anim/ped.ifp` package.
It parses as ANP3 package `ped`, with 294 clips, 1,433,248 bytes, and no
trailing data. The 13 selected candidates contain 5,097 source keyframes:

- `IDLE_stance`
- `WALK_start`, `WALK_player`
- `run_player`, `sprint_civi`, `Run_stop`
- `JUMP_launch`, `JUMP_glide`, `JUMP_land`
- `FALL_fall`, `FALL_glide`, `FALL_land`
- `Swim_Tread`

`sprint_civi` is a generic civilian sprint candidate, not confirmed as a
CJ-exclusive animation. The commercial IFP and keyframe-derived Lua output are
not stored in this public repository.

## First-pass SM64CoopDX retarget

The official Coop Deluxe Fast64 traversal was inspected against the Mario
character template. It exports these 20 GeoLayout animation nodes, in order:

`Body`, `Butt`, `Torso`, `Head`, `Left Arm`, `Left Arm Color`,
`Left Forearm`, `Left Hand`, `Right Arm`, `Right Arm Color`,
`Right Forearm`, `Right Hand`, `Left Thigh`, `Left Thigh Color`,
`Left Leg`, `Left Shoe`, `Right Thigh`, `Right Thigh Color`,
`Right Leg`, `Right Shoe`.

The owner-provided IFP was converted to a private first-pass Lua module with
13 calls to `smlua_anim_util_register_animation`. Each clip has 63 channels:
three fixed-zero root translation channels and three rotation channels for
each of the 20 Fast64 nodes. Each index table has 126 entries. Samples are
generated at 30 FPS, quaternion tracks are interpolated with slerp, converted
to 16-bit SM64 Euler angles, and mapped using the inspected source/target rest
rotations in `tools/cj64_sm64_animation_retarget_map.json`. Loop end indices
are zero-based and point to the final sampled frame.

The reproducible generator is
`tools/generate_cj_sm64_animations.py`. It takes a user-supplied local
`ped.ifp` and writes a Lua module plus a JSON report. Example:

```sh
python3 tools/generate_cj_sm64_animations.py ped.ifp --output CJ64-GTA-SA-Animations.lua
```

Root translation is fixed to zero so these clips do not control native
SM64CoopDX player movement or physics. The Lua module also refuses to apply
a role until the character replacement state explicitly reports
`animationReady = true`.

## CJ skin transfer preview

A first-pass rig transfer was generated from the inspected dual-rig Blender
scene by `tools/prepare_cj_rig_transfer.py` and
`.github/workflows/cj-rig-transfer.yml`.

The transfer:
- Copies the CJ mesh and retains its source textures/UVs.
- Converts the source FBX Y-up rest space to the Mario template X-up space.
- Repositions the Mario/Fast64 animation bones using the corresponding CJ
  source rest matrices.
- Generates deterministic nearest-bone-segment weights for the Mario deform
  bones instead of collapsing multiple GTA joints into one bind matrix.
- Covers all 1,630 vertices with 15 deform groups.
- Preserves an evaluated height of 2.8 Blender units (280 SM64 units).

The successful workflow artifact is named `CJ64-rig-transfer-preview`.
It contains an editable `CJ64-CJ-Rig-Transfer.blend`, a JSON report, and a rendered rest-pose preview (`CJ64-Rigged-Rest-Preview.png`).
This is a first-pass skinned Blender scene only; it has not yet been exported
through Fast64 or tested in SM64CoopDX. The weighting algorithm and rest pose
still require visual inspection before the actor is considered animation-ready.

## Integration boundary

**The generated tables are not active in CJ64 yet.** The public `cj_geo`
DynOS actor remains a static mesh. The new rigged Blender preview is separate
from that actor and has not yet been exported as the final animated GeoLayout.

Remaining work:
1. Visually inspect idle, walk, run, jump, fall, land, and swim poses; correct
   any weighting, rest-basis, or axis errors.
2. Export the skinned `cj_geo` actor with the 20-node hierarchy using Coop
   Deluxe Fast64.
3. Load the private animation Lua module and connect each role to the matching
   native Mario action/animation state, retaining a safe fallback.
4. Test in SM64CoopDX, including the Android build.

The current Lua output passed structural checks (13 registrations, 63
channels and 126 index entries per clip, all channel offsets within the
values array). It has not been visually approved, Fast64-exported with the
rigged CJ scene, or tested inside SM64CoopDX on Android. The private Lua
output is distributed separately to the owner; neither it nor the commercial
IFP is committed here.



## Runtime controller and exported actor

`main.lua` now loads two optional modules: `rigged_actor.lua` and the
private `cj64_gta_animations.lua`. `character.lua` contains the action-state
controller for idle, walk, run, sprint candidate, jump, fall, landing, and
swimming. It tracks each player separately and changes animation only when
the selected role changes.

The controller is guarded: the static actor cannot activate the animation
tables. Both the rigged actor marker and private animation module must be
present. The rig-transfer workflow generates the current rest-basis map from
the actual exported armature; use that map with
`tools/generate_cj_sm64_animations.py`:

```sh
python3 tools/generate_cj_sm64_animations.py ped.ifp \
  --map cj64_sm64_animation_retarget_map.json \
  --output cj64_gta_animations.lua
```

Place the generated `cj64_gta_animations.lua` in the mod root alongside the
rigged actor package. Neither the original IFP nor the derived keyframe arrays
are committed to the public repository.

The controller and Fast64 export pipeline are committed, but they are not
yet considered working in-game until the new workflow passes, the rest and
animated poses are visually inspected, and the actor is tested in
SM64CoopDX on Android.
