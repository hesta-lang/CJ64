# CJ original animations: calibration and integration status

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

The owner has confirmed that the compiled CS model appears normally in-game with native Mario animations. This isolates the current defect to the custom animation data/conversion path; the model's mesh and scale are not modified by the calibration.

## Cause of the previous animation failure

The original generated table carried static reference/rest rotations into the custom animation arrays. In the first frame of the original `cj64_anim_idle` table, the `Body` channel contained approximately 90 degrees around Z and the `Butt` channel contained large rotations. These are rest-space offsets, not useful movement instructions to apply as absolute character pose rotations.

A matching number of nodes or a matching traversal order does not prove the coordinate basis is identical. The prior table could therefore move the model away from its valid neutral pose even though it rendered correctly with native Mario animations.

## Neutral-pose calibration

`tools/normalize_cs_animation_tables.py` now:

1. Parses every `smlua_anim_util_register_animation` block and rejects duplicate names, unexpected channel counts, invalid offsets, missing samples and non-zero root translation.
2. Reads the first XYZ rotation sample for each of the 20 target nodes in `cj64_anim_idle`.
3. Computes each sample relative to that node's idle reference quaternion:
   `q_relative = inverse(q_idle_first) * q_current`.
4. Converts the relative rotations back to 16-bit Euler channels, unwraps angular discontinuities and preserves the channel index tables and all sample lengths.
5. Emits a report that clearly marks visual and in-game validation as incomplete.

Each clip has 63 channels: three fixed-zero root translation channels plus three rotation channels for each of 20 animated parts. The three translation channels remain zero so MarioState continues to own player position and world movement.

The first idle frame is now identity across all 20 nodes, with a maximum numerical residual below (10^{-15}) radians in the private calibration report. All 13 clips retain their original frame counts and 126 index entries per clip.

## Current experimental package

The private `0.1.4-alpha` test package includes the calibrated table and enables it only after successful module loading. If the module fails to load, the main script leaves native Mario animations enabled as a fallback.

Automated tests cover neutral-pose removal, motion preservation, idempotency, preservation of translation channels, duplicate registration rejection and invalid channel-index rejection. These tests validate the converter's data handling; they cannot show how the animation looks on the actual character in the game.

## Limitations and next validation

The CS actor has only 20 animated parts rather than GTA's full ped skeleton. Individual finger, toe, breast and belly tracks cannot be animated independently, so exact one-to-one GTA skeleton parity is not possible without rebuilding the model with a larger skeleton and matching geometry.

The calibrated clips remain experimental until tested in SM64CoopDX on Android. The important in-game checks are idle, walk start/walk, run, sprint candidate, run stop, jump launch/air/land, fall/land and swimming. If one clip deforms the model, the next correction should target that clip/node using the observed pose rather than applying another global model rotation.
