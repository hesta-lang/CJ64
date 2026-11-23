-- CJ64 - Carl Johnson visual replacement for SM64CoopDX
-- 0.1.0-alpha
CJ64 = CJ64 or {}
CJ64.name = "CJ64"
CJ64.version = "0.1.0-alpha"
CJ64.riggedActor = CJ64.riggedActor == true
CJ64.animationTablesLoaded = CJ64.animationTablesLoaded == true

-- A rigged actor marker is generated only in the experimental skinned package.
local rigOk = pcall(require, "rigged_actor")
if not rigOk and CJ64.riggedActor ~= true then
    CJ64.riggedActor = false
end

-- This module is kept private because its keyframes are derived from the
-- user's GTA San Andreas ped.ifp file.
local animationOk = pcall(require, "cj64_gta_animations")
if type(CJ64_GTA_ANIMATIONS) == "table" then
    CJ64.animationTablesLoaded = true
end

-- The entry point must explicitly load the controller; SM64CoopDX does not
-- automatically execute every sibling Lua file in the mod directory.
local characterOk, characterError = pcall(require, "character")
if not characterOk then
    print("[CJ64] ERROR loading character controller: " .. tostring(characterError))
end

print("[CJ64] " .. CJ64.name .. " " .. CJ64.version .. " loaded.")
if not CJ64.riggedActor then
    print("[CJ64] WARNING: rigged_actor.lua did not load; GTA animation playback is disabled.")
elseif not CJ64.animationTablesLoaded then
    print("[CJ64] WARNING: cj64_gta_animations.lua did not load; using native Mario animations.")
else
    print("[CJ64] Rigged CJ model and GTA San Andreas animation tables loaded.")
end
