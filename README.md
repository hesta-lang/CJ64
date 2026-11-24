# CJ64

**Carl Johnson replacement for SM64CoopDX, using the original Character Select DynOS actor and GTA San Andreas movement animations.**

CJ64 is a standalone SM64CoopDX Lua/DynOS mod. Install it separately in the game's `mods/` directory; it is not embedded in or rebuilt into the Android APK. The APK supplies the game engine, while this repository supplies the independent CJ64 mod package.

CJ64 replaces Mario's rendered character while keeping SM64CoopDX in charge of MarioState, movement, collision, camera, player heading, actions and physics.

## Model

The runtime model is the original pre-rigged Character Select actor in `actors/cj/`:

- `mario_geo.bin`: normal CJ actor, registered as `mario_geo`.
- `mario_wingcap_geo.bin`: separate jetpack/wing-cap accessory; not attached to CJ yet.
- `[CS] Carl Johnson.zip`: original Character Select source archive.

The FBX/Fast64 experimental actor is not used in the runtime package. Keep the original Character Select actor; do not replace it with the experimental export.

## GTA San Andreas animations — 0.2.7-alpha

The standalone package contains 13 clips from the supplied GTA SA `ped.ifp`, sampled at 30 FPS and retargeted to the actor's 20 animated parts:

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

The target contains 20 animated nodes, not GTA's full ped skeleton.

### Native idle pose anchor

The current 0.2.7-alpha build composes GTA local-motion deltas on frame zero of SM64's default `MARIO_ANIM_IDLE` (`anim_00`) pose. The final channels are encoded using SM64's Z-X-Y matrix order. The special head-centered `anim_C5` pose is not used.

The original Character Select `mario_geo.bin` remains unchanged and is copied byte-for-byte into the package.

### What stays native to SM64CoopDX

GTA root translation and world-heading tracks are excluded. All three position channels remain zero, so the animations do not move CJ independently of the game. SM64CoopDX continues to control MarioState, movement, collision, camera, player heading, actions and physics.

### Limits

The CS actor has 20 animated parts, not GTA's full ped skeleton. Finger, toe, jaw, brow, belly and breast tracks cannot be reproduced as independent moving parts. This is a best-fit retarget of the main body motion, not an exact reconstruction of the full GTA ped rig. `sprint_civi` is the generic civilian sprint candidate, not a confirmed CJ-exclusive sprint.

CI validates Lua syntax, animation tables, actor integrity and ZIP contents. A successful workflow does not prove in-game pose quality; walk, run, sprint, jump, fall, landing and swimming still require testing on the target Android APK.

## Installation

1. Build or install the Android APK from [sm64coopdx-craft, branch gta-native-assets](https://github.com/hesta-lang/sm64coopdx-craft/tree/gta-native-assets).
2. Download the `CJ64-GTA-Animations-Test-0.2.7-alpha` artifact from the latest successful **Build CJ64 GTA animation preview package** workflow in this repository.
3. Extract the ZIP into the game's root directory. It creates:
   `mods/CJ64-GTA-Animations-Test/`
4. Disable every older CJ64 package that also registers `mario_geo`. Keep only this package enabled.

Do not install the experimental `CJ64-Rigged-Test` FBX package, and do not place this package inside the APK or under `dynos/packs/`.

## Development and validation

- `.github/workflows/build-cj64-cs-baseline.yml`: reconstructs the compressed GTA module, applies the default idle-pose anchor, checks 13 clips/63 channels and packages the unchanged CS actor.
- `tools/native_mario_idle_pose.json`: frame-zero local rotations for all 20 nodes from native SM64 `anim_00`.
- `tools/apply_native_cs_idle_pose.py`: composes GTA local-motion deltas onto the native idle pose before packaging.
- `tools/ifp_reader.py`: reads ANP3 IFP animation tracks.
- `tools/animation_hierarchy.py`: reconstructs GTA source global pose deltas and retargets them to the 20-part animation layout.
- `tools/generate_cj_sm64_animations.py`: generates intermediate SM64 local-motion delta tables.
- `tools/inspect_cs_animation_node_order.py`: verifies the 20-node CS traversal order and selected display-list landmarks.
