# CJ64 animation pipeline and calibration

## Source package

The project owner supplied the original GTA: San Andreas anim/ped.ifp package. It parses as an ANP3 package named ped, with 294 clips and 1,433,248 bytes. Thirteen selected movement candidates contain 5,097 source keyframes:

- IDLE_stance
- WALK_start, WALK_player
- run_player, sprint_civi, Run_stop
- JUMP_launch, JUMP_glide, JUMP_land
- FALL_fall, FALL_glide, FALL_land
- Swim_Tread

sprint_civi is a generic civilian sprint candidate, not confirmed as a CJ-exclusive animation.

## Destination rig

The installed Character Select DynOS actor has 20 GEO_ANIMATED_PART commands, ordered as:

Body, Butt, Torso, Head, Left Arm, Left Arm Color, Left Forearm, Left Hand, Right Arm, Right Arm Color, Right Forearm, Right Hand, Left Thigh, Left Thigh Color, Left Leg, Left Shoe, Right Thigh, Right Thigh Color, Right Leg, Right Shoe.

The node-order tool verifies traversal and 11 display-list landmarks. It does not recover the complete mesh-local bind basis or prove every animation axis visually correct. The report intentionally continues to say \`rotation_basis_validation: NOT_VALIDATED\`.

## Correct animation channel convention — 0.2.9-alpha

The 0.2.8 preview introduced the wrong conversion. It treated the rotation channels consumed by an animated part as ZXY. The source code shows the actual call path:

- \`geo_process_animated_part\` in [SM64CoopDX rendering_graph_node.c](https://github.com/coop-deluxe/sm64coopdx/blob/main/src/game/rendering_graph_node.c) calls \`mtxf_rotate_xyz_and_translate(matrix, translation, rotation)\`.
- [SM64CoopDX math_util.c](https://github.com/coop-deluxe/sm64coopdx/blob/main/src/engine/math_util.c) documents and implements that function as X, then Y, then Z.
- Fast64 samples each animation bone in local space and reads \`local_matrix.to_euler()\`, then converts the resulting XYZ angles to signed 16-bit values.

The runtime animation engine reads the three channels of each GEO_ANIMATED_PART as XYZ. It does not use the ZXY conversion added for the rejected 0.2.8 candidate. The previous ZXY converter could make a correctly sampled source pose render with a different orientation, including lying sideways or upside down.

The 0.2.9-alpha pipeline now:

1. Reconstructs the original direct GTA source table from its archived compressed parts.
2. Verifies the 13 expected clips, 20 target nodes, channel index bounds, frame counts and fixed-zero root translation.
3. Checks that the engine's \`mtxf_rotate_xyz_and_translate\` matrix matches the transpose of the equivalent XYZ quaternion matrix for mixed-axis rotations.
4. Checks the original \`IDLE_stance\` frame-zero channels against the stored 20-node GTA source-pose reference.
5. Preserves every source 16-bit value and index entry; no quaternion decomposition, Euler re-encoding or ZXY conversion is performed.
6. Keeps the original Character Select actor binary unchanged and verifies its SHA-256 before packaging.

The mathematical checks establish the channel order and preserve the source rotations. They do **not** establish that all rest axes in the compiled CS mesh have been recovered correctly. The 20-node traversal and 11 display-list landmarks are structural evidence only. Android visual testing remains necessary to confirm the rendered joint pose.

## Runtime animation mapping

\`character.lua\` maps SM64CoopDX actions and movement speed to the custom roles: idle, walk start/walk, run, sprint candidate, run stop, jump start/air/land, fall/air/land and swim tread. It reasserts a GTA clip if a native Mario animation replaces it. It does not change MarioState, physics, collision, camera or player/world translation.

## Mesh and texture limitations

The current CS archive contains compiled DynOS binaries and does not include editable \`model.inc.c\`, \`geo.inc.c\` or animation source. The separate GTA PNG files in \`assets/gta_sa/original/\` therefore remain source assets; they are not automatically applied to the compiled CS actor. The animation preview keeps the known-working actor binary and its embedded textures unchanged. Changing the mesh or materials requires an editable source/export route that preserves the CS 20-node runtime layout; replacing it with the unvalidated FBX export is not an acceptable shortcut.

## Skeleton limits and in-game validation

The CS actor has 20 animated parts, not the full GTA pedestrian skeleton. Finger, toe, jaw, brow, belly and breast tracks cannot move independently. Exact GTA skeleton parity would require a rebuilt actor and corresponding weighted geometry.

The validation workflow checks Lua syntax, the 13 animation registrations, source-pose quaternion checks, engine XYZ matrix coefficients, channel ranges, root translation, node traversal and the exact CS actor binary. It does not run SM64CoopDX or inspect rendered poses. The Android test must check idle, walking, running, sprinting, jump launch/air/landing, falling/landing and swimming, including limb seams and feet contacting the ground.
