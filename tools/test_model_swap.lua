local hooks = {}
local actorAvailable = false
local packEnabled = false
local packEnableCalls = 0
local setterCalls = 0

E_MODEL_NONE = 0
E_MODEL_ERROR_MODEL = -1
HOOK_MARIO_UPDATE = "mario_update"
HOOK_ON_LEVEL_INIT = "level_init"
function print() end
function hook_event(name, fn) hooks[name] = fn end
function dynos_pack_get_count() return 1 end
function dynos_pack_get_name(index)
    assert(index == 0)
    return "CJ64"
end
function dynos_pack_get_enabled(index)
    assert(index == 0)
    return packEnabled
end
function dynos_pack_set_enabled(index, value)
    assert(index == 0 and value == true)
    packEnableCalls = packEnableCalls + 1
    packEnabled = value
end
function smlua_model_util_get_id(name)
    assert(name == "mario_geo")
    return actorAvailable and packEnabled and 900 or E_MODEL_NONE
end
function obj_get_model_id_extended(obj) return obj.modelId or 1 end
function obj_set_model_extended(obj, id)
    setterCalls = setterCalls + 1
    obj.modelId = id
end

dofile("character.lua")
local c = CJ64.character
assert(type(hooks[HOOK_MARIO_UPDATE]) == "function")
local objA = { modelId = 1 }
local mA = { playerIndex = 0, marioObj = objA }
c.apply(mA)
assert(packEnabled == true and packEnableCalls == 1, "must enable the CJ64 DynOS pack")
assert(objA.modelId == 1 and setterCalls == 0)

actorAvailable = true
assert(c.try_register(true))
c.apply(mA)
assert(objA.modelId == 900 and setterCalls == 1)
c.apply(mA)
assert(setterCalls == 1, "must not redundantly set model each frame")

local objB = { modelId = 1 }
c.apply({ playerIndex = 1, marioObj = objB })
assert(objB.modelId == 900 and setterCalls == 2)

local respawned = { modelId = 1 }
c.apply({ playerIndex = 0, marioObj = respawned })
assert(respawned.modelId == 900 and setterCalls == 3)

c.reset()
assert(next(c.applied) == nil)
print("CJ64 model replacement tests passed.")
