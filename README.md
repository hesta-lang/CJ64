# CJ64

**Carl Johnson character replacement for SM64CoopDX, using the original pre-rigged Character Select actor and adapted GTA San Andreas animations.**

CJ64 replaces Mario's rendered model only. SM64CoopDX continues to own MarioState, movement, collision, camera, player heading, actions and physics.

## Runtime model

The runtime actor remains the original Character Select DynOS model:

- actors/cj/mario_geo.bin: main CJ actor, registered as mario_geo.
- actors/cj/mario_wingcap_geo.bin: separate wing-cap/jetpack accessory; not yet attached.
- actors/cj/[CS] Carl Johnson.zip: original Character Select archive.

The experimental FBX/Fast64 actor is not used by the current runtime package. The packaged actor is checked against the known working CS binary SHA-256:
1e85ef10af95a94d14cf014589811e74adeb437c4e9439eb88d1d3b87b4d0ce4.

## GTA San Andreas animation preview — 0.2.8-alpha

The 0.2.8-alpha preview selects 13 player-movement clips from the supplied GTA SA ped.ifp, sampled at 30 FPS and mapped to the CS actor's 20 animated parts:

| GTA SA clip | CJ64 role |
|---|---|
| IDLE_stance | Idle |
| WALK_start, WALK_player | Walk start, walk |
| run_player, sprint_civi, Run_stop | Run, sprint candidate, run stop |
| JUMP_launch, JUMP_glide, JUMP_land | Jump start, air, landing |
| FALL_fall, FALL_glide, FALL_land | Falling, air, landing |
| Swim_Tread | Swimming idle |

**Animation correction in 0.2.8-alpha:** the archived direct-GTA table stores rotations as XYZ Euler values, but SM64 animated parts interpret their X/Y/Z channels with the engine's Z-X-Y matrix order. Writing those values without conversion changes the actual rotation and can twist or lay the actor sideways. The new build converts each source Euler triplet to a quaternion, then emits equivalent SM64 ZXY channels. It preserves the original GTA IDLE_stance frame-zero pose and does not compose a Mario anim_00 or anim_C5 pose over it.

The build checks all 13 animation tables, 20 destination nodes, fixed-zero root translation, channel ranges, Lua syntax and the reconstructed GTA idle pose against tools/gta_idle_source_pose.json. Quantization and pose comparison are mathematical checks; they do not establish that every joint axis matches the compiled CS mesh in-game.

## Model and rig limitations

The CS actor has 20 animated parts, not GTA SA's full pedestrian skeleton. Finger, toe, jaw, eyebrow, belly and breast joints cannot move independently. The retarget therefore reproduces the main body motion as closely as this rig permits; exact GTA skeleton parity would require an editable mesh/rig with additional deform bones.

The four PNG files under assets/gta_sa/original/ are source textures only. They are **not** substituted into the compiled CS actor by the animation package. The original CS archive contains compiled DynOS binaries and does not provide editable model.inc.c or geo.inc.c sources. The runtime model and its embedded materials remain unchanged to avoid replacing the known-working CS actor with the experimental FBX export.

sprint_civi is a generic civilian sprint animation, not confirmed as a CJ-exclusive sprint.

## Install the preview

Use the artifact CJ64-GTA-Animations-Test-0.2.8-alpha.zip from the latest successful **Build CJ64 direct GTA ZXY animation preview** workflow. Extract it into the game's root; it creates:

mods/CJ64-GTA-Animations-Test/

Disable all older CJ64 test folders first. Only one enabled mod may register mario_geo. This is an alpha build and must be visually checked in SM64CoopDX on Android for idle, walking, running, jumping, falling, landing and swimming.

## Build and diagnostics

- .github/workflows/build-cj64-cs-baseline.yml: reconstructs the direct GTA table, converts rotations to SM64 ZXY, validates the unchanged CS actor and packages the install ZIP.
- tools/convert_direct_gta_to_sm64_zxy.py: preserves GTA source quaternions while re-encoding channels for SM64.
- tools/gta_idle_source_pose.json: reference quaternions from GTA IDLE_stance frame zero for the 20 CS animation nodes.
- tools/apply_native_cs_idle_pose.py: retained for historical tests; the 0.2.8 package does not use its Mario idle-pose overlay.
- tools/ifp_reader.py and tools/animation_hierarchy.py: parse and retarget the GTA IFP source clips.
- tools/inspect_cs_animation_node_order.py: verifies the CS actor's 20-node traversal order and selected display-list landmarks.
