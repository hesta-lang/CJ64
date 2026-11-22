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

The static DynOS actor remains the last verified model. The rig-transfer workflow now retargets the Mario/Fast64-Gart bones using CJ source rest matrices, assigns one deform bone per vertex (weight 1.0), converts textures for TMEM, and attempts a Fast64-Gart armature GeoLayout export at 280 SM64 units. The new exported actor still requires a passing CI build, visual review, and in-game test. See [docs/RETARGET_PLAN.md](docs/RETARGET_PLAN.md).

The visual-size override remains 280 SM64 units. This is a project scale target, not a claim about CJ's canonical GTA height.

Source credit: Carl Johnson (CJ), by Tsaphnat (Tsaphnat Mbuyi), Sketchfab, CC BY 4.0. See [assets/cj/source/README.md](assets/cj/source/README.md).

## Original GTA: San Andreas animations

The owner supplied the original `ped.ifp` again. The ANP3 reader parsed 294 clips and the first retarget pass generated data for 13 selected clips (5,097 source keyframes): idle, walk start/walk, run, sprint candidate, run stop, jump, fall, landing, and swim.

The public repository contains the reusable generator and rig-transfer workflow:
- `tools/generate_cj_sm64_animations.py`
- `tools/cj64_sm64_animation_retarget_map.json` (starter map; the workflow emits the current map from the retargeted armature)
- `tools/prepare_cj_rig_transfer.py`

The generated keyframe Lua module and original IFP are kept outside the public repository because they contain data derived from the commercial game's animation file. The current module must be regenerated with the retarget map emitted by the updated rig-transfer workflow; the earlier structural-only module is not the final in-game package.

**The original animations are not active in-game yet.** The current verified `cj_geo` actor remains static. The new workflow uses a pinned Fast64-Gart 2.5.3 binary-skinned export and the Lua action controller is guarded, but the export must pass CI and visual/in-game testing before the animation module can be enabled. See [docs/ANIMATIONS.md](docs/ANIMATIONS.md).

## Remote Blender bridge

CJ64 can run Blender headlessly through GitHub Actions. It exports the current DynOS actor, saves editable `.blend` scenes, and produces geometry/texture diagnostics. The rigged actor package is built by [the CJ rig transfer workflow](.github/workflows/cj-rig-transfer.yml). This is an on-demand cloud build, not a live Blender session. See [docs/BLENDER_BRIDGE.md](docs/BLENDER_BRIDGE.md).

## Files

- `main.lua` — mod entry point.
- `character.lua` — safe native visual-model replacement.
- `actors/cj/` — final DynOS actor destination.
- `tools/ifp_reader.py` — ANP3 parser for a user-provided `ped.ifp`.
- `tools/extract_cj_animations.py` — extracts selected IFP tracks as intermediate JSON.
- `tools/generate_cj_sm64_animations.py` — generates first-pass SM64CoopDX Lua animation tables from the owner-provided IFP and generated rig map.
- `tools/prepare_cj_rig_transfer.py` — transfers the CJ rig to Mario, builds binary skin weights, and exports the Fast64-Gart actor.
- `tools/cj_animation_manifest.json` — selected original clip names and roles.
- `tools/cj_fbx_bone_map.json` — first-stage IFP-to-source-FBX bone map.
- `tools/cj64_sm64_animation_retarget_map.json` — starter source/target map; the rig-transfer workflow emits the current rest-basis and Fast64 node map.
- `tests/test_ifp_reader.py` — synthetic ANP3 parser regression tests.

## Install

Place the extracted `CJ64` folder inside the SM64CoopDX `mods` directory and enable it. It is a Lua mod, not an APK. The private animation Lua module is not part of the current static-model install package.

## Validation and current status

CI checks Lua syntax/replacement tests and Python IFP parser tests using a synthetic ANP3 file. The animation generator passed structural checks. The previous rig-transfer preview verified 1,630 weighted vertices and a 280-unit evaluated mesh. The updated workflow now requires one influence per vertex and a Fast64-Gart actor export; its new result has not yet been verified. Neither result proves Android runtime compatibility.

**Current milestone:** the Lua action-state controller and Fast64-Gart rigged-actor export path are implemented. The new export must pass CI and visual review; the private animation tables must be regenerated using its emitted retarget map. Android/in-game animation testing remains pending.
