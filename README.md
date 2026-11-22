# CJ64

**Carl Johnson character replacement for SM64CoopDX.**

The visual model target is 280 SM64 units (1.75× the 160-unit Mario reference). Only the visible model is enlarged; native Mario physics and collision remain authoritative.

## 0.1.0-alpha — character replacement and animation preparation

CJ64 is designed to replace only Mario's visible model while keeping the engine's native player entity and behaviour.

- Keeps the original `MarioState` and `marioObj`.
- Does not spawn a second physical character.
- Does not replace native movement, physics, collision, camera, actions or interactions.
- Looks for a DynOS actor named `cj_geo`.
- Waits safely if the actor has not been installed; Mario remains visible.

## Model and textures

The source Carl Johnson FBX has a 58-bone rig and four texture maps. It is an authoring source, not a ready-to-load DynOS actor.

The CJ mesh must be adapted to the SM64CoopDX Mario/Fast64 Armature, assigned compatible vertex-group weights, and exported as a GeoLayout/DynOS actor named `cj_geo`. The currently exported actor is still a static mesh; it is not yet skinned to the Mario animation hierarchy. See [docs/MODEL_IMPORT.md](docs/MODEL_IMPORT.md).

The visual-size override remains 280 SM64 units. This is a project scale target, not a claim about CJ's canonical GTA height.

Source credit: Carl Johnson (CJ), by Tsaphnat (Tsaphnat Mbuyi), Sketchfab, CC BY 4.0. See [assets/cj/source/README.md](assets/cj/source/README.md).

## Original GTA: San Andreas animations

The owner supplied the original `ped.ifp` again. The ANP3 reader parsed 294 clips and the first retarget pass generated data for 13 selected clips (5,097 source keyframes): idle, walk start/walk, run, sprint candidate, run stop, jump, fall, landing, and swim.

The public repository contains the reusable generator and inspected rig map:
- `tools/generate_cj_sm64_animations.py`
- `tools/cj64_sm64_animation_retarget_map.json`

The generated keyframe Lua module and original IFP are kept outside the public repository because they contain data derived from the commercial game's animation file. The Lua module is available separately to the project owner. It has structural validation only; it has not been visually checked or used in the game yet.

**The animations are not active in-game yet.** The current `cj_geo` actor is static and does not contain the 20-node Mario/Fast64 animation hierarchy with compatible skin weights. The next step is to rig the CJ mesh to that hierarchy, validate poses, export with Fast64, and only then connect the clips to native Mario action states. See [docs/ANIMATIONS.md](docs/ANIMATIONS.md) and [docs/RETARGET_PLAN.md](docs/RETARGET_PLAN.md).

## Remote Blender bridge

CJ64 can run Blender headlessly through GitHub Actions. It exports the current DynOS actor, saves an editable `.blend` scene, and produces geometry/texture diagnostics. This is an on-demand cloud build, not a live Blender session. See [docs/BLENDER_BRIDGE.md](docs/BLENDER_BRIDGE.md).

## Files

- `main.lua` — mod entry point.
- `character.lua` — safe native visual-model replacement.
- `actors/cj/` — final DynOS actor destination.
- `tools/ifp_reader.py` — ANP3 parser for a user-provided `ped.ifp`.
- `tools/extract_cj_animations.py` — extracts selected IFP tracks as intermediate JSON.
- `tools/generate_cj_sm64_animations.py` — generates first-pass 20-node SM64CoopDX Lua animation tables.
- `tools/cj_animation_manifest.json` — selected original clip names and roles.
- `tools/cj_fbx_bone_map.json` — first-stage IFP-to-source-FBX bone map.
- `tools/cj64_sm64_animation_retarget_map.json` — inspected source/target rest-basis and Fast64 node map.
- `tests/test_ifp_reader.py` — synthetic ANP3 parser regression tests.

## Install

Place the extracted `CJ64` folder inside the SM64CoopDX `mods` directory and enable it. It is a Lua mod, not an APK. The private animation Lua module is not part of the current static-model install package.

## Validation and current status

CI checks Lua syntax/replacement tests and Python IFP parser tests using a synthetic ANP3 file. The animation generator was rerun against the owner-supplied IFP and its arrays passed structural checks. Neither check proves the rigged CJ model works in-game or on Android.

**Current milestone:** original animation data has been converted to a first-pass SM64 Lua format. The skinned animated actor and in-game animation integration are still pending.
