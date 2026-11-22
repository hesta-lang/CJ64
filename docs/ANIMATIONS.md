# CJ original animations: extraction and integration route

## Source package

The selected clips come from the user-supplied GTA: San Andreas `anim/ped.ifp`
package. The file itself is game data and is not committed to this repository. The current project workspace does not contain the IFP bytes, so the original file must be supplied again as an external build input before keyframes can be regenerated.
The CJ FBX and its four textures remain under `assets/cj/source/`.

Eleven candidates were extracted locally: `IDLE_stance`, `WALK_player`,
`run_player`, `sprint_civi`, `JUMP_launch`, `JUMP_glide`, `JUMP_land`,
`FALL_fall`, `FALL_glide`, `FALL_land`, and `Swim_Tread`.
`sprint_civi` is a generic civilian sprint, not verified as a CJ-exclusive clip.

## Retarget result

The supplied IFP contained 294 clips. The 11 selected candidates were present,
with 4,731 source keyframes total. The CJ FBX has 58 source bones. The official
Coop Deluxe Mario template was inspected with Blender 4.5.16 and Fast64-Coop:
the Mario armature contains 68 bones, while Fast64 exports exactly 20 animation
nodes in its GeoLayout traversal order.

A first-pass mathematical retarget was generated locally as
`CJ64-CJ-Mario-Animations.lua`. It registers 11 clips through
`smlua_anim_util_register_animation`. Each clip contains 63 animation
channels: three root translation channels fixed at zero, plus three rotation
channels for each of the 20 Fast64 nodes. The corresponding index array contains
126 16-bit count/offset entries.

The generated Lua, detailed report and validation JSON are delivered separately
to the project maintainer. They are not committed here because the generated
tables contain animation data extracted from commercial game data. The input
`ped.ifp` is not redistributed.

## Retarget assumptions and limitations

- The first `IDLE_stance` keyframe is used as the shared source reference pose.
- Source joint rotation changes are transported through the source hierarchy
  and mapped into Mario's 20 exportable animation nodes.
- Extra source spine/shoulder joints are combined where Mario has fewer nodes.
- Finger, toe, detailed facial, breast and belly tracks have no independent
  channel in this 20-node target hierarchy and are omitted.
- Root translation is zeroed intentionally; the original SM64CoopDX player
  movement, physics and `marioObj` remain authoritative.
- Vanilla Mario animations remain the fallback.

**Validation boundary:** all 11 generated tables passed structural validation
for channel count, 16-bit values, contiguous offsets, report consistency and
zero root translation. The retarget has not yet been visually validated as
Blender Actions on Mario's Armature, exported through Fast64 inside Blender, or
tested in SM64CoopDX. This is not an in-game-ready animation release.

## Next steps

1. Inspect the generated actions and deformation visually in Blender.
2. Transfer CJ mesh weights to Mario's Armature and export the DynOS actor.
3. Export/bake the animations using Fast64 and test the actor and clips in-game.
4. Connect each registered clip to the appropriate Mario action/state hook while
   retaining the vanilla animation fallback.
