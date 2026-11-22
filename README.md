# CJ64

**Carl Johnson character replacement for SM64CoopDX.**

The current visual model target is 280 SM64 units (1.75× the 160-unit Mario reference). Only the mesh is enlarged; native Mario physics and collision remain unchanged.

## 0.1.0-alpha — replacement framework and asset pipeline

CJ64 replaces only Mario's visible model while keeping the engine's native player entity and behaviour.

- Keeps the original `MarioState` and `marioObj`.
- Does not spawn a second physical character.
- Does not replace native movement, physics, collision, camera, actions or interactions.
- Looks for a DynOS actor named `cj_geo`.
- Waits safely if the actor has not been installed; Mario remains visible.

## Temporary animation plan: native Mario animations

The first playable CJ version will use the existing SM64CoopDX Mario animations. CJ64 will not register, replace or emulate GTA animations in this phase.

This reuses Mario's native animation state and keeps the Lua mod simple. It only works once the CJ mesh has been correctly adapted to the native Mario Armature, with compatible hierarchy and vertex-group weights. Merely assigning the 58-bone GTA FBX rig to the player model is not sufficient.

## Model and textures

The source model package is a rigged Carl Johnson FBX with 58 bones and four texture maps. It is an authoring source, not a ready-to-load DynOS actor.

The CJ mesh must be adapted to the SM64CoopDX Mario Armature and exported as a GeoLayout/DynOS actor named `cj_geo`. See [docs/MODEL_IMPORT.md](docs/MODEL_IMPORT.md).

Source credit: Carl Johnson (CJ), by Tsaphnat (Tsaphnat Mbuyi), Sketchfab, CC BY 4.0. See [assets/cj/source/README.md](assets/cj/source/README.md).

## Original GTA:SA animations — later phase

The original GTA: San Andreas clips may be added later if their source animation file becomes available. CJ64 includes an ANP3 reader, a candidate clip manifest and a first-stage FBX bone map for that future work.

The IFP file is not included in the repository. The current retarget notes report structural validation of candidate clips, but the animation keyframes must be supplied again as a local `ped.ifp` input to regenerate and bake original GTA clips. Do not commit the commercial source file. Custom clips would still need to be retargeted and baked onto the Mario Armature before being converted to SM64/DynOS animation data. See [docs/ANIMATIONS.md](docs/ANIMATIONS.md).

## Remote Blender bridge

CJ64 can run Blender headlessly through GitHub Actions. It exports the DynOS actor, saves an editable `.blend` scene, and produces geometry/texture diagnostics. This is an on-demand cloud build, not a live MCP session. See [docs/BLENDER_BRIDGE.md](docs/BLENDER_BRIDGE.md) for instructions from Android.

## Files

- `main.lua` — mod entry point.
- `character.lua` — safe native model replacement.
- `actors/cj/` — final DynOS actor destination.
- `tools/ifp_reader.py` — ANP3 parser kept for future original-animation work.
- `tools/extract_cj_animations.py` — extracts selected tracks from a user-provided `ped.ifp`.
- `tools/cj_animation_manifest.json` — candidate original clip names.
- `tools/cj_fbx_bone_map.json` — first-stage map to the supplied 58-bone FBX.
- `tests/test_ifp_reader.py` — synthetic parser regression tests.

## Install

Place the extracted `CJ64` folder inside the SM64CoopDX `mods` directory and enable it. It is a Lua mod, not an APK.

## Validation and current status

CI checks Lua syntax/replacement tests and Python IFP parser tests using a synthetic ANP3 file. It does not prove that the real CJ model has been rigged/exported or that the character works in-game or on Android.

**Current milestone:** export and test the CJ model using native Mario animations. Original GTA animations are deferred. The final DynOS actor and in-game CJ model are not complete yet.
