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

## GTA San Andreas animation preview — 0.2.9-alpha

The preview uses 13 player-movement clips from the supplied GTA SA ped.ifp, sampled at 30 FPS and mapped to the CS actor's 20 animated parts:

| GTA SA clip | CJ64 role |
|---|---|
| IDLE_stance | Idle |
| WALK_start, WALK_player | Walk start, walk |
| run_player, sprint_civi, Run_stop | Run, sprint candidate, run stop |
| JUMP_launch, JUMP_glide, JUMP_land | Jump start, air, landing |
| FALL_fall, FALL_glide, FALL_land | Falling, air, landing |
| Swim_Tread | Swimming idle |

**Rotation correction in 0.2.9-alpha:** the 0.2.8 preview incorrectly converted XYZ animation channels to ZXY. That order belongs to a different GeoLayout transform path, not the animated-part path that renders Mario's bones. In \`geo_process_animated_part\`, SM64CoopDX passes the animation's three channels to \`mtxf_rotate_xyz_and_translate\`. Fast64 also reads each bone's local matrix as XYZ Euler angles. Reordering the values changed the rotations and caused the actor to lie sideways or appear inverted.

The new preview therefore removes the ZXY conversion entirely. It preserves the direct GTA table's original 16-bit XYZ channel values and index tables byte-for-byte. The tests cross-check the exact C matrix coefficients against the equivalent quaternion matrix, validate the stored GTA idle reference, all 13 clips, channel bounds and zero root translation. No Mario \`anim_00\` or \`anim_C5\` pose is applied as an overlay.

This corrects the known channel-order error; it does **not** prove that every local rest axis in the compiled CS model matches the GTA target rig. The node-order inspector still reports \`rotation_basis_validation: NOT_VALIDATED\`. Android in-game visual validation is required before treating the animation retarget as finished.

## Model and rig limitations

The CS actor has 20 animated parts, not GTA SA's full pedestrian skeleton. Finger, toe, jaw, eyebrow, belly and breast joints cannot move independently. The retarget therefore reproduces the main body motion as closely as this rig permits; exact GTA skeleton parity would require an editable mesh/rig with additional deform bones.

The four PNG files under \`assets/gta_sa/original/\` are source textures only. They are **not** substituted into the compiled CS actor by the animation package. The original CS archive contains compiled DynOS binaries and does not provide editable \`model.inc.c\` or \`geo.inc.c\` sources. The runtime model and its embedded materials remain unchanged to avoid replacing the known-working CS actor with the experimental FBX export.

\`sprint_civi\` is a generic civilian sprint animation, not confirmed as a CJ-exclusive sprint.

## Install the preview

Use the artifact \`CJ64-GTA-Animations-Test-0.2.9-alpha.zip\` from the latest successful **Build CJ64 direct GTA XYZ animation preview** workflow. Extract it into the game's root; it creates:

\`mods/CJ64-GTA-Animations-Test/\`

Disable all older CJ64 test folders first. Only one enabled mod may register \`mario_geo\`. This is an alpha build and must be visually checked in SM64CoopDX on Android for idle, walking, running, jumping, falling, landing and swimming.

## Build and diagnostics

- \`.github/workflows/build-cj64-cs-baseline.yml\`: reconstructs the direct GTA table, preserves its XYZ channels, validates the unchanged CS actor and packages the install ZIP.
- \`tools/convert_direct_gta_to_sm64_xyz.py\`: validates the engine's XYZ rotation matrix and preserves all original animation values and indices.
- \`tools/gta_idle_source_pose.json\`: quaternion reference for GTA \`IDLE_stance\` frame zero across the 20 animation nodes.
- \`tools/apply_native_cs_idle_pose.py\`: legacy ZXY candidate helper; not used by 0.2.9 and must not be used for GEO_ANIMATED_PART rotations.
- \`tools/inspect_cs_animation_node_order.py\`: verifies the CS actor's 20-node traversal order and selected display-list landmarks; it does not validate all mesh-local rest axes.
