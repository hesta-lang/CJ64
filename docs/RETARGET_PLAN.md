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

## First-pass rig transfer

The rig-transfer workflow
`.github/workflows/cj-rig-transfer.yml` uses the inspected dual-rig Blender
artifact and `tools/prepare_cj_rig_transfer.py`.

The first successful transfer:
- Keeps the CJ mesh and its original material/UV data.
- Converts source coordinates into the Mario/Fast64 armature coordinate
  system and scales the model to 280 SM64 units.
- Repositions the Mario animation bones using corresponding CJ rest matrices.
- Generates nearest-bone-segment weights for 15 deform groups.
- Assigns weights to all 1,630 CJ vertices.
- Reports evaluated mesh dimensions of approximately
  `[2.800, 2.771, 0.576]` Blender units.

The workflow artifact `CJ64-rig-transfer-preview` contains the editable
`CJ64-CJ-Rig-Transfer.blend` and validation JSON. This is not yet a Fast64
DynOS export and has not been tested in game. Nearest-segment weights are a
first-pass approximation; inspect deformations before accepting the rig.

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
