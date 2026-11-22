# CJ64

**Carl Johnson character replacement for SM64CoopDX.**

## 0.1.0-alpha — replacement framework and asset pipeline

CJ64 is designed to replace only Mario's visible model while keeping the engine's native player entity and behaviour.

- Keeps the original `MarioState` and `marioObj`.
- Does not spawn a second physical character.
- Does not replace native movement, physics, collision, camera, actions or interactions.
- Looks for a DynOS actor named `cj_geo`.
- Waits safely if the actor has not been installed; Mario remains visible.

## Model and textures

The source model package is a rigged Carl Johnson FBX with 58 bones and four texture maps. It is an authoring source, not a ready-to-load DynOS actor. Its FBX rig differs from the native SM64 player skeleton.

Add the files from the supplied source package under `assets/cj/source/`. Preserve the attribution in that folder's README: Carl Johnson (CJ), by Tsaphnat (Tsaphnat Mbuyi), Sketchfab, CC BY 4.0.

## Original GTA:SA animations

The original player/pedestrian clips are stored in GTA San Andreas `anim/ped.ifp`. CJ64 now includes an ANP3 reader, a candidate clip manifest, a first-stage GTA-IFP-to-FBX joint map, and synthetic parser tests.

The IFP itself is not included. Supply `ped.ifp` from your own GTA San Andreas installation. The extraction script writes an interchange JSON, not a game animation. The tracks still need to be applied to the source FBX, retargeted/baked onto the SM64CoopDX Mario Armature, and exported as SM64/DynOS assets. See [docs/ANIMATIONS.md](docs/ANIMATIONS.md) and [docs/MODEL_IMPORT.md](docs/MODEL_IMPORT.md).

## Files

- `main.lua` — mod entry point.
- `character.lua` — safe native model replacement.
- `actors/cj/` — final DynOS actor destination.
- `tools/ifp_reader.py` — checked ANP3 IFP parser.
- `tools/extract_cj_animations.py` — extracts selected tracks from a user-provided `ped.ifp`.
- `tools/cj_animation_manifest.json` — candidate original clip names.
- `tools/cj_fbx_bone_map.json` — first-stage map to the supplied 58-bone FBX.
- `tests/test_ifp_reader.py` — parser regression tests.

## Install

Place the extracted `CJ64` folder inside the SM64CoopDX `mods` directory and enable it. It is a Lua mod, not an APK.

## Validation and current status

CI checks Lua syntax/replacement tests and Python IFP parser tests using a synthetic ANP3 file. It does not prove that a real `ped.ifp` parses, that the retargeted model exports, or that the character works on Android.

**The final DynOS actor and in-game CJ animations are not complete yet.**