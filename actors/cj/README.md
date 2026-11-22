# CJ DynOS actor

Required runtime model name: `cj_geo`.

The supplied source asset is a rigged FBX with 58 bones and four textures. It is not yet a DynOS actor. Add the source FBX and texture maps under `assets/cj/source/` and follow [the model conversion guide](../../docs/MODEL_IMPORT.md).

## Animation setup for the first playable version

Use the **native SM64CoopDX Mario animations** for now. Do not register custom CJ/GTA animation tables and do not add a second animation controller.

The final runtime mesh must be driven by the native **Mario Armature**. Reassign the CJ mesh weights to the matching Mario vertex groups, parent the mesh to that armature, and export the armature's GeoLayout. The original 58-bone GTA armature must not remain as an independent runtime skeleton.

The replacement script only changes the model assigned to the existing `marioObj`. It does not create another physical body, skeleton controller, camera or collision body. MarioState and the engine's normal action/animation selection remain authoritative.

## Later: original CJ animations

Original GTA San Andreas IFP clips are deferred until a legitimate source file is available. They must be retargeted and baked to the Mario Armature before integration. SM64CoopDX does not load GTA IFP files directly. See [the animation guide](../../docs/ANIMATIONS.md).

No compiled `cj_geo` DynOS actor is included yet.
