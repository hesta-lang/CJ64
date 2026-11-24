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

## Body-root alignment: 0.2.10-alpha

The 0.2.9 runtime made the limbs animate correctly, but the complete CJ actor still appeared laid down. The root cause is the distinction between GTA's source skeleton root and the Body root orientation expected by the compiled Character Select actor.

The direct GTA table includes GTA's own Normal/root orientation. That is not a safe replacement for the target actor's model-space root orientation: applying it tilts the whole actor and every child animated part. The game already owns player heading and world movement, so this GTA root orientation must not be transferred to MarioState.

The 0.2.10-alpha pipeline now does the following:

1. Rebuilds the direct GTA table and validates the 13 clips, XYZ channel order, frame counts and value/index bounds.
2. Loads the known-good native CS/Mario \`anim_00\` frame-zero reference and reads only the Body node's rotation: XYZ \`[0000, 3FFF, 0000]\`.
3. Replaces only Body X/Y/Z on every frame of all 13 clips with those fixed values.
4. Preserves root translation as zero and leaves all channel-index entries untouched.
5. Verifies that all 57 rotation channels belonging to the other 19 animated parts match the pre-correction table exactly in every clip.
6. Keeps the original CS actor binary and all existing animation role/action mappings unchanged.

This does not apply the full Mario idle pose to CJ's limbs. The GTA limb animation samples remain as in 0.2.9; only the actor-wide Body root orientation is aligned to the known-good CS pose. The one-axis Y reference is the same physical rotation in the archived XYZ and ZXY angle order descriptions because X and Z are zero.

The root correction is strongly isolated and regression-tested. It still requires Android visual validation, because automated validation cannot inspect the final rendered geometry, local mesh axes or joint seams.

## Runtime animation mapping

\`character.lua\` maps SM64CoopDX actions and movement speed to the custom roles: idle, walk start/walk, run, sprint candidate, run stop, jump start/air/land, fall/air/land and swim tread. It reasserts a GTA clip if a native Mario animation replaces it. It does not change MarioState, physics, collision, camera or player/world translation.

## Mesh and texture limitations

The current CS archive contains compiled DynOS binaries and does not include editable \`model.inc.c\`, \`geo.inc.c\` or animation source. The separate GTA PNG files in \`assets/gta_sa/original/\` therefore remain source assets; they are not automatically applied to the compiled CS actor. The animation preview keeps the known-working actor binary and its embedded textures unchanged.

## Skeleton limits and in-game validation

The CS actor has 20 animated parts, not the full GTA pedestrian skeleton. Finger, toe, jaw, brow, belly and breast tracks cannot move independently. Exact GTA skeleton parity would require a rebuilt actor and corresponding weighted geometry.

CI can validate the XYZ channel path, Body-only correction, unchanged limb samples, clip tables, root translation, node traversal and the original actor hash. It cannot render SM64CoopDX. The Android test should check idle, walking, running, sprinting, jump launch/air/landing, falling/landing and swimming, including the actor's upright posture, limb seams and foot contact.
