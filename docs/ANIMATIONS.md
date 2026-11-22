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
rotations in `tools/cj64_sm64_animation_retarget_map.json`.

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

## Integration boundary

**The generated tables are not active in CJ64 yet.** The current exported
`cj_geo` DynOS actor is a static mesh. It does not contain the compatible
20-node animated GeoLayout hierarchy or the corresponding transferred skin
weights. Registering and selecting the tables against this static mesh cannot
visibly animate CJ.

Before enabling the module, the project must:
1. Transfer the CJ mesh weights to the Mario/Fast64 deform bones while
   preserving the 280-SM64-unit visual height and texture/TMEM fixes.
2. Inspect the retargeted idle, walk, run, jump, fall, land, and swim poses in
   Blender; correct rest-basis or axis errors found in those previews.
3. Export the skinned `cj_geo` actor with the 20-node hierarchy using
   Coop Deluxe Fast64.
4. Load the private animation Lua module and connect each role to the matching
   native Mario action/animation state, retaining a safe fallback.
5. Test in SM64CoopDX, including the Android build.

The current Lua output passed structural checks (13 registrations, 63
channels and 126 index entries per clip, all channel offsets within the
values array). It has **not** been visually approved in Blender, tested by
Fast64 export with a skinned CJ model, or tested inside SM64CoopDX on Android.
The private Lua output is distributed separately to the owner; neither it nor
the commercial IFP is committed here.
