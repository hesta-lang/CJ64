# CJ64

**Carl Johnson character replacement for SM64CoopDX.**

CJ64 replaces Mario's visible character model with a rigged Carl Johnson model from GTA: San Andreas. It keeps the existing Mario player object, movement, physics, collision, camera, actions and interactions.

## Model integration

The rigged actor and its textures are shipped **inside the CJ64 mod**:

```
mods/
└── CJ64-Rigged-Test/
    ├── main.lua
    ├── character.lua
    ├── rigged_actor.lua
    └── actors/
        └── Assets/
            ├── geo.inc.c
            ├── geo_header.h
            ├── model.inc.c
            └── texture PNG files
```

SM64CoopDX scans each mod's `actors/` directory at startup. It compiles the actor sources into `actors/mario_geo.bin` inside that same mod and registers the binary as a mod-owned custom actor. CJ64 then requests the actor by the GeoLayout name `mario_geo`.

This uses the engine's DynOS actor compiler internally, but **does not require a separate/global DynOS pack**. Do not copy anything to `dynos/packs/`; install only the CJ64 mod folder.

The model is targeted at 280 SM64 units. The rig-transfer validation reported 1,630 weighted vertices, one deform influence per vertex, zero invalid weights, a 20-node Mario-compatible armature, and a preserved native Mario rest pose. These are export checks, not proof of correct appearance or animation in-game.

## Installation

1. Close SM64CoopDX.
2. Remove the older standalone `dynos/packs/CJ64` folder if a previous build installed it.
3. Extract `CJ64-Install-Package.zip`.
4. Copy only `mods/CJ64-Rigged-Test` into the game's `mods/` directory.
5. Start SM64CoopDX and enable **CJ64-Rigged-Test** in the Mods menu.

On startup the game generates `mods/CJ64-Rigged-Test/actors/mario_geo.bin` from the embedded source files. The generated `.bin` is not shipped in the ZIP, so stale actor binaries are not reused.

## GTA: San Andreas animations

The model uses the native 20-node Mario-compatible armature so SM64CoopDX can deform the mesh. Original GTA animation clips require converted animation tables generated from the supplied `ped.ifp`. Those tables are kept out of the public repository because they are derived from the commercial game's animation file; the public workflow validates the rig and model export, not the private clip data.

The experimental converted clips have not been visually approved or confirmed in-game. Native Mario physics remain authoritative, and any animation retargeting must not move the player root independently of MarioState.

## Build and validation

The [CJ rig transfer workflow](.github/workflows/cj-rig-transfer.yml) imports the source FBX into the SM64CoopDX Mario template, transfers skin weights, exports the Fast64-Gart actor, embeds its sources and textures under the mod's `actors/` directory, and validates the install ZIP.

The CI checks confirm packaging structure, texture references, GeoLayout name and scale, model weights, skeleton and Lua syntax. They cannot confirm Android runtime rendering, skin deformation or animation quality; that still requires an in-game test.

## Source and credits

The Carl Johnson source model is by Tsaphnat (Tsaphnat Mbuyi), Sketchfab, CC BY 4.0. See [assets/cj/source/README.md](assets/cj/source/README.md).

## Repository tools

- `tools/inspect_cj_mario_rigs.py` — inspects the source and target armatures.
- `tools/prepare_cj_rig_transfer.py` — transfers the CJ skin to the Mario-compatible armature and exports the actor source.
- `tools/fix_cj_dynos_texture_paths.py` — normalizes texture paths and embeds the actor under the mod's `actors/` folder.
- `tools/ifp_reader.py` and `tools/generate_cj_sm64_animations.py` — parse and retarget owner-provided GTA animation data.
