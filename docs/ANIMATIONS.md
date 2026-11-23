# CJ original animations: calibration and runtime integration

## Source package

The project owner supplied the original GTA: San Andreas `anim/ped.ifp` package. It parses as ANP3 package `ped`, with 294 clips and 1,433,248 bytes. Thirteen selected candidates contain 5,097 source keyframes:

- `IDLE_stance`
- `WALK_start`, `WALK_player`
- `run_player`, `sprint_civi`, `Run_stop`
- `JUMP_launch`, `JUMP_glide`, `JUMP_land`
- `FALL_fall`, `FALL_glide`, `FALL_land`
- `Swim_Tread`

`sprint_civi` is a generic civilian sprint candidate, not confirmed as a CJ-exclusive animation. The IFP and derived per-frame Lua output are private working inputs and are not stored in this public repository.

## Verified animated-part mapping

The CS DynOS actor has 20 `GEO_ANIMATED_PART` commands. `tools/inspect_cs_animation_node_order.py` compares their traversal order and 11 display-list landmarks against the Fast64/Mario reference. The order and selected part identities match:

`Body`, `Butt`, `Torso`, `Head`, `Left Arm`, `Left Arm Color`, `Left Forearm`, `Left Hand`, `Right Arm`, `Right Arm Color`, `Right Forearm`, `Right Hand`, `Left Thigh`, `Left Thigh Color`, `Left Leg`, `Left Shoe`, `Right Thigh`, `Right Thigh Color`, `Right Leg`, `Right Shoe`.

The project owner confirmed that the compiled CS model appears normally with native Mario animations. This isolates the deformation issue to the custom animation data/runtime path rather than the base mesh.

## Native CS actor pose anchor — 0.2.1-alpha

The 0.2.0-alpha preview incorrectly treated zero animation channels as the
visible neutral pose. That assumption was false for the working Character
Select actor: its 20 animated parts use the native Mario animation channel
layout, and the model relies on non-zero frame-zero rotations from the Mario
idle pose to stand upright. Omitting those constants left CJ lying on his side.

The correct anchor is frame zero of
`MARIO_ANIM_IDLE_HEAD_CENTER` (`anim_C5`) from the SM64 animation assets.
The source file is
[`assets/anims/anim_C5.inc.c`](https://github.com/n64decomp/sm64/blob/master/assets/anims/anim_C5.inc.c).
Its first Body rotation is `(0x0000, 0x3FFF, 0x0000)`, approximately
`(0°, 89.995°, 0°)`. The Butt and the remaining parts also have non-zero
native frame-zero rotations.

The package build now performs these steps:

1. Generate GTA rotations as local motion deltas, keeping GTA Normal/world
   heading and root translation out of MarioState.
2. Load the 20 native idle-pose quaternions from
   `tools/native_mario_idle_pose.json`.
3. For every animated part and every frame, compose
   `native_idle_local_pose * GTA_local_motion_delta`.
4. Encode the result back into SM64's 16-bit Euler channels and verify that
   the first frame of `cj64_anim_idle` reproduces the native idle pose within
   0.02 degrees.
5. Reconstruct and syntax-check the Lua tables before packaging them with the
   unchanged Character Select `mario_geo.bin`.

The postprocessor is `tools/apply_native_cs_idle_pose.py`. It refuses to
apply the anchor twice. The regression tests check the 90-degree Body anchor,
all 20 node entries, delta composition and the zeroed root translation.
This is a pose calibration, not a mesh or scale change.

The pose anchor corrects the missing native base pose that caused the 0.2.0
model to lie sideways. The remaining GTA-to-CS joint motion still needs visual
checking in Android; successful CI alone does not establish that every limb
follows the original GTA animation perfectly.

## Neutral-pose calibration

The original animation arrays carried static reference/rest rotations into the custom animation channels. In the first frame of `cj64_anim_idle`, the Body channel contained approximately 90 degrees around Z and the Butt channel contained large rotations. Those values are static pose offsets, not useful movement instructions when applied as absolute body rotations.

`tools/normalize_cs_animation_tables.py` now:

1. Parses every `smlua_anim_util_register_animation` block and rejects duplicate names, unexpected channel counts, invalid offsets, missing samples and non-zero root translation.
2. Reads the first XYZ rotation sample for each of the 20 target nodes in `cj64_anim_idle`.
3. Computes each sample relative to that node's idle reference quaternion:
   `q_relative = inverse(q_idle_first) * q_current`.
4. Converts the relative rotations back to 16-bit Euler channels, unwraps angular discontinuities and preserves channel index tables and sample lengths.
5. Emits a report that marks visual and in-game validation as incomplete.

Each clip has 63 channels: three fixed-zero root translation channels plus three rotation channels for each of 20 animated parts. The three translation channels remain zero so MarioState continues to own player position and world movement.

The first idle frame is identity across all 20 nodes, with a maximum numerical residual below (10^{-15}) radians in the private calibration report. All 13 clips retain their original frame counts and 126 index entries per clip.

## Runtime override detection — 0.1.5-alpha

The 0.1.4 controller selected a GTA clip only when the semantic role changed. SM64CoopDX invokes `HOOK_MARIO_UPDATE` at the end of a Mario update, after native action code has selected an animation. When the native animation ID changes but CJ64's mapped GTA role remains the same, native code can replace the current animation pointer. The controller then sees no role change and may leave Mario's clip active.

The 0.1.5 controller reads `smlua_anim_util_get_current_animation_name` on each `HOOK_MARIO_UPDATE`. It compares the current clip with the name registered for the current GTA role. It calls `smlua_anim_util_set_animation` only when those names differ, and verifies that the requested custom clip became current. When the expected GTA clip is already active, it does not call the setter again, so it does not unnecessarily restart the animation.

`tests/test_animation_hook.lua` is an executable regression test that:
- selects the GTA fall clip on the first update;
- simulates native SM64 replacing it while the mapped role remains `fall`;
- verifies that CJ64 restores the GTA clip;
- verifies that an already-active custom clip is not reset;
- verifies that changing to idle selects the GTA idle clip.

The test proves the controller's override-detection behavior with a simulated native override. It does not prove the converted poses look correct on CJ in the game.

## Limits and in-game validation

The CS actor has only 20 animated parts rather than GTA's full ped skeleton. Individual finger, toe, breast and belly tracks cannot be animated independently. Exact one-to-one GTA skeleton parity would require rebuilding the model with a larger skeleton and corresponding geometry weights.

The calibrated clips remain experimental until tested in SM64CoopDX on Android. The important checks are idle, walk start/walk, run, sprint candidate, run stop, jump launch/air/land, fall/land and swimming. If a particular clip deforms CJ, the next correction should target that clip/node from the observed pose rather than applying another global model rotation.
