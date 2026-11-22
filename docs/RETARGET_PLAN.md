# CJ to SM64CoopDX Mario retarget

## Rig inspection

The source CJ FBX and the official SM64CoopDX Mario template were imported in
Blender 4.5.16 LTS. Fast64-Coop was loaded before inspecting the Mario
GeoLayout properties. The Mario armature contains 68 bones, but Fast64 exports
exactly 20 animation nodes in a fixed traversal order. The CJ source armature
contains 58 bones and its skinned mesh uses 57 weighted groups.

The target hierarchy does not have a one-to-one equivalent for all GTA joints.
Source spine and shoulder chains must be combined into the available Mario
nodes. Fingers, toes and detailed face/breast tracks have no separate channels
in the 20-node Fast64 animation hierarchy.

## First-pass output

The user-supplied `ped.ifp` was parsed locally: 294 clips were found, including
the 11 selected candidates, with 4,731 source keyframes. The generated Lua
module contains 11 calls to `smlua_anim_util_register_animation`, using the
20-node Fast64 order.

Each registration has 63 channels: three zeroed root-translation channels and
60 rotation channels. The index table contains 126 16-bit count/offset entries.
Root motion is deliberately removed so GTA animation data cannot override
SM64CoopDX player movement, physics or the original `marioObj`.

The Lua module and reports are delivered as a separate package. They are not
committed to this repository because their values are extracted from
copyrighted commercial game animation data. The original `ped.ifp` is not
redistributed.

## Validation

The local structural validator passed all 11 registrations. It confirmed:
- 63 channels per clip and 126 index shorts per clip.
- Contiguous offsets with no unreferenced value entries.
- All values and offsets fit unsigned 16-bit storage.
- All three root translation channels contain a single zero sample.
- The Lua tables match the generated report.

The repository's GitHub Actions validation workflow also passed after adding
Python syntax checks and the existing automated test suite.

## Not yet complete

This is a first-pass mathematical retarget, **not a visually approved or
in-game-tested release**. The animation data has not yet been reviewed as
Blender Actions deforming the CJ mesh on Mario's Armature, exported through
Fast64 inside Blender, or tested in SM64CoopDX. CJ's source vertex weights still
need to be transferred to Mario's target vertex groups before a working DynOS
actor can be exported.

The selected `sprint_civi` clip is a generic civilian sprint candidate, not
confirmed as CJ-exclusive. Finger, toe, facial and breast/belly animation is
omitted in this pass. Keep vanilla Mario animations as the fallback.

## Remaining work

1. Visually review the retargeted clips and joint axes in Blender.
2. Transfer CJ's mesh weights to the Mario Armature and export the DynOS actor.
3. Export the clips with Fast64 and validate the baked SM64 animation arrays.
4. Connect the registered clip names to the appropriate player action/state
   hooks and test idle, walk, run, jump, fall, land and swim in-game.
