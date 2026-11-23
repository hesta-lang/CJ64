# CJ64

**Carl Johnson replacement for SM64CoopDX, using the original Character Select DynOS actor and GTA San Andreas movement animations.**

CJ64 replaces Mario's rendered character while keeping SM64CoopDX in charge of MarioState, movement, collision, camera, player heading, actions and physics.

## Model

The runtime model is the original pre-rigged Character Select actor in `actors/cj/`:

- `mario_geo.bin`: normal CJ actor, registered as `mario_geo`.
- `mario_wingcap_geo.bin`: separate jetpack/wing-cap accessory; not attached to CJ yet.
- `[CS] Carl Johnson.zip`: original Character Select source archive.

The FBX/Fast64 experimental actor is not used in the runtime package. The CS model has already been confirmed working in-game with native Mario animations.

## GTA San Andreas animations — 0.2.0-alpha

The preview package adds 13 clips from the user-supplied GTA SA `ped.ifp`, sampled at 30 FPS and retargeted to the 20 animated parts of the CS actor:

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

The generated table contains 5,097 source keyframes, resampled to 30 FPS. Its neutral-pose calibration uses the first frame of `IDLE_stance`. The animation retargeter uses the original Mario template's native parent rest frames because those are the frames used by the working CS actor. It does not use the experimental FBX-transferred rest axes.

### What stays native to SM64CoopDX

GTA root translation and world-heading tracks are excluded. All three position channels remain zero, so the animations do not move CJ independently of the game. SM64CoopDX continues to control movement, collision, camera, actions, and physics.

### Limits

The CS actor has 20 animated parts, not GTA's full ped skeleton. Finger, toe, jaw, brow, belly and breast tracks cannot be reproduced as independent moving parts. This is a best-fit retarget of the main body movement, not an exact 58-bone reconstruction. `sprint_civi` is the generic civilian sprint candidate, not a confirmed CJ-exclusive sprint.

The alpha package passes structural and Lua checks, but the new GTA clips still need in-game visual testing on Android. A green workflow does not prove that every pose looks correct. Test idle, walking, running, sprinting, jumping, falling, landing and swimming.

## Installation

Use the `CJ64-GTA-Animations-Test-0.2.0-alpha.zip` package from the latest successful **Build CJ64 GTA animation preview package** workflow. Extract it into the game's root so it creates `mods/CJ64-GTA-Animations-Test/`.

Disable older CJ64 packages first. Only one mod registering `mario_geo` should be enabled at a time. Do not install the experimental `CJ64-Rigged-Test` FBX package.

## Development and validation

- `.github/workflows/build-cj64-cs-baseline.yml`: reconstructs the compressed animation table, checks all 13 clip names and Lua syntax, then packages the working CS actor with the GTA preview module.
- `.github/workflows/cj-rig-transfer.yml`: inspects and exports the experimental FBX rig. It supplies native Mario rest-frame data for animation retarget calibration, but its exported FBX actor is not the runtime model.
- `tools/ifp_reader.py`: reads ANP3 IFP animation tracks.
- `tools/animation_hierarchy.py`: reconstructs source global pose deltas and solves them against the target actor's parent hierarchy.
- `tools/generate_cj_sm64_animations.py`: generates the 20-part SM64 animation tables.
- `tools/normalize_cs_animation_tables.py`: calibrates generated animation tables against the first idle pose.
