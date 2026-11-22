# CJ to SM64CoopDX Mario retarget

## Inspected rigs

The source CJ FBX and official SM64CoopDX Mario template were inspected with
Blender and Coop Deluxe Fast64. The CJ source armature contains 58 bones. The
Mario template armature contains 68 bones, while Fast64 exports exactly 20
animatable GeoLayout nodes in its own traversal order. That 20-node order is
stored in the separately delivered animation bridge report.

The target has fewer animation joints than the GTA ped skeleton. Spine and
neck chains must be combined, source clavicle/upper-arm/forearm/hand tracks
must be assigned to the corresponding Mario nodes, and finger, toe, facial,
breast, and belly tracks have no independent target channel in this first
pass.

## Source IFP and first-pass data

The user supplied the original ANP3 `ped.ifp` again. It parsed as package
`ped` with 294 clips and 1,433,248 bytes. Thirteen selected clips were found,
with 5,097 source keyframes in total:
`IDLE_stance`, `WALK_start`, `WALK_player`, `run_player`,
`sprint_civi`, `Run_stop`, `JUMP_launch`, `JUMP_glide`, `JUMP_land`,
`FALL_fall`, `FALL_glide`, `FALL_land`, and `Swim_Tread`.

A first-pass Lua module was generated separately. Every clip has 63 channels
(three fixed-zero root translation channels plus 60 rotations for Fast64's 20
nodes) and a 126-entry index table. Source rotations are sampled at 30 FPS and
made relative to the first `IDLE_stance` keyframe. Root translation is
intentionally suppressed so the custom animation cannot take control of
SM64CoopDX player movement or physics.

The generated Lua tables are not stored in the public repository because they
are derived from commercial game animation data. The original IFP is not
stored either.

## Not yet integrated or validated

The project's current DynOS actor is a static CJ mesh and does not yet contain
a compatible 20-node animated rig or transferred weights. Therefore the new
Lua tables are not loaded by `main.lua` and are not called from the player
hooks. Enabling them now would not animate the current model.

The following work remains:
1. Remap/transfer CJ mesh weights to the Mario rig without creating a second
   physical character or changing MarioState, movement, collision, or camera.
2. Validate the 13 retargeted poses visually on the CJ mesh in Blender.
3. Export the skinned actor and animation data with the actual Coop Deluxe
   Fast64 exporter.
4. Wire clips to appropriate native player action states and test idle, walk,
   run, jump, fall, land, and swim in SM64CoopDX.

The current result is a structural first pass only, not an in-game-ready
animation release. `sprint_civi` remains a generic civilian sprint candidate,
not confirmed as CJ-specific.
