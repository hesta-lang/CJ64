# CJ model import

Source file: `CarlJohnson-GTASA.FBX`, accompanied by `head.png`, `upper body.png`, `legs.png` and `shoes.png`. The FBX contains a 58-bone rig and skin clusters. It is still an authoring source, not a DynOS actor.

Use the official SM64CoopDX character template and a compatible Fast64 fork. The CJ mesh must be parented to the Mario Armature and assigned to its vertex groups, then exported as a DynOS actor in `actors/cj/` with runtime model name `cj_geo`.

The mod's chosen architecture keeps MarioState and the original `marioObj` as the single physical player. Therefore a separate GTA skeleton in-game would not be driven by the native Mario animation system. Retarget the mesh and bake animations onto Mario's skeleton instead.

Source credit: Carl Johnson (CJ), by Tsaphnat (Tsaphnat Mbuyi), Sketchfab, CC BY 4.0. See `assets/cj/source/README.md`.
