# CJ DynOS actor

Required runtime model name: `cj_geo`.

The supplied source asset is a rigged FBX with 58 bones and four textures. It is not yet a DynOS actor. Add the source FBX and texture maps under `assets/cj/source/` and follow [the model conversion guide](../../docs/MODEL_IMPORT.md).

The final actor must be weighted to the **native SM64CoopDX Mario Armature** and exported with the compatible Fast64 GeoLayout exporter. The model must use the same skeleton that drives the existing Mario player object.

The replacement script only changes the model assigned to the existing `marioObj`. It does not create another physical body, skeleton controller, camera or collision body.

Original GTA San Andreas IFP clips must first be converted to the CJ FBX rig and then retargeted/baked to Mario's armature. SM64CoopDX does not load GTA IFP files directly. See [the animation guide](../../docs/ANIMATIONS.md).

No compiled `cj_geo` DynOS actor or playable CJ animation set is included yet.
