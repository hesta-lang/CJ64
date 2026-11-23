-- Test the production animation reassertion guard without starting the game.
E_MODEL_NONE = 0
E_MODEL_ERROR_MODEL = -1
HOOK_MARIO_UPDATE = 1
HOOK_ON_LEVEL_INIT = 2
function hook_event() end
function smlua_model_util_get_id() return 123 end

dofile("character.lua")

local guard = CJ64.character.should_reassert_animation
assert(type(guard) == "function", "character controller did not expose its reassertion guard")

-- Getter is unavailable: set once on initial role, but don't restart each update.
assert(guard(false, nil, "cj64_anim_idle", nil, "idle", nil) == true)
assert(guard(false, nil, "cj64_anim_idle", "idle", "idle", "cj64_anim_idle") == false)
-- A role transition still starts the new clip.
assert(guard(false, nil, "cj64_anim_walk", "idle", "walk", "cj64_anim_idle") == true)

-- Getter is available: compare the actual clip every update and restore only on mismatch.
assert(guard(true, "cj64_anim_idle", "cj64_anim_idle", "idle", "idle", "cj64_anim_idle") == false)
assert(guard(true, "mario_idle", "cj64_anim_idle", "idle", "idle", "cj64_anim_idle") == true)
print("CJ64 animation reassertion guard tests passed.")
