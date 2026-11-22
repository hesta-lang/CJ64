# CJ to SM64CoopDX Mario retarget

## Inspected rigs

The source CJ FBX and official SM64CoopDX Mario template were inspected with
Blender and Coop Deluxe Fast64. The CJ source armature contains 58 bones. The
Mario template armature contains 68 bones, while Fast64 exports exactly 20
animatable GeoLayout nodes in its own traversal order. Their order and
inspected rest rotations are stored in
`tools/cj64_sm64_animation_retarget_map.json`.

The target has fewer animation joints than the GTA ped skeleton. Spine and
neck chains are combined for the first pass; source clavicle/upper-arm/
forearm/hand tracks are assigned to corresponding Mario nodes. Finger, toe,
facial, breast, and belly tracks have no independent channel in this
20-node target.

## Source IFP and generated data

The owner supplied the original ANP3 `ped.ifp`. It parsed as package
`ped` with 294 clips and 1,433,248 bytes. Thirteen selected clips were
found, with 5,097 source keyframes in total:
`IDLE_stance`, `WALK_start`, `WALK_player`, `run_player`,
`sprint_civi`, `Run_stop`, `JUMP_launch`, `JUMP_glide`,
`JUMP_land`, `FALL_fall`, `FALL_glide`, `FALL_land`, and
`Swim_Tread`.

A first-pass Lua module was generated separately. Every clip has 63 channels
(three fixed-zero root translation channels and 60 rotation channels for the
20 Fast64 nodes) and a 126-entry index table. Source quaternion samples are
interpolated at 30 FPS and converted through the inspected rest-basis map.
Root translation is deliberately suppressed so the animation cannot take
over native player movement or physics.

The reusable generator and non-keyframe retarget map are in
`tools/generate_cj_sm64_animations.py` and
`tools/cj64_sm64_animation_retarget_map.json`. The commercial IFP and
derived per-frame Lua arrays remain outside the public repository.

## Not yet integrated or validated

The current DynOS actor is still a static CJ mesh. It has no compatible
20-node Mario/Fast64 animated hierarchy or transferred weights. Therefore
the generated Lua table module is not loaded or called by `main.lua`; doing
so before the model is rigged would not animate CJ.

Remaining work:
1. Transfer/reassign CJ vertex weights to the Mario deform bones without
   spawning a second character or changing `MarioState`, movement,
   collision, or camera.
2. Validate the retargeted poses and joint axes visually in Blender.
3. Export the skinned `cj_geo` actor with the 20-node hierarchy using Coop
   Deluxe Fast64.
4. Load the private Lua module and map animation roles to native Mario
   action/animation states, keeping the vanilla fallback.
5. Test idle, walk, run, jump, fall, land, and swim in SM64CoopDX on Android.

The current result is a structurally checked first pass, not an in-game-ready
animation release. `sprint_civi` remains a generic civilian sprint
candidate, not confirmed as CJ-specific.
