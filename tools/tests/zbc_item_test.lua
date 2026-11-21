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

-- a normal run ends after the motion's length: the hand motion is stopped (never left cycling), controls back
do
	local chunk = assert(loadfile("optional/bodycam_item/gamedata/scripts/zbc_item_anim.script"))
	local locked, stopped, played = nil, 0, 0
	local actor = {
		alive = function() return true end,
		active_slot = function() return 0 end,
		active_detector = function() return nil end,
		active_item = function() return nil end,
		activate_slot = function() end,
	}
	local A = setmetatable({
		db = { actor = actor },
		game = {
			only_allow_movekeys = function(v) locked = v end,
			play_hud_motion = function() played = played + 1 end,
			get_motion_length = function() return 1000 end,
			stop_hud_motion = function() stopped = stopped + 1 end,
		},
		level = {},
		printf = function() end,
		time_global = function() return 0 end,
	}, { __index = _G })
	setfenv(chunk, A)
	chunk()
	A.request("dead", 0)
	A.update(0, true)
	A.update(10, true)
	check(played == 1 and locked == true, "the animation plays once, movement keys only")
	A.update(500, true)
	check(stopped == 0 and locked == true, "still playing halfway through")
	A.update(1100, true)
	check(stopped == 1 and locked == false, "after its length the hand motion is stopped and controls return")
	A.update(5000, true)
	check(played == 1, "it is not played again")
end

-- an engine call that fails mid-animation releases the movement lock and gives the weapon back
do
	local chunk = assert(loadfile("optional/bodycam_item/gamedata/scripts/zbc_item_anim.script"))
	local locked, slot_back, logged = nil, nil, false
	local actor = {
		alive = function() return true end,
		active_slot = function() return 2 end,
		active_detector = function() return nil end,
		active_item = function() return nil end,
		activate_slot = function(_, s) slot_back = s end,
	}
	local A = setmetatable({
		db = { actor = actor },
		game = {
			only_allow_movekeys = function(v) locked = v end,
			play_hud_motion = function() error("no such motion") end,
		},
		level = {},
		printf = function() logged = true end,
		time_global = function() return 0 end,
	}, { __index = _G })
	setfenv(chunk, A)
	chunk()
	A.request("dead", 0)
	A.update(0, true)          -- puts the weapon away, locks to movement keys
	check(locked == true, "animation start locks to movement keys")
	A.update(10, true)         -- weapon gone: plays, the engine call fails
	check(locked == false, "a failing animation releases the movement lock")
	check(slot_back == 2, "a failing animation gives the weapon back")
	check(logged, "a failing animation is logged")
	A.update(20, true)
	check(locked == false, "nothing is retried after a failure")
end

