# CJ64 animation plan

## Current phase: native Mario animations

The first playable CJ model will use the **default SM64CoopDX Mario animations**. CJ64 does not need GTA San Andreas animation files for this phase.

The Lua replacement keeps the engine's original `MarioState` and `marioObj` and does not register or select custom animation clips. The model must be exported on the native Mario Armature with compatible vertex groups and weights so that the existing player animation system can deform it.

This is a temporary baseline, not a claim that CJ's original GTA movements have been recreated. The first in-game checks should cover idle, walking, running, jumping, falling and landing. Swimming and other special actions should also be checked once the basic rig works.

## Why the FBX needs retargeting

The supplied `CarlJohnson-GTASA.FBX` has 58 bones and skin clusters. Its GTA skeleton does not automatically match the SM64CoopDX Mario Armature. The mesh weights need to be reassigned and tested against Mario's armature before the actor is exported. See [MODEL_IMPORT.md](MODEL_IMPORT.md).

The official [SM64CoopDX character template](https://github.com/coop-deluxe/character-template) documents the Mario Armature, vertex-group assignment and GeoLayout export process.

## Later phase: original GTA animations

The original GTA: San Andreas player/pedestrian clips are associated with `anim/ped.ifp`. The uploaded CJ model package did not contain an IFP file or animation clips. The IFP is not included in CJ64 and is not needed for the current approach.

When a legitimate source copy is available:

1. Inspect the IFP and confirm which player clips are present.
2. Extract the selected tracks with `tools/extract_cj_animations.py`.
3. Apply tracks to the FBX skeleton by GTA bone ID and verify quaternion order, handedness, axes and translation direction.
4. Retarget and bake the clips onto the native Mario Armature.
5. Convert the baked actions to SM64/DynOS animation data.
6. Add/select the custom clips without changing MarioState, movement, collision or camera.

SM64CoopDX does not load GTA IFP files directly. Its custom Lua route uses SM64 animation arrays (`values` and `index`) through `smlua_anim_util_register_animation(...)`; the clips must be converted first.

## Tooling retained for future conversion

- `tools/ifp_reader.py` — ANP3 parser.
- `tools/extract_cj_animations.py` — selected-track extraction to interchange JSON.
- `tools/cj_animation_manifest.json` — candidate clip names to verify against the source file.
- `tools/cj_fbx_bone_map.json` — first-stage GTA IFP joint to FBX joint mapping; not a final retarget map.
- `tests/test_ifp_reader.py` — synthetic parser tests only.

Do not redistribute a dump of GTA's commercial animation files in this repository.

## Status

- [x] Inspect the uploaded FBX (58 bones and skin clusters).
- [x] Establish native Mario animations as the temporary baseline.
- [x] Keep the original player entity and physics architecture.
- [ ] Adapt CJ's weights to the Mario Armature.
- [ ] Export the `cj_geo` DynOS actor.
- [ ] Test idle, walk, run, jump, fall, landing and special actions in-game.
- [ ] Later, obtain and verify original animation source data.
- [ ] Later, retarget and integrate selected original CJ clips.

CJ's model is not yet playable in-game; the current repository contains the replacement framework and conversion tooling, not the exported actor.
