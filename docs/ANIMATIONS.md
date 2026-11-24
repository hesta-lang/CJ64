# CJ original animations: calibration and runtime integration

## Source package

The project owner supplied the original GTA: San Andreas anim/ped.ifp package. It parses as ANP3 package ped, with 294 clips and 1,433,248 bytes. Thirteen selected movement candidates contain 5,097 source keyframes:

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

The node-order tool verifies traversal and 11 display-list landmarks. It does not recover the complete mesh-local bind basis or prove every animation axis visually correct. This remains a key limitation of the compiled CS actor.

## Direct GTA source pose, re-encoded for SM64 ZXY — 0.2.8-alpha

The runtime actor stays the original actors/cj/mario_geo.bin; its SHA-256 is checked byte-for-byte during packaging. The experimental FBX/Fast64 actor is not substituted.

The direct GTA animation archive under tools/animations/cj64_gta_direct_source.xz.b64.part-* contains the original GTA IDLE_stance pose, not neutral-relative motion deltas. Earlier direct-table previews wrote XYZ-serialized Euler values straight into SM64 animation channels. That was incorrect because SM64's animated-part matrix applies rotations in Z-X-Y order. The stored values therefore represented different rotations once interpreted by the engine.

The 0.2.8-alpha converter, tools/convert_direct_gta_to_sm64_zxy.py, now:

1. Decodes every source XYZ triplet to a quaternion.
2. Decomposes that same quaternion using SM64's ZXY convention.
3. Chooses equivalent Euler solutions near the preceding frame to avoid unnecessary 180-degree representation flips.
4. Preserves the 13 clip registrations, sample counts and channel index tables.
5. Keeps all three root translation channels fixed at zero, leaving player movement and world heading to SM64CoopDX.
6. Checks that the converted first frame of IDLE_stance matches the 20 quaternion references in tools/gta_idle_source_pose.json within 0.02 degrees.

Unlike the 0.2.6/0.2.7 pipeline, this candidate does not compose GTA motion over Mario's anim_00 pose. The mathematical check verifies that the quaternion rotations survive channel-order conversion. It does not prove that the compiled CS mesh has the same rest axes as the GTA source rig. Android visual validation is still required before treating the animations as fixed.

## Runtime animation mapping

character.lua maps SM64CoopDX actions and movement speed to the custom roles: idle, walk start/walk, run, sprint candidate, run stop, jump start/air/land, fall/air/land and swim tread. It reasserts a GTA clip if a native Mario animation replaces it. It does not change MarioState, physics, collision, camera or player/world translation.

## Mesh and texture limitations

The current CS archive contains compiled DynOS binaries and does not include editable model.inc.c, geo.inc.c or animation source. The separate GTA PNG files in assets/gta_sa/original/ therefore remain source assets; they are not automatically applied to the compiled CS actor. The 0.2.8 animation build intentionally keeps the known-working actor binary and its embedded textures unchanged. Changing the mesh or materials requires an editable source/export route that preserves the CS 20-node runtime layout; replacing it with the unvalidated FBX export is not an acceptable shortcut.

## Limits and in-game validation

The CS actor has 20 animated parts, not the full GTA pedestrian skeleton. Finger, toe, jaw, brow, belly and breast tracks cannot be animated independently. Exact GTA skeleton parity would require a rebuilt actor and corresponding weighted geometry.

The validation workflow checks Lua syntax, the 13 animation registrations, source-pose quaternion round trips, channel ranges, root translation, node traversal and the exact CS actor binary. It does not run SM64CoopDX or inspect rendered poses. The Android test must check idle, walking, running, sprinting, jump launch/air/landing, falling/landing and swimming, including limb seams and feet contacting the ground.
