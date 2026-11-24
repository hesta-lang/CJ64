# CJ64 animation pipeline and root-pose calibration

## Source package

The project owner supplied the original GTA: San Andreas anim/ped.ifp package. It parses as an ANP3 package named ped, with 294 clips and 1,433,248 bytes. Thirteen selected movement candidates contain 5,097 source keyframes:

- IDLE_stance
- WALK_start, WALK_player
- run_player, sprint_civi, Run_stop
- JUMP_launch, JUMP_glide, JUMP_land
- FALL_fall, FALL_glide, FALL_land
- Swim_Tread

sprint_civi is a generic civilian sprint candidate, not confirmed as a CJ-exclusive sprint.

## Destination rig

The installed Character Select DynOS actor has 20 GEO_ANIMATED_PART commands, ordered as:

Body, Butt, Torso, Head, Left Arm, Left Arm Color, Left Forearm, Left Hand, Right Arm, Right Arm Color, Right Forearm, Right Hand, Left Thigh, Left Thigh Color, Left Leg, Left Shoe, Right Thigh, Right Thigh Color, Right Leg, Right Shoe.

The original CS actor binary is kept byte-for-byte intact. The node-order tool verifies traversal and 11 display-list landmarks; it does not recover every mesh-local bind axis.

## Rotation channels: XYZ

The 0.2.8 preview incorrectly treated animated-part channels as ZXY. The source code shows the actual call path:

- \`geo_process_animated_part\` in [SM64CoopDX rendering_graph_node.c](https://github.com/coop-deluxe/sm64coopdx/blob/main/src/game/rendering_graph_node.c) calls \`mtxf_rotate_xyz_and_translate(matrix, translation, rotation)\`.
- [SM64CoopDX math_util.c](https://github.com/coop-deluxe/sm64coopdx/blob/main/src/engine/math_util.c) documents and implements that function as X, then Y, then Z.
- Fast64 samples each animation bone in local space and reads \`local_matrix.to_euler()\`, then converts the resulting XYZ angles to signed 16-bit values.

The 0.2.9-alpha pipeline restores these original XYZ channel values without reordering them.

## All-joint native pose composition: 0.2.11-alpha

The Body-only adjustment in 0.2.10 was not sufficient. It changed the root rotation but retained the 19 articulated nodes' absolute GTA source rotations. Those values describe GTA's source pose, not motion deltas in the destination CS animation channels.

The active animation-only pipeline is now:

1. Reconstruct the original direct GTA XYZ channel table and verify the 13 clip names, sample counts, index bounds and fixed-zero player translations.
2. Normalize every node's local rotations as `inverse(IDLE_stance frame 0) * current frame`, producing neutral-relative motion deltas.
3. Read the raw frame-zero XYZ channels from native SM64 `MARIO_ANIM_IDLE (anim_00)`.
4. Compose each of the 19 articulated nodes as `native anim_00 local pose * GTA local motion delta`, and encode the result using the engine's `mtxf_rotate_xyz_and_translate` convention.
5. Keep Body fixed at its native `anim_00` XYZ orientation. The GTA `Normal` track is not Mario's world root; SM64CoopDX continues to own player heading, translation, movement, collision, camera and physics.
6. Verify the idle first frame reconstructs all 20 native joint rotations, all root translations remain zero, and animation index tables are unchanged.

This changes only animation channel samples. It does not modify the CS DynOS binary, mesh, textures, bone definitions, rig, GeoLayout hierarchy or runtime action mapping. Android visual validation is still required; this rig has 20 animated parts and cannot reproduce GTA's independent finger, toe, jaw, eyebrow, belly or breast tracks.

## Runtime animation mapping

\`character.lua\` maps SM64CoopDX actions and movement speed to the custom roles: idle, walk start/walk, run, sprint candidate, run stop, jump start/air/land, fall/air/land and swim tread. It reasserts a GTA clip if a native Mario animation replaces it. It does not change MarioState, physics, collision, camera or player/world translation.

## Mesh and texture limitations

The current CS archive contains compiled DynOS binaries and does not include editable \`model.inc.c\`, \`geo.inc.c\` or animation source. The separate GTA PNG files in \`assets/gta_sa/original/\` therefore remain source assets; they are not automatically applied to the compiled CS actor. The animation preview keeps the known-working actor binary and its embedded textures unchanged.

## Skeleton limits and in-game validation

The CS actor has 20 animated parts, not the full GTA pedestrian skeleton. Finger, toe, jaw, brow, belly and breast tracks cannot move independently. Exact GTA skeleton parity would require a rebuilt actor and corresponding weighted geometry.

CI can validate the XYZ channel path, Body-only correction, unchanged limb samples, clip tables, root translation, node traversal and the original actor hash. It cannot render SM64CoopDX. The Android test should check idle, walking, running, sprinting, jump launch/air/landing, falling/landing and swimming, including the actor's upright posture, limb seams and foot contact.
