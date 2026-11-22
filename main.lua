-- CJ64 - Carl Johnson visual replacement for SM64CoopDX
-- 0.1.0-alpha
CJ64 = CJ64 or {}
CJ64.name = "CJ64"
CJ64.version = "0.1.0-alpha"
CJ64.riggedActor = CJ64.riggedActor == true
CJ64.animationTablesLoaded = CJ64.animationTablesLoaded == true

-- A rigged actor marker is generated only in the experimental skinned package.
local rigOk = pcall(require, "rigged_actor")
if not rigOk then
    CJ64.riggedActor = false
end

-- This module is kept private because its keyframes are derived from the
-- user's GTA San Andreas ped.ifp file.
local animationOk = pcall(require, "cj64_gta_animations")
if animationOk and type(CJ64_GTA_ANIMATIONS) == "table" then
    CJ64.animationTablesLoaded = true
end

print("[CJ64] " .. CJ64.name .. " " .. CJ64.version .. " loaded.")
if CJ64.riggedActor and CJ64.animationTablesLoaded then
    print("[CJ64] Original GTA animation tables loaded; waiting for the skinned actor.")
end
