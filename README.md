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

## GTA San Andreas animation preview — 0.2.11-alpha

The preview uses 13 player-movement clips from the supplied GTA SA ped.ifp, sampled at 30 FPS and mapped to the CS actor's 20 animated parts:

| GTA SA clip | CJ64 role |
|---|---|
| IDLE_stance | Idle |
| WALK_start, WALK_player | Walk start, walk |
| run_player, sprint_civi, Run_stop | Run, sprint candidate, run stop |
| JUMP_launch, JUMP_glide, JUMP_land | Jump start, air, landing |
| FALL_fall, FALL_glide, FALL_land | Falling, air, landing |
| Swim_Tread | Swimming idle |

### Animation basis and native CS pose composition

The 0.2.8 preview used the wrong rotation convention. The current conversion verifies the XYZ path used by `geo_process_animated_part` through `mtxf_rotate_xyz_and_translate`.

The 0.2.10 correction was insufficient: it replaced only the Body root while leaving the 19 child nodes with absolute GTA rotations. Those values are not neutral-relative motion for the CS rig, so a Body-only change could not correct the complete pose.

The 0.2.11-alpha pipeline now:
1. Validates and preserves the original source XYZ channels.
2. Converts each node's GTA rotations to motion deltas relative to the first frame of `IDLE_stance`.
3. Composes those deltas over all 20 frame-zero joint rotations from the native CS/Mario `anim_00` pose, using the engine XYZ convention.
4. Keeps GTA's `Normal`/root rotation out of player/world heading; the Body node remains on the native `anim_00` base orientation.
5. Preserves zero root translations, the original actor binary, and the existing runtime action mapping.

This is an animation-only correction. It does not edit `mario_geo.bin`, the mesh, bones, skeleton hierarchy, textures, `character.lua`, camera, movement, collision or physics. The CS rig has fewer deform joints than GTA's ped skeleton, so the result is still an approximation and must be visually checked in SM64CoopDX on Android.

## Model and rig limitations

The CS actor has 20 animated parts, not GTA SA's full pedestrian skeleton. Finger, toe, jaw, eyebrow, belly and breast joints cannot move independently. The retarget therefore reproduces the main body motion as closely as this rig permits; exact GTA skeleton parity would require an editable mesh/rig with additional deform bones.

The four PNG files under \`assets/gta_sa/original/\` are source textures only. They are **not** substituted into the compiled CS actor by the animation package. The original CS archive contains compiled DynOS binaries and does not provide editable \`model.inc.c\` or \`geo.inc.c\` sources. The runtime model and its embedded materials remain unchanged to avoid replacing the known-working CS actor with the experimental FBX export.

\`sprint_civi\` is a generic civilian sprint candidate, not confirmed as a CJ-exclusive sprint.

## Install the preview

Use the artifact \`CJ64-GTA-Animations-Test-0.2.11-alpha.zip\` from the latest successful **Build CJ64 GTA animation preview with native CS anim_00 XYZ pose** workflow. Extract it into the game's root; it creates:

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
