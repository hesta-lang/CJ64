# CJ64

**Carl Johnson character replacement for SM64CoopDX, using the Character Select DynOS actor.**

CJ64 replaces Mario's rendered model while keeping MarioState, movement, collision, camera, actions and physics native.

## Current model

The active source files are stored in `actors/cj/`:

- `mario_geo.bin`: normal CJ actor, intended to be registered inside the mod as `mario_geo`.
- `mario_wingcap_geo.bin`: separate wingcap/Jetpack accessory; it is not attached and has no flight or fuel behaviour yet.
- `[CS] Carl Johnson.zip`: original Character Select actor archive.

The compiled CS actor contains 20 `GEO_ANIMATED_PART` nodes. **Only the node count is known. Its node order, hierarchy and rest rotations have not been proven to match the Fast64/Mario animation map.** A matching count is not sufficient to reuse animation tables.

## Size

The scale workflow sets the root `GEO_SCALE` to `0.39`, approximately 1.5 times the source actor's previous root scale. The resulting in-game height has not been measured, so this is **not a verified 280-unit model**. The binary has not been given a speculative global 90-degree rotation.

## Animations

The custom GTA San Andreas clips are **disabled by default** in version `0.1.3-alpha`.

The private `cj64_gta_animations.lua` file was generated from the user's `ped.ifp` against the experimental FBX/Fast64 Mario skeleton. It was not calibrated or validated against the compiled Character Select actor. The first idle sample contains a roughly 90-degree Z rotation on the `Body` channel and large `Butt` rotations; applying those values to an unverified CS node layout can produce the horizontal pose and overlapping parts shown in the in-game screenshot.

`tools/normalize_cs_animation_tables.py` removes a reference sample from each numbered channel, but it assumes the channel order already corresponds. It does not inspect or prove the CS actor's hierarchy, node order or rest basis. Its output must not be treated as a verified retarget.

The current safe baseline leaves SM64CoopDX's native player animation handling in control while the CS actor is tested. The 20-node CS actor also cannot reproduce every independent track of the full GTA skeleton (such as individual fingers and toes).

## Test package

The [Build CJ64 CS baseline test package](.github/workflows/build-cj64-cs-baseline.yml) workflow creates a self-contained install ZIP with this structure:

```
mods/CJ64-CS-Baseline/
  main.lua
  character.lua
  actors/
    mario_geo.bin
```

Install only the generated `CJ64-CS-Baseline` folder under `mods/` for this test. Disable other CJ64 test copies while checking it. This package deliberately excludes the private GTA animation table.

## Validation status

- [Scale CS CJ DynOS actors](.github/workflows/scale-cs-cj-actor.yml) validates the binary structure and requested scale.
- [Build CJ64 CS baseline test package](.github/workflows/build-cj64-cs-baseline.yml) checks Lua syntax, actor structure and ZIP paths.
- [CJ rigged actor export](.github/workflows/cj-rig-transfer.yml) remains the separate FBX/Fast64 experiment; it does not prove the CS binary's animation compatibility.

A green workflow proves structural checks only. The model's upright orientation and appearance still require an Android in-game test. GTA animation playback must remain disabled until the CS hierarchy and rest pose are inspected and matching animation previews are checked.
