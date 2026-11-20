-- Tests the pure battery logic of the optional bodycam item (optional/bodycam_item/.../zbc_item.script)
-- and that the component hands its power gate to zbc_bodycam.script on game start.
--
-- Usage (from the repo root): lua tools/tests/zbc_item_test.lua

local PATH = "optional/bodycam_item/gamedata/scripts/zbc_item.script"

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end
local function near(a, b, eps) return math.abs(a - b) <= (eps or 1e-9) end

-- load the script in its own environment, like the engine does for a script namespace
local function load_script(globals)
	local chunk = assert(loadfile(PATH))
	local env = setmetatable(globals or {}, { __index = _G })
	setfenv(chunk, env)
	chunk()
	return env
end

local M = load_script()

-- clamp_hours
check(M.clamp_hours(4) == 4, "clamp_hours keeps 4")
check(M.clamp_hours("2.5") == 2.5, "clamp_hours reads strings")
check(M.clamp_hours(nil) == 4, "clamp_hours defaults nil to 4")
check(M.clamp_hours(0) == 0.25, "clamp_hours lower bound")
check(M.clamp_hours(1000) == 48, "clamp_hours upper bound")
check(M.clamp_hours(0 / 0) == 4, "clamp_hours rejects NaN")

-- drain_step: a full charge lasts exactly `hours` of 1 s steps
do
	local c, steps = 1, 0
	while c > 0 and steps < 10 * 3600 do
		c = M.drain_step(c, 1000, 1, 1)
		steps = steps + 1
	end
	check(steps == 3600, "1 hour battery empties in 3600 one-second steps, got " .. steps)
end
check(near(M.drain_step(1, 500, 4, 1), 1 - 0.5 / (4 * 3600)), "half-second step on a 4 h battery")
check(near(M.drain_step(1, 1000, 4, 2), 1 - 2 / (4 * 3600)), "difficulty factor doubles the drain")
check(M.drain_step(0.5, 1000, 4, 0) == 0.5, "factor 0 never drains")
check(M.drain_step(0.5, 1000, 4, -3) == 0.5, "negative factor is treated as 0")
check(M.drain_step(0.5, 0, 4, 1) == 0.5, "no time, no drain")
check(M.drain_step(0.5, -20, 4, 1) == 0.5, "negative time, no drain")
check(M.drain_step(0.5, 5000, 4, 1) == 0.5, "loading hitches (over 1 s) are not drained")
check(M.drain_step(0.00001, 1000, 0.25, 1) == 0, "charge never goes below 0")
check(M.drain_step(nil, 1000, 4, 1) == 0, "nil charge reads as 0")

-- is_charged
check(M.is_charged(0.5, 0.05) == true, "half charge works")
check(M.is_charged(0.05, 0.05) == false, "at the critical level the camera is off")
check(M.is_charged(0.04, nil) == false, "default critical level is 0.05")
check(M.is_charged(0.06, nil) == true, "just above the default critical level")
check(M.is_charged(nil, 0.05) == false, "no charge value means off")

-- best_index
check(M.best_index({}) == nil, "no cameras, no pick")
check(M.best_index({ 0.2, 0.9, 0.5 }) == 2, "picks the fullest camera")
check(M.best_index({ 0.3, 0.3 }) == 1, "ties keep the first")
check(M.best_index({ "x", 0.1 }) == 2, "skips bad values")

-- on_game_start: registers the gate with the base mod and the callbacks it needs
do
	local gate_fn, callbacks = nil, {}
	local G = load_script({
		zbc_bodycam = { set_power_gate = function(fn) gate_fn = fn end },
		RegisterScriptCallback = function(name, fn) callbacks[name] = fn end,
		printf = function() end,
	})
	G.on_game_start()
	check(type(gate_fn) == "function", "on_game_start registers the power gate")
	check(gate_fn and gate_fn() == false, "no camera carried: no power before the first update")
	for _, name in ipairs({ "actor_on_first_update", "actor_on_update", "actor_on_item_take",
		"actor_on_item_drop", "on_option_change" }) do
		check(type(callbacks[name]) == "function", "registers " .. name)
	end
end

-- on_game_start without the base mod: warns, never errors
do
	local warned = false
	local G = load_script({
		zbc_bodycam = false,
		RegisterScriptCallback = function() end,
		printf = function() warned = true end,
	})
	local ok = pcall(G.on_game_start)
	check(ok and warned, "missing base mod only prints a warning")
end

-- on_game_start: hands the battery gauge its charge source when the base mod has the hook
do
	local src = nil
	local G = load_script({
		zbc_bodycam = { set_power_gate = function() end, set_battery_source = function(fn) src = fn end },
		RegisterScriptCallback = function() end,
		printf = function() end,
	})
	G.on_game_start()
	check(type(src) == "function", "on_game_start registers the battery source")
	check(src and src() == nil, "no camera carried: no battery level")
end

-- has_power: off while a battery-insert animation still holds the power
do
	local G = load_script({ zbc_item_anim = { holding_power = function() return true end } })
	check(G.has_power() == false, "has_power is false with no charged camera")
end

-- hand animations (zbc_item_anim.script): pure logic
do
	local chunk = assert(loadfile("optional/bodycam_item/gamedata/scripts/zbc_item_anim.script"))
	local A = setmetatable({}, { __index = _G })
	setfenv(chunk, A)
	chunk()

	check(A.is_insert(0.04, 1.0) == true, "a fresh battery on a dead camera is an insert")
	check(A.is_insert(0.5, 0.9) == true, "a fresh battery on a half camera is an insert")
	check(A.is_insert(0.5, 0.5 - 1e-4) == false, "draining is not an insert")
	check(A.is_insert(0.5, 0.51) == false, "a tiny rise is not an insert")
	check(A.is_insert(nil, 1.0) == false, "no previous charge: not an insert (first look, new camera)")

	check(A.next_queue(nil, "dead") == "dead", "dead queues on an empty queue")
	check(A.next_queue("dead", "insert") == "insert", "a new battery replaces a pending dead animation")
	check(A.next_queue("insert", "dead") == "insert", "dead never replaces a pending insert")
	check(A.next_queue(nil, "bogus") == nil, "unknown kinds queue nothing")

	check(A.power_held(nil, 1000, nil) == false, "no hold, power free")
	check(A.power_held(1000, 2000, nil) == true, "insert pending: power held")
	check(A.power_held(1000, 2000 + A.HOLD_MAX_MS, nil) == false, "a hold that never played expires")
	check(A.power_held(1000, 5000, 4000) == true, "playing, before the camera is on the chest: held")
	check(A.power_held(1000, 4000 + A.POWER_AT_MS, 4000) == false, "camera on the chest: power back")
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_item_test: all checks passed")
