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

The source Carl Johnson FBX has a 58-bone rig and four texture maps. The rig-transfer workflow now exports a separate experimental DynOS actor using the 20-node Mario/Fast64-Gart hierarchy. Workflow run [#71](https://github.com/hesta-lang/CJ64/actions/runs/45089345497) completed successfully: 1,630 vertices, exactly one weight-1.0 deform influence per vertex, zero invalid weights, zero fallback vertices, and a 280-unit evaluated height. The artifact includes the installable actor ZIP, editable Blender scene, rest-pose preview, report, and actual retarget map. This is a successful CI export, not yet a visually approved or in-game-tested model. See [docs/RETARGET_PLAN.md](docs/RETARGET_PLAN.md).

The visual-size override remains 280 SM64 units. This is a project scale target, not a claim about CJ's canonical GTA height.

Source credit: Carl Johnson (CJ), by Tsaphnat (Tsaphnat Mbuyi), Sketchfab, CC BY 4.0. See [assets/cj/source/README.md](assets/cj/source/README.md).

## Original GTA: San Andreas animations

The supplied `ped.ifp` parses as ANP3 package `ped` with 294 clips. Using the actual 20-node rest map from workflow #71, I regenerated 13 selected clips containing 5,097 source keyframes: idle, walk start/walk, run, sprint candidate, run stop, jump, fall, landing, and swim. The generated Lua table is 170,984 bytes and samples at 30 FPS.

The public repository contains the reusable generator and rig-transfer workflow:
- `tools/generate_cj_sm64_animations.py`
- `tools/cj64_sm64_animation_retarget_map.json` (actual v2 rest map captured from successful workflow #71)
- `tools/prepare_cj_rig_transfer.py`

The generated keyframe Lua module and original IFP are kept outside the public repository because they contain data derived from the commercial game's animation file. The experimental download bundle combines the rigged actor with the regenerated `cj64_gta_animations.lua`; it does not include `ped.ifp`.

**The original animations are not yet verified in-game.** The experimental bundle contains the CI-exported skinned actor and regenerated Lua tables. The controller only activates when both the rigged-actor marker and animation module are present; native MarioState, movement, collision, camera, and physics remain authoritative. The rest pose and animated poses still need visual review and SM64CoopDX testing. See [docs/ANIMATIONS.md](docs/ANIMATIONS.md).

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

Download the [experimental rigged + animated package](https://github.com/hesta-lang/CJ64/actions/runs/45089345497), extract it, place the `CJ64-Rigged-Test` folder in SM64CoopDX's `mods` directory, and enable it. It is a Lua mod, not an APK. Keep a copy of the current mod first: this package is experimental and has not yet been tested in-game.

## Validation and current status

CI run #71 passed the complete rigged export and actor validation. It verified 1,630/1,630 weighted vertices, one influence per vertex, no invalid/fallback weights, 280 SM64 units, and 20 animation nodes. The actual v2 retarget map is now checked in. The private animation module was regenerated against that map and passed Lua syntax/structural checks (13 clips, 63 channels and 126 index entries per clip). These checks do not prove that the poses look correct or that SM64CoopDX loads and plays them correctly.

**Current milestone:** CI export and first-pass animation-table generation are complete. Remaining validation is visual pose review, in-game testing, and Android testing. The sprint candidate `sprint_civi` is a generic civilian clip, not confirmed as CJ-exclusive.
