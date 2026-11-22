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

The Fast64-Gart traversal was inspected against the Mario
character template. It exports these 20 GeoLayout animation nodes, in order:

`Body`, `Butt`, `Torso`, `Head`, `Left Arm`, `Left Arm Color`,
`Left Forearm`, `Left Hand`, `Right Arm`, `Right Arm Color`,
`Right Forearm`, `Right Hand`, `Left Thigh`, `Left Thigh Color`,
`Left Leg`, `Left Shoe`, `Right Thigh`, `Right Thigh Color`,
`Right Leg`, `Right Shoe`.

The owner-provided IFP was converted to a private first-pass Lua module with
13 calls to `smlua_anim_util_register_animation`. Each clip has 63 channels:
three fixed-zero root translation channels and three rotation channels for
each of the 20 Fast64-Gart nodes. Each index table has 126 entries. Samples are
generated at 30 FPS, quaternion tracks are interpolated with slerp, converted
to 16-bit SM64 Euler angles, and mapped using the inspected source/target rest
rotations in `tools/cj64_sm64_animation_retarget_map.json`. Loop end indices
are zero-based and point to the final sampled frame.

The reproducible generator is
`tools/generate_cj_sm64_animations.py`. It takes a user-supplied local
`ped.ifp` and writes a Lua module plus a JSON report. Example:

```sh
python3 tools/generate_cj_sm64_animations.py ped.ifp \
  --map cj64_sm64_animation_retarget_map.json \
  --output cj64_gta_animations.lua
```

Root translation is fixed to zero so these clips do not control native
SM64CoopDX player movement or physics. The Lua module also refuses to apply
a role until the character replacement state explicitly reports
`animationReady = true`.

## CJ skin transfer preview

The earlier rig-transfer preview was generated from the inspected dual-rig Blender
scene by `tools/prepare_cj_rig_transfer.py` and
`.github/workflows/cj-rig-transfer.yml`. The workflow has since been expanded
to run inspection and export in Blender 3.6 as one reproducible pipeline.

The transfer:
- Copies the CJ mesh and retains its source textures/UVs.
- Converts the source FBX Y-up rest space to the Mario template X-up space.
- Repositions the Mario/Fast64-Gart animation bones using the corresponding CJ
  source rest matrices.
- Collapses each original FBX vertex's mapped source weights to its strongest
  Mario deform group, assigning exactly one bone at weight 1.0.
- Uses nearest-bone-segment assignment only as a fallback for unmapped source vertices.
- Preserves an evaluated height of 2.8 Blender units (280 SM64 units).

The previous preview artifact was named `CJ64-rig-transfer-preview` and contained an editable Blender scene, report, and rest-pose render. The updated Fast64-Gart workflow exports a DynOS actor as `CJ64-rigged-actor`, using one bone per vertex at weight 1.0. This newer build must pass CI and visual inspection; it has not been tested in SM64CoopDX or Android yet.

## Integration boundary

**The generated tables are not active in CJ64 yet.** The last verified public
`cj_geo` package remains a static mesh. The updated workflow now attempts to
produce a separate rigged Fast64-Gart actor; that new export is not yet a verified
release.

Remaining work:
1. Visually inspect idle, walk, run, jump, fall, land, and swim poses; correct
   any weighting, rest-basis, or axis errors.
2. Verify the new Fast64-Gart export and correct any CI, texture, or GeoLayout errors.
3. Load the private animation Lua module and connect each role to the matching
   native Mario action/animation state, retaining a safe fallback.
4. Test in SM64CoopDX, including the Android build.

The earlier Lua output passed structural checks (13 registrations, 63
channels and 126 index entries per clip), but it used the preliminary rig map.
It must be regenerated with the map emitted by the updated rig-transfer
workflow. The private Lua output and commercial IFP are not committed here.



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

The controller and Fast64-Gart export pipeline are committed, but they are not
yet considered working in-game until the new workflow passes, the rest and
animated poses are visually inspected, and the actor is tested in
SM64CoopDX on Android.
