-- Regression test for gamedata/scripts/zbc_allies.script aim_target_ok(): the aimed-at object (a
-- barrel, crate, artefact or stash) must never get alive() called on it unless it is a stalker or a
-- monster. On anything else the engine logs "CSciptEntity [...]: cannot access class member Alive!"
-- with a stack through zbc_bodycam.script, every frame the camera points at it while it is powered.
--
-- Usage (from the repo root): lua tools/tests/zbc_allies_aim_target_test.lua

local PATH = "gamedata/scripts/zbc_allies.script"

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end

local alive_on_non_creature = 0

-- fake game_object: kind = "stalker" | "monster" | "physic"
local function obj(kind, opts)
	opts = opts or {}
	local o = { kind = kind }
	function o:id() return opts.id or 100 end
	function o:section() return opts.section or kind end
	function o:clsid() return nil end
	function o:alive()
		if self.kind ~= "stalker" and self.kind ~= "monster" then
			alive_on_non_creature = alive_on_non_creature + 1
			return false
		end
		return opts.alive ~= false
	end
	function o:relation() return opts.relation or 1 end
	return o
end

local env = setmetatable({
	IsStalker = function(o) return o.kind == "stalker" end,
	IsMonster = function(o) return o.kind == "monster" end,
	game_object = { enemy = 2, neutral = 1, friend = 0 },
}, { __index = _G })
local chunk = assert(loadfile(PATH))
setfenv(chunk, env)
local ok, err = pcall(chunk)
check(ok, "script loads: " .. tostring(err))
local f = rawget(env, "aim_target_ok")
check(type(f) == "function", "aim_target_ok exists")

if type(f) == "function" then
	local actor = obj("stalker", { id = 0 })
	for _, mut in ipairs({ true, false }) do
		for _, enemies in ipairs({ true, false }) do
			check(f(obj("physic"), actor, mut, enemies) == false, "a physics object is never a target")
		end
	end
	check(alive_on_non_creature == 0, "alive() never called on a non-creature (called "
		.. alive_on_non_creature .. " times)")

	check(f(obj("stalker"), actor, false, false) == true, "a friendly stalker is a target")
	check(f(obj("stalker", { alive = false }), actor, false, true) == false, "a dead stalker is not")
	check(f(obj("stalker", { relation = 2 }), actor, false, false) == false, "an enemy, enemies off: not")
	check(f(obj("stalker", { relation = 2 }), actor, false, true) == true, "an enemy, enemies on: a target")
	check(f(obj("monster"), actor, true, true) == true, "a monster with mutants on is a target")
	check(f(obj("monster"), actor, false, true) == false, "a monster with mutants off is not")
	check(f(obj("stalker", { id = 0 }), actor, true, true) == false, "the actor (id 0) is not")
	check(f(nil, actor, true, true) == false, "nothing aimed at: no target")
	check(f(obj("monster", { section = "zombie_ghost" }), actor, true, true) == false, "a ghost is not")
end

if failures == 0 then
	print("zbc_allies_aim_target_test: all passed")
else
	print(("zbc_allies_aim_target_test: %d failure(s)"):format(failures))
	os.exit(1)
end
