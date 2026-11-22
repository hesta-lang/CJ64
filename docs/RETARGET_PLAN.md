# CJ to SM64CoopDX Mario retarget

## Inspected rigs

The source CJ FBX and official SM64CoopDX Mario template were inspected with
Blender and Fast64-Gart. The CJ source armature contains 58 bones. The
Mario template armature contains 68 bones, while Fast64-Gart exports exactly 20
animatable GeoLayout nodes in its own traversal order. The rig-transfer
workflow writes their current order and post-retarget rest rotations into the
`CJ64-rigged-actor` artifact; the checked-in JSON is only a starter map.

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

The reusable generator and starter map are in
`tools/generate_cj_sm64_animations.py` and
`tools/cj64_sm64_animation_retarget_map.json`. The generator must be run with
the current map emitted by the rig-transfer artifact. The commercial IFP and
derived per-frame Lua arrays remain outside the public repository.

## Rig transfer and Fast64 export

The current workflow `.github/workflows/cj-rig-transfer.yml` performs the
full pipeline in Blender 3.6 with Fast64-Gart 2.5.3, pinned to commit `9384477f2ccdc8b6e05a96b52241f98808feb90b`:

1. Download the official Mario template and import the source CJ FBX.
2. Inspect the real CJ and Mario rigs and preserve their rest matrices.
3. Convert the CJ FBX Y-up coordinates to the Mario template X-up coordinates.
4. Reposition the Mario/Fast64-Gart animation bones from corresponding CJ source
   rest matrices and scale the model to 280 SM64 units.
5. Collapse each original FBX vertex's mapped source weights to its strongest
   Mario deform group at exactly weight 1.0; use nearest-bone fallback only
   where the source has no mapped weight. This avoids unsupported smooth
   multi-bone skinning while retaining the source's dominant influence.
6. Split textures into TMEM-safe UV islands, convert materials, and export
   the skinned `cj_geo` actor using Fast64-Gart's armature GeoLayout operator and `combined_export` settings.
7. Generate a retarget map from the actual post-transfer bone rest rotations
   and Fast64-Gart animation-node traversal through `is_bone_animatable()`. 

The workflow artifact `CJ64-rigged-actor` is intended to contain the
installable actor ZIP, editable Blender scene, rest-pose preview, validation
report, and generated retarget map. The generated animation tables are not
included because they are derived from the owner's commercial `ped.ifp`.

The previous rig-transfer preview covered 1,630 vertices across 15 deform
groups. The updated single-influence/Fast64-Gart export path is a new build and
must pass CI and visual inspection before being treated as complete.

## Remaining work

1. Visually inspect the rigged rest pose and the original GTA animation poses.
2. Correct the weighting and retarget basis wherever the previews show errors.
3. Verify the new Fast64 `cj_geo` export and correct any CI or export errors.
4. Include/load the private Lua animation module and map its roles to native
   Mario action states without changing `MarioState`, movement, collision,
   or camera.
5. Test idle, walk, run, jump, fall, land, and swim in SM64CoopDX on Android.

The last verified static DynOS actor remains unchanged. The updated rigged actor workflow now attempts a Fast64-Gart export, but it must not be described as a working in-game animation integration until CI, visual pose review, and Android runtime tests succeed.
