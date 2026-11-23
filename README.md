# CJ64

**Carl Johnson character replacement for SM64CoopDX, using the Character Select DynOS actor.**

CJ64 replaces Mario's rendered model while keeping MarioState, movement, collision, camera, actions and physics native.

## Model

The active runtime model is the original Character Select DynOS actor stored in `actors/cj/`:

- `mario_geo.bin`: normal CJ actor, registered inside the mod as `mario_geo`.
- `mario_wingcap_geo.bin`: separate wingcap/Jetpack accessory; it is not attached and has no flight or fuel behaviour yet.
- `[CS] Carl Johnson.zip`: original Character Select actor archive.

**CJ64 0.1.8-alpha returns to this original CS model.** The FBX/Fast64-generated mesh is no longer used for the baseline package. The project owner confirmed that the CS actor appears correctly with native Mario animations. This avoids the FBX skin-weight/export deformation that persisted despite rig corrections.

The scale workflow sets root `GEO_SCALE` to `0.39`, approximately 1.5 times the source actor's previous root scale. Its absolute in-game height has not been measured, so 280 SM64 units is not yet verified.

## GTA animation pipeline

The user-supplied GTA San Andreas `ped.ifp` was converted into 13 candidate clips for the actor's 20 animated-part nodes. Their neutral-pose offsets were calibrated relative to the first frame of `cj64_anim_idle`:

`q_relative = inverse(q_idle_first) * q_current`

The converter preserves the three zeroed root translation channels, clip names, frame counts, channel indices and sample lengths. This is a best-fit retarget, not a one-to-one recreation of GTA's complete ped skeleton.

### Runtime selection correction — 0.1.5-alpha

The earlier controller selected a GTA clip only when its semantic role changed. SM64CoopDX calls `HOOK_MARIO_UPDATE` at the end of a Mario update, after native action code has chosen an animation. If the native animation ID changed while CJ's mapped GTA role stayed the same, the current animation pointer could be replaced by a Mario clip without the controller noticing.

The 0.1.5-alpha controller checks `smlua_anim_util_get_current_animation_name` against the expected GTA clip on each Mario update. It restores the GTA clip only when the current clip differs, then verifies the selected name. It does not call the setter again while the expected GTA clip is already active, avoiding unnecessary frame resets.

The regression test `tests/test_animation_hook.lua` simulates the native animation replacing the GTA fall clip, verifies that CJ64 restores the GTA clip, confirms that an already-active GTA clip is not reset, and checks role changes to idle.

## Current baseline — 0.1.8-alpha\n\nThe install package embeds `actors/cj/mario_geo.bin` directly under `mods/CJ64-CS-Baseline/actors/`. Its filename registers the actor as `mario_geo`. The model is the original CS binary, not the generated FBX mesh. Native Mario animation playback is retained.\n\n## Limits and validation

The CS actor has 20 animated parts rather than GTA's full ped skeleton. Independent finger, toe, breast and belly tracks cannot be reproduced one-to-one. `sprint_civi` is a generic civilian sprint candidate, not confirmed as a CJ-exclusive clip.

The 13 GTA clips are not enabled in the CS baseline. Although the CS actor has the same 20-node traversal order as the Fast64/Mario reference, its local rest-axis basis has not been validated. The baseline therefore deliberately uses native Mario animations until that calibration is completed. A matching node count/order alone is insufficient to enable GTA rotations safely.

The [CJ64 CS baseline workflow](.github/workflows/build-cj64-cs-baseline.yml) runs animation calibration tests, the runtime override regression test, CS animated-part order/landmark validation, Lua syntax checks and DynOS actor structure checks. The [CS animation node inspection workflow](.github/workflows/inspect-cs-animation-node-order.yml) publishes the traversal-order report.
