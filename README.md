# CJ64

**Carl Johnson character replacement for SM64CoopDX, using the original pre-rigged Character Select actor and adapted GTA San Andreas animations.**

CJ64 replaces Mario's rendered model only. SM64CoopDX continues to own MarioState, movement, collision, camera, player heading, actions and physics.

## Runtime model

The runtime actor remains the original Character Select DynOS model:

- \`actors/cj/mario_geo.bin\`: main CJ actor, registered as \`mario_geo\`.
- \`actors/cj/mario_wingcap_geo.bin\`: separate wing-cap/jetpack accessory; not yet attached.
- \`actors/cj/[CS] Carl Johnson.zip\`: original Character Select archive.

The experimental FBX/Fast64 actor is not used by the current runtime package. The packaged actor is checked against the known working CS binary SHA-256:
\`1e85ef10af95a94d14cf014589811e74adeb437c4e9439eb88d1d3b87b4d0ce4\`.

## GTA San Andreas animation preview — 0.2.10-alpha

The preview uses 13 player-movement clips from the supplied GTA SA ped.ifp, sampled at 30 FPS and mapped to the CS actor's 20 animated parts:

| GTA SA clip | CJ64 role |
|---|---|
| IDLE_stance | Idle |
| WALK_start, WALK_player | Walk start, walk |
| run_player, sprint_civi, Run_stop | Run, sprint candidate, run stop |
| JUMP_launch, JUMP_glide, JUMP_land | Jump start, air, landing |
| FALL_fall, FALL_glide, FALL_land | Falling, air, landing |
| Swim_Tread | Swimming idle |

### Rotation channels and upright Body root

The 0.2.8 preview incorrectly converted XYZ animation channels to ZXY. The 0.2.9 preview corrected that by preserving the direct GTA XYZ samples, as consumed by \`geo_process_animated_part\` through \`mtxf_rotate_xyz_and_translate\`.

The remaining posture issue was isolated to the root \`Body\` animated part. The direct GTA table contains GTA's own Normal/root orientation, but this is not the orientation basis of the compiled Character Select actor. Copying that root rotation to the CS actor tilts the complete model, including every child part.

The 0.2.10-alpha pipeline therefore changes only the three rotation channels of the \`Body\` node. It replaces them on every frame with the known-good native CS/Mario \`anim_00\` frame-zero Body orientation: XYZ \`[0000, 3FFF, 0000]\` (approximately 89.9945 degrees around Y). It deliberately does **not** apply the complete Mario idle pose to CJ's limbs.

All root translation channels remain zero. The 19 child animated parts retain their original GTA XYZ samples, frame counts, and channel indices exactly. The regression tests compare those samples before and after the Body correction for all 13 clips.

This is an isolated root calibration based on the known-good CS idle pose; it does not alter the actor mesh, embedded textures, child joints, action mapping, physics, camera, or player/world movement. Android visual validation remains necessary to confirm the model is now upright in the actual game runtime.

## Model and rig limitations

The CS actor has 20 animated parts, not GTA SA's full pedestrian skeleton. Finger, toe, jaw, eyebrow, belly and breast joints cannot move independently. The retarget therefore reproduces the main body motion as closely as this rig permits; exact GTA skeleton parity would require an editable mesh/rig with additional deform bones.

The four PNG files under \`assets/gta_sa/original/\` are source textures only. They are **not** substituted into the compiled CS actor by the animation package. The original CS archive contains compiled DynOS binaries and does not provide editable \`model.inc.c\` or \`geo.inc.c\` sources. The runtime model and its embedded materials remain unchanged to avoid replacing the known-working CS actor with the experimental FBX export.

\`sprint_civi\` is a generic civilian sprint candidate, not confirmed as a CJ-exclusive sprint.

## Install the preview

Use the artifact \`CJ64-GTA-Animations-Test-0.2.10-alpha.zip\` from the latest successful **Build CJ64 GTA animation preview with CS Body root alignment** workflow. Extract it into the game's root; it creates:

\`mods/CJ64-GTA-Animations-Test/\`

Disable all older CJ64 test folders first. Only one enabled mod may register \`mario_geo\`. This alpha must be visually checked in SM64CoopDX on Android for idle, walking, running, jumping, falling, landing and swimming.

## Build and diagnostics

- \`.github/workflows/build-cj64-cs-baseline.yml\`: reconstructs the direct GTA table, preserves its XYZ channels, aligns only the CS Body root, verifies all 19 child tracks are unchanged, validates the original actor binary and packages the install ZIP.
- \`tools/convert_direct_gta_to_sm64_xyz.py\`: validates the engine's XYZ rotation matrix and preserves all original animation values and indices.
- \`tools/apply_cs_body_root_orientation.py\`: replaces only Body XYZ with the native CS \`anim_00\` frame-zero orientation.
- \`tools/native_mario_idle_pose.json\`: reference for the known-good native CS/Mario idle pose; only its Body entry is used for this correction.
- \`tools/gta_idle_source_pose.json\`: quaternion reference for GTA \`IDLE_stance\` frame zero across the 20 animation nodes.
- \`tools/apply_native_cs_idle_pose.py\`: legacy ZXY candidate helper; not used by 0.2.10.
- \`tools/inspect_cs_animation_node_order.py\`: verifies the CS actor's 20-node traversal order and selected display-list landmarks; it does not validate all mesh-local rest axes.
