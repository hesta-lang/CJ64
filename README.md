# CJ64

**Carl Johnson character replacement for SM64CoopDX, using the Character Select DynOS actor.**

CJ64 replaces Mario's rendered model while keeping MarioState, movement, collision, camera, actions and physics native.

## Model

The active source files are stored in `actors/cj/`:

- `mario_geo.bin`: normal CJ actor, registered inside the mod as `mario_geo`.
- `mario_wingcap_geo.bin`: separate wingcap/Jetpack accessory; it is not attached and has no flight or fuel behaviour yet.
- `[CS] Carl Johnson.zip`: original Character Select actor archive.

The model has now been tested in-game by the project owner with SM64CoopDX's native Mario animations and appears normal. Model geometry, scale and orientation are therefore not being changed as part of the current animation correction.

The scale workflow sets root `GEO_SCALE` to `0.39`, approximately 1.5 times the source actor's previous root scale. Its absolute in-game height has not been measured, so 280 SM64 units is not yet verified.

## Animation correction

The custom GTA San Andreas clips previously applied their generated rest-pose rotations directly to the CS model. That caused the body and limbs to inherit large static offsets, including a roughly 90-degree root Z rotation in the idle source.

The compiled CS actor's animated-part traversal order has been inspected against the Fast64/Mario mapping: 20 animated parts and 11 display-list landmarks match. This verifies node order and part identity; it does not mean the CS actor has GTA's full skeleton or every independent source joint.

The new `tools/normalize_cs_animation_tables.py` utility calibrates each node against the first frame of `cj64_anim_idle`:

`q_relative = inverse(q_idle_first) * q_current`

It preserves the three zeroed root translation channels, animation names, frame counts, channel indices and sample lengths. This removes the fixed idle/rest offset while retaining motion relative to the neutral reference.

The private experimental package `0.1.4-alpha` contains 13 calibrated clips and enables them only after the module loads successfully. The derived animation Lua tables and user-supplied `ped.ifp` are not committed to this public repository.

**Runtime status:** the converter and neutral-pose structure pass automated checks, but the GTA clips still need to be tested in-game on Android. This is an experimental best-fit retarget, not a verified final animation release.

## Limits

The CS actor has 20 animated parts rather than GTA's full ped skeleton. Independent finger, toe, breast and belly tracks cannot be reproduced one-to-one with this model. `sprint_civi` is a generic civilian sprint candidate, not confirmed as a CJ-exclusive clip.

## Validation

The [CJ64 CS baseline workflow](.github/workflows/build-cj64-cs-baseline.yml) runs the animation calibration regression tests, checks the CS animated-part traversal and landmarks, validates Lua syntax and the DynOS actor, and builds the native-animation baseline package. A green workflow proves these structural checks; it does not replace the Android animation test.

The [CS animation node inspection workflow](.github/workflows/inspect-cs-animation-node-order.yml) also publishes the traversal-order report.
