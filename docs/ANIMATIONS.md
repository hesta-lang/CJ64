# CJ original animations

## Source

The original GTA: San Andreas player/pedestrian clips are held in the game's `anim/ped.ifp`. The uploaded CJ model package contains a rigged FBX and four texture maps, but **no IFP or animation clips**.

The public GTA Connected animation index lists source clip names including `IDLE_stance`, `WALK_player`, `run_player`, `JUMP_launch`, `JUMP_glide`, `JUMP_land`, `FALL_fall`, `FALL_glide`, `FALL_land`, and `Swim_Tread`. `sprint_civi` is included as a candidate only; it is a generic civilian sprint, not confirmed as CJ-exclusive.

Do not bundle a random mirror copy of `ped.ifp`. It is commercial game data. Supply the file from your own legitimate GTA: San Andreas installation; CJ64 does not include it.

## Extract

Python 3 is required. From the repository root:

```sh
python tools/extract_cj_animations.py /path/to/anim/ped.ifp --list
python tools/extract_cj_animations.py /path/to/anim/ped.ifp --output cj_original_animations.json
```

The output records source bone names/IDs, quaternion keys, timestamps and translations. It is an interchange file only, **not game-ready animation data**. Keep it private/local; do not publish a dump of the commercial game's animation package.

## How they enter SM64CoopDX

GTA IFP clips target GTA's pedestrian HAnim skeleton. SM64CoopDX does not read IFP files. Its custom Lua route uses SM64 animation arrays (`values` and `index`) through `smlua_anim_util_register_animation(...)`. The model must be skinned to the native Mario Armature; the original `marioObj` and MarioState continue to provide physics/collision.

The uploaded FBX contains 58 bones. `tools/cj_fbx_bone_map.json` maps GTA IFP tracks onto the corresponding joints of that FBX. This is only a first-stage mapping; it is **not yet the final Mario-armature retarget**. GTA facial bones and extra finger segments without an SM64 equivalent should remain static or be omitted in the first playable pass.

Required remaining steps:
1. Extract the user's `ped.ifp` and verify the selected clips.
2. Apply its tracks to the FBX skeleton and check axis/quaternion conventions in Blender.
3. Retarget and bake actions onto the SM64CoopDX Mario Armature using the official character-template/Fast64 pipeline.
4. Export the CJ DynOS actor as `cj_geo` and bake the custom clips.
5. Register the SM64-formatted Lua animation tables and select those clips from the player update hook.
6. Test idle, walk, run, jump, fall, landing and swim in-game.

The official character-template documentation describes Mario-armature vertex groups, GeoLayout export, DynOS animation replacement and custom Lua animation registration. Custom Lua clips can exist without replacing vanilla animations, but require the correct SM64 `values` and `index` arrays.

## Status

- [x] Uploaded FBX inspected: 58 bones and skin clusters.
- [x] ANP3 reader, candidate manifest and FBX joint map added.
- [x] Synthetic format regression tests added.
- [ ] Receive and parse the user's `ped.ifp`.
- [ ] Verify clips on the CJ source rig.
- [ ] Retarget/bake model and animations to Mario Armature.
- [ ] Export DynOS actor and custom SM64 Lua clips.
- [ ] In-game and multiplayer test.

CJ's model and original animations are **not yet playable** in-game.
