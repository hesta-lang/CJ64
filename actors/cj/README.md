# CJ DynOS actor

Required runtime model name: `cj_geo`.

The rig-transfer workflow produced an experimental skinned DynOS actor in successful CI run [#71](https://github.com/hesta-lang/CJ64/actions/runs/45089345497). The package contains the CJ mesh on the 20-node Mario/Fast64-Gart hierarchy at 280 SM64 units. CI verified 1,630 vertices, one deform-bone influence at weight 1.0 per vertex, no invalid weights, and no nearest-bone fallback. The ZIP and editable Blender scene are workflow artifacts; the source FBX is still an authoring asset.

## Runtime architecture

The mesh is exported against the native Mario armature. CJ's original 58-bone skeleton is not used as an independent runtime skeleton.

The replacement script only changes the model assigned to the existing `marioObj`. It does not create another physical body, skeleton controller, camera or collision body. `MarioState`, movement, collision, camera, actions, and physics remain authoritative.

## Experimental original GTA animations

The owner-provided `ped.ifp` was parsed and 13 clips were retargeted to the current 20-node map. The generated module is bundled as `cj64_gta_animations.lua` with the rigged actor in the experimental package. The IFP itself is not included.

The selected clips include idle, walk, run, jump, fall, land, swim, and a generic civilian sprint candidate (`sprint_civi`). The module and actor have passed structural CI checks only; rest and animated poses have not yet been approved visually or tested in-game. The controller has a safe guard and will not activate with the old static actor.

See [the animation guide](../../docs/ANIMATIONS.md) and [retarget plan](../../docs/RETARGET_PLAN.md).
