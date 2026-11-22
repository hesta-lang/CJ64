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
Root translation is deliberately suppressed so these clips cannot take
over native player movement or physics. The generator uses zero-based final
frame indices for each clip.

The reusable generator and non-keyframe retarget map are in
`tools/generate_cj_sm64_animations.py` and
`tools/cj64_sm64_animation_retarget_map.json`. The commercial IFP and
derived per-frame Lua arrays remain outside the public repository.

## Rig transfer and Fast64 export

The current workflow `.github/workflows/cj-rig-transfer.yml` performs the
full pipeline in Blender 3.6 with the official Coop Deluxe Fast64 add-on:

1. Download the official Mario template and import the source CJ FBX.
2. Inspect the real CJ and Mario rigs and preserve their rest matrices.
3. Convert the CJ FBX Y-up coordinates to the Mario template X-up coordinates.
4. Reposition the Mario/Fast64 animation bones from corresponding CJ source
   rest matrices and scale the model to 280 SM64 units.
5. Assign every CJ vertex to its nearest Mario deform-bone segment at exactly
   weight 1.0. This avoids unsupported smooth multi-bone skinning.
6. Split textures into TMEM-safe UV islands, convert materials, and export
   the skinned `cj_geo` actor using Fast64's armature GeoLayout exporter.
7. Generate a retarget map from the actual post-transfer bone rest rotations
   and Fast64 animation-node traversal.

The workflow artifact `CJ64-rigged-actor` is intended to contain the
installable actor ZIP, editable Blender scene, rest-pose preview, validation
report, and generated retarget map. The generated animation tables are not
included because they are derived from the owner's commercial `ped.ifp`.

The previous rig-transfer preview covered 1,630 vertices across 15 deform
groups. The updated single-influence/Fast64 export path is a new build and
must pass CI and visual inspection before being treated as complete.

## Remaining work

1. Visually inspect the rigged rest pose and the original GTA animation poses.
2. Correct the weighting and retarget basis wherever the previews show errors.
3. Export the skinned `cj_geo` actor through Coop Deluxe Fast64.
4. Include/load the private Lua animation module and map its roles to native
   Mario action states without changing `MarioState`, movement, collision,
   or camera.
5. Test idle, walk, run, jump, fall, land, and swim in SM64CoopDX on Android.

The current static DynOS actor is unchanged. The rigged Blender scene is a
separate preparation artifact; it must not be described as an in-game
animation integration until Fast64 export and runtime tests succeed.
