# CJ model import

Source file: `CarlJohnson-GTASA.FBX`, accompanied by `head.png`, `upper body.png`, `legs.png` and `shoes.png`. The source FBX contains a 58-bone GTA rig and skin clusters; it is not loaded directly by the game.

## Runtime model

The CJ mesh is transferred onto SM64CoopDX's native Mario/Fast64-Gart 20-node armature. This keeps the original game player entity and its animation node layout intact. The current rig-transfer export validates:

- 1,630 weighted vertices.
- Exactly one deform influence per vertex, with weight 1.0.
- No invalid or unweighted vertices.
- Native Mario rest matrices preserved.
- A 280 SM64-unit target height.

These checks are structural and do not substitute for visual or in-game verification.

## Embedded actor layout

The generated model source and textures are copied into the mod:

```
mods/CJ64-Rigged-Test/actors/Assets/
  geo.inc.c
  geo_header.h
  model.inc.c
  *.png
```

SM64CoopDX's own mod-loading path scans `<mod>/actors`, compiles the actor to `<mod>/actors/mario_geo.bin`, and registers that binary as a custom actor owned by the mod. The Lua controller requests the GeoLayout name `mario_geo`.

The actor is therefore self-contained in the CJ64 mod. It does not need a separate folder under `dynos/packs/`. The engine still uses its DynOS compiler internally; that does not make this an independently installed pack.

## Export pipeline

1. Inspect the actual CJ FBX and SM64CoopDX Mario target armatures.
2. Transfer the CJ skin weights to the Mario-compatible armature.
3. Export the actor source with Fast64-Gart.
4. Normalize texture include paths and strip unsupported empty `CUSTOM_CMD()` placeholders.
5. Copy `Assets/` into the mod's `actors/` folder.
6. Validate that the ZIP contains only the mod folder, with all texture references resolved and no standalone DynOS pack directory.

The export target root GeoLayout is `mario_geo`, with a root scale of 1.0 (the 280-unit target).

## Animations and physics

Original GTA: San Andreas animation tracks need to be retargeted to the 20-node runtime armature. The user-provided `ped.ifp` is processed into private animation tables; those derived tables are not committed publicly. Until the retargeted clips have been reviewed in-game, the model can fall back to the game's native Mario animation system.

MarioState, collision, movement, physics and camera remain unchanged.
