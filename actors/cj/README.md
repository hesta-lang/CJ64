# CJ CS DynOS actor

Active model filename: `mario_geo.bin`; SM64CoopDX registers the custom actor alias as `mario_geo`.

The normal model contains 20 animated-part nodes. Its layout is compatible with Mario's native player model structure, but the mesh is not a full 58-bone GTA San Andreas skin. Fine finger, toe, breast and belly motions therefore cannot be independently reproduced.

`mario_wingcap_geo.bin` is the separate Jetpack accessory model. It is not yet attached to CJ and does not implement flight or fuel logic.

The scale workflow increases both root GeoLayouts to 0.39. This is an initial 1.5x size increase; it is not a verified 280-unit measurement.

The original CS ZIP contains compiled DynOS binaries and textures but no editable `model.inc.c`, `geo.inc.c`, or animation source files.
