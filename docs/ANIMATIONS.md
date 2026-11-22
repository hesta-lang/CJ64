# CJ original animations

## Source

The original GTA: San Andreas player/pedestrian animation set is `anim/ped.ifp`. The uploaded CJ model package contains a rigged FBX and four textures, but **no IFP file or animation clips**.

The public animation index includes the player clips `IDLE_stance`, `WALK_start`, `WALK_player`, `run_player`, `Run_stop`, `JUMP_launch`, `JUMP_glide`, `JUMP_land`, `FALL_fall`, `FALL_glide`, `FALL_land` and `Swim_Tread`. `sprint_civi` is included as a candidate only: it is a generic civilian sprint and must be confirmed against CJ's default controller before using it.

Do not bundle a random mirror copy of `ped.ifp`. It is commercial game data. Supply the file from your own legitimate GTA: San Andreas installation; CJ64 does not include it.

## Find it on Android

For the classic Android build, check the game's extracted data first:

```text
Android/data/com.rockstargames.gtasa/files/anim/ped.ifp
```

If it is not there, check the OBB directory:

```text
Android/obb/com.rockstargames.gtasa/
```

Open the matching `main.*.com.rockstargames.gtasa.obb` with ZArchiver without modifying it, and look for `anim/ped.ifp` inside. The exact OBB filename depends on the game build. Copy only `ped.ifp` out to a normal folder. If your install uses a different package name or layout, the path will differ.

## Extract

Python 3 is required. From the repository root:

```sh
python tools/extract_cj_animations.py /path/to/anim/ped.ifp --list
python tools/extract_cj_animations.py /path/to/anim/ped.ifp --output cj_original_animations.json
```

The output records source bone names/IDs, quaternion keys, timestamps and raw/decoded translations. It is an interchange file only, **not game-ready animation data**. Keep it private/local; do not publish a dump of the commercial game's animation package.

## How they enter SM64CoopDX

GTA IFP clips target GTA's pedestrian HAnim skeleton. SM64CoopDX does not read IFP files. Its custom Lua route uses SM64 animation arrays (`values` and `index`) through `smlua_anim_util_register_animation(...)`. The model must be skinned to the native Mario Armature; the original `marioObj` and MarioState continue to provide physics/collision.

The uploaded FBX contains 58 bones. `tools/cj_fbx_bone_map.json` maps GTA IFP bone IDs/names onto candidate FBX joints. This is only a first-stage mapping; it is **not yet the final Mario-armature retarget**. Validate the source rest pose, bone roll, axes and skin weights in Blender. Extra facial bones and finger segments without a direct GTA/SM64 match should be kept static or omitted initially.

The IFP ANP3 encoding uses signed 16-bit quaternion components divided by 4096, translation values divided by 4096, and timestamps divided by 60. The parser preserves the raw translation values as well, because the animation needs to be checked against the source rig before baking.

## Required conversion stages

1. Extract the user's `ped.ifp` and verify which clips are present.
2. Apply tracks to the FBX skeleton by GTA bone ID, then validate quaternion handedness, axis order and translation direction in Blender.
3. Retarget and bake actions onto the SM64CoopDX Mario Armature using the official character-template/Fast64 pipeline.
4. Export the CJ DynOS actor as `cj_geo` and bake custom clips.
5. Register the SM64-formatted Lua animation tables and select those clips from the player update hook.
6. Test idle, walk, run, jump, fall, landing and swimming in SM64CoopDX.

The official character-template documentation describes Mario-armature vertex groups, GeoLayout export, DynOS animation replacement and custom Lua animation registration. The Lua path can add clips without replacing vanilla animations, but requires correct SM64 `values` and `index` arrays.

## Status

- [x] Uploaded FBX inspected: 58 bones and skin clusters.
- [x] ANP3 parser, candidate clip manifest and first-stage FBX bone map added.
- [x] Synthetic parser regression tests added.
- [ ] Receive and parse the user's `ped.ifp`.
- [ ] Verify clips on the CJ source rig.
- [ ] Retarget/bake model and animations to Mario Armature.
- [ ] Export DynOS actor and custom SM64 Lua clips.
- [ ] In-game and multiplayer test.

CJ's model and original animations are **not yet playable** in-game.
