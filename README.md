# CJ64

**Carl Johnson replacement for SM64CoopDX, using the original Character Select DynOS actor and GTA San Andreas movement animations.**

CJ64 replaces Mario's rendered character while keeping SM64CoopDX in charge of MarioState, movement, collision, camera, player heading, actions and physics.

## Model

The runtime model is the original pre-rigged Character Select actor in `actors/cj/`:

- `mario_geo.bin`: normal CJ actor, registered as `mario_geo`.
- `mario_wingcap_geo.bin`: separate jetpack/wing-cap accessory; not attached to CJ yet.
- `[CS] Carl Johnson.zip`: original Character Select source archive.

The FBX/Fast64 experimental actor is not used in the runtime package. The CS model was confirmed working in-game with native Mario animations.

## GTA San Andreas animations — 0.2.1-alpha

The package contains 13 clips from the user-supplied GTA SA `ped.ifp`, sampled at 30 FPS and retargeted to the actor's 20 animated parts:

| GTA SA source clip | CJ64 role |
|---|---|
| `IDLE_stance` | Idle |
| `WALK_start` | Walk start |
| `WALK_player` | Walk |
| `run_player` | Run |
| `sprint_civi` | Sprint candidate |
| `Run_stop` | Run stop |
| `JUMP_launch` | Jump start |
| `JUMP_glide` | Jump in air |
| `JUMP_land` | Jump landing |
| `FALL_fall` | Falling |
| `FALL_glide` | Falling in air |
| `FALL_land` | Fall landing |
| `Swim_Tread` | Swimming idle |

The converted table carries 5,097 original source keyframes, resampled at 30 FPS. The target contains 20 animated nodes, not GTA's full ped skeleton.

### Native idle pose anchor

The 0.2.0 preview set every idle rotation channel to zero. That was not a valid neutral pose for the CS actor and caused CJ to lie sideways.

The 0.2.1 build restores frame zero of native SM64 `MARIO_ANIM_IDLE_HEAD_CENTER` (`anim_C5`) as the base pose for all 20 nodes. For each sample, it composes:

`native Mario idle local pose × GTA local motion delta`

This includes the approximately 90-degree Y rotation on the Body node and the other non-zero native part rotations. The original Character Select `mario_geo.bin` remains unchanged. The new build checks that the first frame of `cj64_anim_idle` matches the native pose within 0.02 degrees.

### What stays native to SM64CoopDX

GTA root translation and world-heading tracks are excluded. All three position channels remain zero, so the animations do not move CJ independently of the game. SM64CoopDX continues to control movement, collision, camera, actions and physics.

### Limits

The CS actor has 20 animated parts, not GTA's full ped skeleton. Finger, toe, jaw, brow, belly and breast tracks cannot be reproduced as independent moving parts. This is a best-fit retarget of the main body motion, not an exact reconstruction of the full GTA ped rig. `sprint_civi` is the generic civilian sprint candidate, not a confirmed CJ-exclusive sprint.

The native pose anchor fixes the missing neutral pose that caused the sideways model in 0.2.0. The remaining GTA limb motion still needs in-game visual testing on Android. A green workflow does not prove that every pose is visually identical to GTA.

## Installation

Use the `CJ64-GTA-Animations-Test-0.2.1-alpha.zip` artifact from the latest successful **Build CJ64 GTA animation preview package** workflow. Extract it into the game's root so it creates `mods/CJ64-GTA-Animations-Test/`.

Disable older CJ64 packages first. Only one mod registering `mario_geo` should be enabled at a time. Do not install the experimental `CJ64-Rigged-Test` FBX package.

## Development and validation

- `.github/workflows/build-cj64-cs-baseline.yml`: reconstructs the compressed GTA module, applies the native idle-pose anchor, checks 13 clips/63 channels and packages the unchanged CS actor.
- `tools/native_mario_idle_pose.json`: frame-zero local rotations for all 20 nodes from native SM64 `anim_C5`.
- `tools/apply_native_cs_idle_pose.py`: composes GTA local-motion deltas onto the native idle pose before packaging.
- `tools/ifp_reader.py`: reads ANP3 IFP animation tracks.
- `tools/animation_hierarchy.py`: reconstructs GTA source global pose deltas and retargets them to the 20-part animation layout.
- `tools/generate_cj_sm64_animations.py`: generates intermediate SM64 local-motion delta tables.
- `tools/inspect_cs_animation_node_order.py`: verifies the 20-node CS traversal order and selected display-list landmarks.
