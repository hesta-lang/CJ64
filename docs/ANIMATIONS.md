# CJ original animations: extraction and integration route

## Source package

The original GTA: San Andreas pedestrian/player clips are stored in the game's `anim/ped.ifp` package. The CJ model upload contains the FBX rig and four textures. The user subsequently supplied `ped.ifp` separately for local extraction; that copyrighted game-data file is not committed to CJ64.

A public animation index lists the `ped.ifp` names, including `IDLE_stance`, `WALK_player`, `run_player`, `JUMP_launch`, `JUMP_glide`, `JUMP_land`, `FALL_fall`, `FALL_glide`, `FALL_land`, and `Swim_Tread`. `sprint_civi` is included only as a candidate because it is a generic civilian sprint, not a clip verified as CJ-exclusive.

Do not download or commit a random copy of `ped.ifp` from a mirror. It is game data. For extraction, supply `ped.ifp` from your own legally obtained GTA: San Andreas installation. CJ64 does not bundle it.

## Extract clips to an interchange file

Python 3 is required. From the repository root:

```sh
python tools/extract_cj_animations.py /path/to/anim/ped.ifp --list
python tools/extract_cj_animations.py /path/to/anim/ped.ifp --output cj_original_animations.json
```

The first command lists all clips and their track counts. The second extracts only the clips in `tools/cj_animation_manifest.json`. The supplied file was parsed successfully: 294 total clips, all 11 manifest candidates found, 4,731 keyframes extracted. The JSON is an intermediate representation (bone IDs, names, quaternion tracks, times, and translations), **not a file the game can load**. Keep the resulting JSON private/local; do not commit or publish animation data extracted from the commercial game.

## Why a direct IFP load does not work

GTA IFP clips use the GTA pedestrian skeleton and HAnim bone IDs. SM64CoopDX does not load GTA IFP packages. Its supported custom-animation path uses the SM64 animation layout (`values` and `index`) and `smlua_anim_util_register_animation(...)`.

The uploaded CJ FBX contains 58 bones; the GTA SA ped IFP tracks use a smaller set of named/numbered pedestrian joints. The checked-in `tools/cj_fbx_bone_map.json` maps the selected IFP joints onto the corresponding CJ FBX joints. Leading spaces in GTA bone names are meaningful to this parser and are preserved. Structural validation maps 29/32 tracks for the 32-track clips (the three unmatched tracks are the breast/belly tracks with no matching FBX deform joints) and 26/26 tracks for the 26-track clips. This is only the first mapping stage; it is not yet a retarget to Mario's armature.

## Required conversion stages

1. Read `ped.ifp` and select original player clips. **Complete:** 294 clips parsed; all 11 selected clips extracted to a local interchange JSON (not committed).
2. Apply the source tracks to the corresponding CJ FBX bones using the supplied map. `tools/import_cj_ifp_actions_blender.py` now creates editable first-stage Blender Actions on the imported source rig. The quaternion/local-axis convention still requires visual validation in Blender.
3. Retarget and bake those actions onto the **SM64CoopDX Mario Armature**. The mesh must have vertex groups assigned to that armature; extra GTA facial bones/finger segments with no SM64 equivalent must be static or omitted in the first pass.
4. Export the CJ geometry as a DynOS actor and export/bake each animation using Fast64's SM64 animation exporter.
5. Register custom Lua clips using `smlua_anim_util_register_animation`, then select them from the Mario update hook with `smlua_anim_util_set_animation`. Do not use a GTA IFP reader at runtime.
6. Test idle, walking, running, jumping, falling, landing, and swimming in SM64CoopDX. Validate multiplayer/player-index behaviour and make sure model replacement still uses the original `marioObj`.

The official character-template guide describes Mario-armature vertex groups and GeoLayout export, plus two custom animation routes: DynOS replacement of existing animations or custom Lua registration. The Lua path can add clips without replacing vanilla animations, but requires correctly exported `values` and `index` tables.

## Current status

- [x] Uploaded FBX and textures inspected; FBX has 58 bones and skin clusters.
- [x] IFP ANP3 reader added with bounds checks and synthetic regression tests.
- [x] Candidate clip manifest and first-stage FBX joint map added.
- [x] User-supplied `ped.ifp` received and parsed locally (294 clips; 11 selected candidates; none missing).
- [x] Corrected IFP-to-FBX bone map using the actual leading-space track names in the uploaded file.
- [x] Added a Blender 3.6 action-import script for source-rig preview; syntax checked, not run inside Blender here.
- [ ] Visually validate the candidate clips and source rig pose in Blender.
- [ ] Retarget/bake onto Mario Armature and export a DynOS actor.
- [ ] Generate/register SM64 custom animation tables and runtime-test on SM64CoopDX.

No claim is made that CJ's model or original animations are playable in-game yet.