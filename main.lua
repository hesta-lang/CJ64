-- CJ64 - CS DynOS model port for SM64CoopDX
CJ64 = CJ64 or {}
CJ64.name = "CJ64"
CJ64.version = "0.1.2-alpha"
CJ64.csActor = true
CJ64.animationTablesLoaded = false

-- The GTA animation table is private because its keyframes are derived from
-- the user's ped.ifp file. Its 20 channels are calibrated for the CS actor.
local animationOk, animationError = pcall(require, "cj64_gta_animations")
if type(CJ64_GTA_ANIMATIONS) == "table"
    and type(CJ64_GTA_ANIMATIONS.set_for_role) == "function" then
    CJ64.animationTablesLoaded = true
elseif not animationOk then
    print("[CJ64] GTA animation module unavailable: " .. tostring(animationError))
end

-- SM64CoopDX does not automatically execute every sibling Lua file.
local characterOk, characterError = pcall(require, "character")
if not characterOk then
    print("[CJ64] ERROR loading character controller: " .. tostring(characterError))
end

print("[CJ64] " .. CJ64.name .. " " .. CJ64.version .. " loaded.")
if CJ64.animationTablesLoaded then
    print("[CJ64] CS 20-node actor and calibrated GTA animation tables loaded.")
else
    print("[CJ64] GTA animation tables unavailable; SM64CoopDX animations remain active.")
end