-- zbc_item_anim.reset(): safe cleanup only (never calls activate_slot or det:switch_state)
-- and holster wait checks actor:active_detector() == nil
do
	local chunk = assert(loadfile("optional/bodycam_item/gamedata/scripts/zbc_item_anim.script"))
	local locked, ladder, fov_restored, stopped, played = nil, nil, 0, 0, 0
	local slot_restores, det_states = 0, {}
	local active_det, active_item = nil, nil
	local det_obj = {
		id = function() return 77 end,
		parent = function() return { id = function() return 0 end } end,
		switch_state = function(_, st) det_states[#det_states + 1] = st end,
	}
	active_det = det_obj
	local actor = {
		alive = function() return true end,
		active_slot = function() return 2 end,
		active_detector = function() return active_det end,
		active_item = function() return active_item end,
		activate_slot = function(_, s) if s ~= 0 then slot_restores = slot_restores + 1 end end,
	}
	local A = setmetatable({
		AC_ID = 0,
		db = { actor = actor },
		level = { object_by_id = function(id) return id == 77 and det_obj or nil end },
		game = {
			only_allow_movekeys = function(v) locked = v end,
			set_actor_allow_ladder = function(v) ladder = v end,
			play_hud_motion = function() played = played + 1 end,
			get_motion_length = function() return 1000 end,
			stop_hud_motion = function() stopped = stopped + 1 end,
		},
		fov_anim_manager = {
			change_fov = function() return true end,
			restore_fov = function() fov_restored = fov_restored + 1 end,
		},
		printf = function() end,
		time_global = function() return 0 end,
	}, { __index = _G })
	setfenv(chunk, A)
	chunk()

	A.request("insert", 0)
	A.update(0, true)
	check(det_states[1] == 2 and played == 0, "begin hides detector and waits in holster phase")
	-- still holding detector even though active_item() == nil
	A.update(10, true)
	check(played == 0, "holster wait does not play while active_detector() is still present")
	active_det = nil
	A.update(20, true)
	check(played == 1, "plays once both active_item() and active_detector() are nil")

	-- reset() mid-playing does safe cleanup ONLY without restoring slot or detector
	A.reset()
	check(stopped == 1 and locked == false and ladder == true and fov_restored == 1, "reset cleans up motion, locks, ladder, and FOV")
	check(slot_restores == 0 and #det_states == 1, "reset does not call activate_slot or det:switch_state(1)")
	check(A.holding_power() == false, "reset clears power hold")
end

-- zbc_item.script: warned_low silent load seeding, camera swap seeding, drain gating, parent check, enabled=false skip
do
	local cbs = {}
	local now_ms = 1000
	local mcm_enabled = true
	local holding = false
	local anim_updates = 0
	local alerts = 0
	local cam1_cond, cam1_parent = 0.08, 0
	local cam2_cond, cam2_parent = 0.09, 0
	local active_cam_id = 101

	local function make_obj(id, get_cond, set_cond, get_parent)
		return {
			id = function() return id end,
			section = function() return "zbc_bodycam_item" end,
			condition = get_cond,
			set_condition = set_cond,
			parent = function() return get_parent() and { id = get_parent } or nil end,
		}
	end
	local obj1 = make_obj(101, function() return cam1_cond end, function(_, c) cam1_cond = c end, function() return cam1_parent end)
	local obj2 = make_obj(102, function() return cam2_cond end, function(_, c) cam2_cond = c end, function() return cam2_parent end)

	local actor = {
		iterate_inventory = function(_, fn, ctx)
			if active_cam_id == 101 and cam1_parent == 0 then fn(ctx, obj1) end
			if active_cam_id == 102 and cam2_parent == 0 then fn(ctx, obj2) end
		end,
	}

	local G = load_script({
		AC_ID = 0,
		db = { actor = actor },
		time_global = function() return now_ms end,
		level = { object_by_id = function(id) return (id == 101 and obj1) or (id == 102 and obj2) or nil end },
		ui_mcm = { get = function(k) if k == "zone_bodycam/enabled" then return mcm_enabled end return nil end },
		item_device = { get_power_critical = function() return 0.05 end },
		game_difficulties = { get_eco_factor = function() return 1 end },
		actor_menu = { set_msg = function() end },
		game = { translate_string = function(s) return s end },
		sound_object = function() return { play = function() end } end,
		zbc_bodycam = { set_power_gate = function() end, set_battery_source = function() end },
		zbc_item_anim = {
			holding_power = function() return holding end,
			is_insert = function() return false end,
			request = function() end,
			reset = function() end,
			update = function() anim_updates = anim_updates + 1 end,
		},
		RegisterScriptCallback = function(name, fn) cbs[name] = fn end,
		printf = function() end,
	})
	G.low_battery_alert = function() alerts = alerts + 1; return true end
	G.on_game_start()

	-- Load at 8% battery: silently seeds warned_low = 1, zero alerts
	cbs.actor_on_first_update()
	check(alerts == 0, "loading a save at 8% battery does not trigger a false low-battery alert")

	-- Drains while powered; at 6% the second warning fires
	now_ms = 1500
	cbs.actor_on_update()
	check(alerts == 0, "no alert above 6% after silent seed")
	cam1_cond = 0.06
	now_ms = 2000
	cbs.actor_on_update()
	check(alerts == 1, "6% warning still fires after silent 10% seed on load")

	-- While holding_power() == true, battery does not drain
	holding = true
	local before_hold = cam1_cond
	now_ms = 2500
	cbs.actor_on_update()
	check(cam1_cond == before_hold, "battery does not drain while holding_power() is true")
	holding = false

	-- Switching cameras to a 9% camera seeds warned_low silently without false alert
	active_cam_id = 102
	cbs.actor_on_item_take()
	now_ms = 3000
	cbs.actor_on_update()
	check(alerts == 1, "swapping to a 9% camera seeds warned_low silently")

	-- Dropped / non-actor parent returns nil from battery_level()
	cam2_parent = 999
	check(G.battery_level() == nil, "battery_level() returns nil when parent is not AC_ID")

	-- Disabling zone_bodycam skips zbc_item_anim.update() and resets last_t / last_charge
	local anim_reqs = 0
	cam2_parent = 0
	cam2_cond = 0.50
	G.zbc_item_anim.is_insert = function(prev, cur) return prev and cur and (cur - prev > 0.02) end
	G.zbc_item_anim.request = function(w) if w == "insert" then anim_reqs = anim_reqs + 1 end end
	mcm_enabled = false
	cbs.on_option_change()
	local prev_anim = anim_updates
	now_ms = 3500
	cbs.actor_on_update()
	check(anim_updates == prev_anim, "zbc_item_anim.update() skipped when zone_bodycam/enabled == false")

	-- Re-enabling after 1 hour + battery swap without main_menu_on_quit: no drain spike, no phantom insert anim
	cam2_cond = 1.00
	now_ms = 3500 + 3600000
	mcm_enabled = true
	cbs.on_option_change()
	cbs.actor_on_update()
	check(cam2_cond == 1.00, "re-enabling without main_menu_on_quit causes no drain spike")
	check(anim_reqs == 0, "battery swapped while disabled does not trigger delayed insert animation")
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_item_test: all checks passed")
