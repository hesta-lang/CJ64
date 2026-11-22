# CJ original animations: extraction and integration status

## Source package

The selected clips come from the user-supplied GTA: San Andreas `anim/ped.ifp`
package. The IFP itself and keyframe-derived Lua tables are not committed to
this repository.

The supplied ANP3 package was parsed successfully: package name `ped`, 294
clips, 1,433,248 bytes, and no trailing data. The 13 selected candidates below
contain 5,097 source keyframes in total:

- `IDLE_stance`
- `WALK_start`, `WALK_player`
- `run_player`, `sprint_civi`, `Run_stop`
- `JUMP_launch`, `JUMP_glide`, `JUMP_land`
- `FALL_fall`, `FALL_glide`, `FALL_land`
- `Swim_Tread`

`sprint_civi` is a generic civilian sprint candidate, not confirmed as a
CJ-exclusive animation.

## First-pass SM64 retarget data

The official Coop Deluxe Fast64 traversal was inspected against the Mario
character template. It exports exactly 20 GeoLayout animation nodes, in this
order:

`Body`, `Butt`, `Torso`, `Head`, `Left Arm`, `Left Arm Color`,
`Left Forearm`, `Left Hand`, `Right Arm`, `Right Arm Color`,
`Right Forearm`, `Right Hand`, `Left Thigh`, `Left Thigh Color`,
`Left Leg`, `Left Shoe`, `Right Thigh`, `Right Thigh Color`,
`Right Leg`, `Right Shoe`.

A first-pass retarget was generated locally as
`CJ64-Original-Animations.lua` (provided separately to the maintainer). It
contains all 13 registrations through `smlua_anim_util_register_animation`.
Each registration has 63 channels: three root translation channels fixed at
zero and three rotation channels for each of the 20 Fast64 nodes. Each index
table has 126 16-bit values.

Rotations are sampled at 30 FPS, expressed as deltas from the first
`IDLE_stance` reference keyframe, combined for source chains where the Mario
rig has fewer nodes, and encoded as SM64 16-bit Euler angle values. Root
translation is deliberately zeroed so native MarioState movement, physics,
and collision remain authoritative.

## Important integration boundary

**The animation tables are not yet active in CJ64.** The current exported
`cj_geo` DynOS actor is still a static mesh: it does not contain the 20-node
animated GeoLayout rig or compatible vertex weights. Registering these clips
against that static model would not animate CJ.

Before enabling the tables, the project still needs to:
1. Transfer the CJ mesh weights to the Mario rig and preserve the 280-unit size
   and existing texture/TMEM fixes.
2. Visually validate the retargeted poses and joint axes in Blender.
3. Export the skinned actor and animations with Fast64-Coop.
4. Connect idle, walk, run, jump, fall, land, and swim clips to native Mario
   action states while retaining the vanilla fallback.

The current first-pass output has passed structural array checks only. It has
not been visually approved, Fast64-exported as a skinned CJ character, or
tested inside SM64CoopDX on Android. The source IFP is not redistributed.
