# CJ64

**Carl Johnson character replacement for SM64CoopDX, using the original Character Select DynOS actor.**

CJ64 replaces only Mario's rendered model. MarioState, the existing marioObj, movement, collision, camera, actions and physics remain native.

## Current model

The active actor files are stored in `actors/cj/`:

- `mario_geo.bin`: normal CJ model. Its filename registers it as `mario_geo`, which CJ64 requests from SM64CoopDX.
- `mario_wingcap_geo.bin`: separate CJ wingcap/jetpack accessory. It is preserved for the upcoming Jetpack implementation; it is not yet attached to CJ and does not provide flight, fuel or thrust behaviour.
- `[CS] Carl Johnson.zip`: original Character Select archive retained as the source reference.

The normal actor contains 20 `GEO_ANIMATED_PART` nodes in the same order used by the controller and the calibrated animation tables. The binary uses the existing Mario-compatible GeoLayout function hooks. No separate/global DynOS pack is needed; place the mod's actor files under its own `actors/` folder.

## Size

The scaling workflow changes the root `GEO_SCALE` to `0.39` (about 1.5× the original normal actor scale). The wingcap/Jetpack accessory is scaled to the same root value. This is an initial increase for an in-game size check, **not a verified 280-unit measurement**. We do not apply a global 90-degree rotation: the Mario-compatible skeleton already uses its native local coordinate convention.

## Animations

The previous animation tables were generated for the experimental FBX/Fast64 rig. The private replacement module is recalibrated against the CS actor's first `IDLE_stance` sample, per animated node, to remove static orientation offsets before preserving relative motion.

The generated animation module is not committed because it contains keyframes derived from the user's `ped.ifp`. Use `tools/normalize_cs_animation_tables.py` to recalibrate a private generated Lua table:

```sh
python tools/normalize_cs_animation_tables.py cj64_gta_animations.lua --output cj64_gta_animations_cs.lua
```

The CS model has 20 animated parts, not the full GTA skeleton. Individual finger, toe, breast and belly tracks cannot be ported one-to-one onto this model. A genuinely full-fidelity port requires a model with the complete GTA skeleton and matching skinned geometry, or a rebuilt GeoLayout with corresponding bones and vertex weights. The current 13 clips are experimental and still require visual/in-game validation.

## Workflow and validation

- [Scale CS CJ DynOS actors](.github/workflows/scale-cs-cj-actor.yml) applies the model scale and verifies the DynOS binary structure.
- [CJ rigged actor export](.github/workflows/cj-rig-transfer.yml) is the legacy FBX/Fast64 experiment and is not the current source of the active CS actor.
- `tools/scale_cs_cj_actor.py` changes only the root scale command and checks the 20 animated-part count.
- `tools/normalize_cs_animation_tables.py` recalibrates a private animation module for the 20-node CS actor.

Passing a structural workflow does not prove that the character looks correct on Android or that every animation is faithful. That still requires testing inside SM64CoopDX.

