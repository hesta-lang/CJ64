# CS actor transform diagnosis

The 0.1.5-alpha test package was inspected directly, rather than assuming the repository baseline Lua was the installed package. Its main.lua reports version 0.1.5-alpha and sets CJ64.useGTAAnimations = true; the calibration report contains 13 clips.

The new transform inspector reads the compiled CS DynOS actor and checks the GeoLayout command path to the Body animated part, root scale, static rotations above Body, and nearest animated-part parent index for all 20 animated nodes. The reference contains non-animated helper nodes (Cap State Switch, 2 Torso Rotation, Left Hand Switch, Right Hand Switch); the diagnostic resolves these to their nearest animated ancestors before comparing hierarchy.

For the inspected mario_geo.bin from 0.1.5-alpha, the report finds: 20 animated parts; all nearest animated-parent indices match the Fast64/Mario reference; root scale 0.39; no static rotation node above Body; Body root translation [0, 43, 0]. The other non-zero static GeoLayout rotations are small local offsets (under 0.74 degrees), not a global quarter-turn.

Interpretation: the binary GeoLayout does not contain a global static rotation that could explain CJ being horizontal. Changing the model root rotation is not a supported fix based on this evidence. The test also does not prove that display-list vertices have the same local axis/rest basis as the FBX/Fast64 skeleton: that information is not fully recoverable from this GeoLayout traversal. The next high-priority target is the GTA-to-CS local rotation/rest-pose basis and actual runtime clip selection, not the actor root scale or animated-node hierarchy.

The Inspect CJ64 CS actor transforms workflow runs regression tests and publishes the JSON diagnostic. It deliberately performs no geometry or rotation changes.
