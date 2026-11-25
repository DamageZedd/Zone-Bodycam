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

-- actor dying during holster phase aborts immediately, cleans up locks, and never plays on corpse
do
	local chunk = assert(loadfile("optional/bodycam_item/gamedata/scripts/zbc_item_anim.script"))
	local locked, played, is_alive = nil, 0, true
	local actor = {
		alive = function() return is_alive end,
		active_slot = function() return 2 end,
		active_detector = function() return nil end,
		active_item = function() return {} end,
		activate_slot = function() end,
	}
	local A = setmetatable({
		db = { actor = actor },
		level = {},
		game = {
			only_allow_movekeys = function(v) locked = v end,
			play_hud_motion = function() played = played + 1 end,
		},
		printf = function() end,
		time_global = function() return 0 end,
	}, { __index = _G })
	setfenv(chunk, A)
	chunk()

	A.request("dead", 0)
	A.update(0, true)
	check(locked == true, "holster locks movekeys")
	is_alive = false
	A.update(3000, true)
	check(locked == false and played == 0, "dying during holster unlocks movekeys and never plays animation")
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

---------------------------------------------------------------------------------------------------
-- 5-Generation Axon Body Suite: CAMERAS table, tie-breaking, hysteresis, drain_mult, HUD routing,
-- OSD watermark hook, LTX/DLTX/trade configs, and 3D/DDS asset checks
---------------------------------------------------------------------------------------------------

-- CAMERAS & CAMERA_ORDER contract
do
	check(M.ITEM_SECTION == "zbc_bodycam_item", "ITEM_SECTION stays zbc_bodycam_item for save compatibility")
	check(type(M.CAMERA_ORDER) == "table" and #M.CAMERA_ORDER == 5, "CAMERA_ORDER lists all 5 cameras")
	local expected = {
		zbc_bodycam_1    = { gen = 1, hud = "zbc_bodycam_1_anim_hud", label = "AXON BODY",   drain_mult = 1.333 },
		zbc_bodycam_2    = { gen = 2, hud = "zbc_bodycam_2_anim_hud", label = "AXON BODY 2", drain_mult = 1.143 },
		zbc_bodycam_3    = { gen = 3, hud = "zbc_bodycam_3_anim_hud", label = "AXON BODY 3", drain_mult = 1.053 },
		zbc_bodycam_item = { gen = 4, hud = "zbc_bodycam_anim_hud",   label = "AXON BODY 4", drain_mult = 1.000 },
		zbc_bodycam_5    = { gen = 5, hud = "zbc_bodycam_5_anim_hud", label = "AXON BODY 5", drain_mult = 0.833 },
	}
	for sec, exp in pairs(expected) do
		local got = M.CAMERAS and M.CAMERAS[sec]
		check(type(got) == "table", "CAMERAS has " .. sec)
		if got then
			check(got.gen == exp.gen, sec .. " gen")
			check(got.hud == exp.hud, sec .. " hud section")
			check(got.label == exp.label, sec .. " OSD label")
			check(near(got.drain_mult, exp.drain_mult, 1e-6), sec .. " drain_mult")
		end
	end
end

-- best_index(charges, gens): generation tie-breaking
do
	check(M.best_index({ 1.0, 1.0 }, { 1, 5 }) == 2, "tie at 100% picks higher generation (Body 5 over Gen 1)")
	check(M.best_index({ 1.0, 1.0, 1.0 }, { 2, 5, 4 }) == 2, "tie across 3 cameras picks Body 5 regardless of order")
	check(M.best_index({ 1.0, 1.0 - 5e-7 }, { 1, 4 }) == 2, "within 1e-6 epsilon still breaks tie by generation")
	check(M.best_index({ 0.85, 0.80 }, { 1, 5 }) == 1, "meaningfully fuller Gen 1 (85%) beats 80% Body 5")
	check(M.best_index({ 0.5, 0.5 }, { 3, 3 }) == 1, "equal charge and equal gen keeps first")
end

-- Anti-ping-pong hysteresis, per-generation drain_mult, active_device_label(), and HUD section routing
do
	local cbs = {}
	local now_ms = 0
	local anim_calls = {}
	local items = {}

	local function add_cam(id, sec, cond)
		local o = { _cond = cond, _parent = 0 }
		function o:id() return id end
		function o:section() return sec end
		function o:condition() return self._cond end
		function o:set_condition(c) self._cond = c end
		function o:parent() return self._parent and { id = function() return self._parent end } or nil end
		items[#items + 1] = o
		return o
	end

	local c1 = add_cam(201, "zbc_bodycam_1", 1.0)
	local c5 = add_cam(205, "zbc_bodycam_5", 1.0)

	local by_id = { [201] = c1, [205] = c5 }
	local dev_src_fn = nil

	local G = load_script({
		AC_ID = 0,
		db = {
			actor = {
				iterate_inventory = function(_, fn, ctx)
					for i = 1, #items do
						if items[i]._parent == 0 then fn(ctx, items[i]) end
					end
				end,
			},
		},
		time_global = function() return now_ms end,
		level = { object_by_id = function(id) return by_id[id] end },
		ui_mcm = { get = function(k)
			if k == "zone_bodycam/enabled" then return true end
			if k == "zone_bodycam_item/battery_hours" then return 4 end
			return nil
		end },
		item_device = { get_power_critical = function() return 0.05 end },
		game_difficulties = { get_eco_factor = function() return 1 end },
		actor_menu = { set_msg = function() end },
		game = { translate_string = function(s) return s end },
		zbc_bodycam = {
			set_power_gate = function() end,
			set_battery_source = function() end,
			set_device_source = function(fn) dev_src_fn = fn end,
		},
		zbc_item_anim = {
			holding_power = function() return false end,
			is_insert = function(prev, cur) return prev and cur and (cur - prev > 0.02) end,
			request = function(what, t, hud) anim_calls[#anim_calls + 1] = { what = what, t = t, hud = hud } end,
			reset = function() end,
			update = function() end,
		},
		RegisterScriptCallback = function(name, fn) cbs[name] = fn end,
		printf = function() end,
	})
	G.on_game_start()
	check(type(dev_src_fn) == "function", "on_game_start registers set_device_source")

	-- Initial scan with both at 100%: Body 5 wins tie-break over Gen 1
	cbs.actor_on_first_update()
	check(G.active_device_label() == "AXON BODY 5", "100% tie selects Body 5 watermark")

	-- 1 second drain on Body 5: drains at 0.833x rate, and next scan does NOT flip-flop to Gen 1 (1.0)
	now_ms = 1000
	cbs.actor_on_update() -- seeds last_t = 1000
	now_ms = 2000
	cbs.actor_on_update() -- drains 1000 ms AND triggers scan() at next_scan == 1000
	local expected_c5 = 1.0 - (1 / (4 * 3600)) * 0.833
	check(near(c5._cond, expected_c5, 1e-9), "Body 5 drains with drain_mult = 0.833")
	check(c1._cond == 1.0, "inactive Gen 1 camera does not drain")

	now_ms = 3000
	cbs.actor_on_update() -- another scan() at 3000 ms; c5 is ~0.9999, within STICKY_EPS (0.002) of c1 (1.0)
	check(G.active_device_label() == "AXON BODY 5", "STICKY_EPS prevents ping-pong to 100% Gen 1 every second")

	-- Drop Body 5 to 0.50: Gen 1 (1.0) exceeds 0.50 + STICKY_EPS, so scan switches immediately to Gen 1
	c5._cond = 0.50
	now_ms = 4000
	cbs.actor_on_update()
	check(G.active_device_label() == "AXON BODY", "switches to Gen 1 once charge gap exceeds STICKY_EPS")
	local before_c1 = c1._cond
	now_ms = 5000
	cbs.actor_on_update()
	check(near(before_c1 - c1._cond, (1 / (4 * 3600)) * 1.333, 1e-9), "Gen 1 drains with drain_mult = 1.333")

	-- Remove Gen 1; drain Body 5 across critical threshold -> requests dead with zbc_bodycam_5_anim_hud
	c1._parent = nil
	c5._cond = 0.05001
	cbs.actor_on_item_drop()
	now_ms = 6000
	cbs.actor_on_update()
	check(G.has_power() == true and G.active_device_label() == "AXON BODY 5", "Body 5 active just above critical")
	c5._cond = 0.049
	now_ms = 6500
	cbs.actor_on_update()
	check(#anim_calls == 1 and anim_calls[1].what == "dead" and anim_calls[1].hud == "zbc_bodycam_5_anim_hud",
		"dead animation receives Body 5 HUD section")

	-- Insert fresh battery into Body 5 -> requests insert with zbc_bodycam_5_anim_hud
	c5._cond = 1.0
	now_ms = 6800
	cbs.actor_on_update()
	check(#anim_calls == 2 and anim_calls[2].what == "insert" and anim_calls[2].hud == "zbc_bodycam_5_anim_hud",
		"insert animation receives Body 5 HUD section")
end

-- zbc_item_anim.script: HUD section propagation & queue priority
do
	local chunk = assert(loadfile("optional/bodycam_item/gamedata/scripts/zbc_item_anim.script"))
	local played_huds, len_huds = {}, {}
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
			only_allow_movekeys = function() end,
			play_hud_motion = function(_, hud, anm) played_huds[#played_huds + 1] = { hud = hud, anm = anm } end,
			get_motion_length = function(hud) len_huds[#len_huds + 1] = hud; return 500 end,
			stop_hud_motion = function() end,
		},
		level = {},
		printf = function() end,
		time_global = function() return 0 end,
	}, { __index = _G })
	setfenv(chunk, A)
	chunk()

	-- Default nil hud_sec falls back to HUD_SECTION (Body 4)
	A.request("dead", 0, nil)
	A.update(0, true)
	A.update(10, true)
	check(played_huds[1] and played_huds[1].hud == "zbc_bodycam_anim_hud", "nil hud_sec defaults to zbc_bodycam_anim_hud")
	check(len_huds[1] == "zbc_bodycam_anim_hud", "get_motion_length receives default HUD section")
	A.update(600, true) -- finish

	-- Pending "dead" (Gen 1) replaced by "insert" (Gen 3) updates HUD section, and subsequent "dead" (Gen 2) cannot overwrite it
	A.request("dead", 700, "zbc_bodycam_1_anim_hud")
	A.request("insert", 710, "zbc_bodycam_3_anim_hud")
	A.request("dead", 720, "zbc_bodycam_2_anim_hud")
	A.update(730, true)
	A.update(740, true)
	check(played_huds[2] and played_huds[2].hud == "zbc_bodycam_3_anim_hud" and played_huds[2].anm == "anm_zbc_insert",
		"insert replaces pending dead HUD section and ignores later dead HUD section")
	A.update(1400, true) -- finish

	-- Queuing "insert" (Gen 5) mid-"dead" (Gen 2) plays Gen 5 insert right after Gen 2 dead finishes
	A.request("dead", 2000, "zbc_bodycam_2_anim_hud")
	A.update(2000, true)
	A.update(2010, true)
	check(played_huds[3] and played_huds[3].hud == "zbc_bodycam_2_anim_hud", "Gen 2 dead starts playing")
	A.request("insert", 2200, "zbc_bodycam_5_anim_hud")
	A.update(2600, true) -- finishes Gen 2 dead, preserves queued Gen 5 insert
	A.update(2610, true) -- begins Gen 5 insert
	A.update(2620, true) -- plays Gen 5 insert
	check(played_huds[4] and played_huds[4].hud == "zbc_bodycam_5_anim_hud" and played_huds[4].anm == "anm_zbc_insert",
		"queued insert HUD section survives finish() of preceding dead animation")
end

-- zbc_bodycam.script: set_device_source & effective_device_label()
do
	local mcm_vals = {}
	local cbs = {}
	local stub
	stub = setmetatable({}, {
		__index = function() return stub end,
		__call = function() return stub end,
		__add = function() return 0 end, __sub = function() return 0 end,
		__mul = function() return 0 end, __div = function() return 0 end,
		__unm = function() return 0 end, __concat = function() return "" end,
		__lt = function() return false end, __le = function() return false end,
	})
	local benv = setmetatable({
		shader_bus = false,
		ui_mcm = { get = function(k) return mcm_vals[k] end },
		device = function() return { width = 1920, height = 1080 } end,
		RegisterScriptCallback = function(name, fn) cbs[name] = fn end,
	}, { __index = function(_, k)
		local v = _G[k]
		if v ~= nil then return v end
		return stub
	end })
	local bchunk = assert(loadfile("gamedata/scripts/zbc_bodycam.script"))
	setfenv(bchunk, benv)
	check(pcall(bchunk), "zbc_bodycam.script loads cleanly")
	benv.on_game_start()

	check(benv.effective_device_label() == "AXON BODY 4", "default device label without item source is AXON BODY 4")
	local cur_dev = "AXON BODY 2"
	benv.set_device_source(function() return cur_dev end)
	check(benv.effective_device_label() == "AXON BODY 2", "device_source overrides default AXON BODY 4 watermark")
	cur_dev = nil
	check(benv.effective_device_label() == "AXON BODY 4", "nil from device_source falls back to AXON BODY 4")
	cur_dev = "AXON BODY"
	mcm_vals["zone_bodycam/device_label"] = "CUSTOM UNIT 7"
	if cbs.on_option_change then cbs.on_option_change() end
	check(benv.effective_device_label() == "CUSTOM UNIT 7", "custom user MCM device_label overrides device_source")
end

-- Configs & Assets verification (LTX, DLTX, 21 trader files, OGFs, and 512x128 DDS atlas)
do
	local function read_text(path)
		local f = io.open(path, "rb")
		if not f then return nil end
		local s = f:read("*a")
		f:close()
		return s
	end

	local function parse_ltx(path)
		local txt = read_text(path)
		check(txt ~= nil, "LTX exists: " .. path)
		local secs = {}
		local cur = nil
		for raw in (txt or ""):gmatch("[^\r\n]+") do
			local line = raw:gsub(";.*$", ""):match("^%s*(.-)%s*$")
			if line ~= "" then
				local name, parent = line:match("^%[([^%]]+)%]%s*:%s*([%w_]+)$")
				if not name then name = line:match("^%[([^%]]+)%]$") end
				if name then
					cur = {}
					if parent and secs[parent] then
						for k, v in pairs(secs[parent]) do cur[k] = v end
					end
					cur._parent = parent
					secs[name] = cur
				elseif cur then
					local k, v = line:match("^([%w_%$]+)%s*=%s*(.-)%s*$")
					if k then cur[k] = v end
				end
			end
		end
		return secs
	end

	local ltx = parse_ltx("optional/bodycam_item/gamedata/configs/items/items/items_zbc_bodycam.ltx")
	local expected_ltx = {
		{ sec = "zbc_bodycam_1",    hud = "zbc_bodycam_1_anim_hud", ogf = "zbc_bodycam_1.ogf", hud_ogf = "zbc_bodycam_1_hud.ogf", hand = "zbc_bodycam_1", omf = "zbc_bodycam_1_hud_animation.omf", gx = "1", gy = "0", w = "0.20", cost = "5000", tier = "1" },
		{ sec = "zbc_bodycam_2",    hud = "zbc_bodycam_2_anim_hud", ogf = "zbc_bodycam_2.ogf", hud_ogf = "zbc_bodycam_2_hud.ogf", hand = "zbc_bodycam_2", omf = "zbc_bodycam_2_hud_animation.omf", gx = "2", gy = "0", w = "0.24", cost = "8000", tier = "2" },
		{ sec = "zbc_bodycam_3",    hud = "zbc_bodycam_3_anim_hud", ogf = "zbc_bodycam_3.ogf", hud_ogf = "zbc_bodycam_3_hud.ogf", hand = "zbc_bodycam_3", omf = "zbc_bodycam_3_hud_animation.omf", gx = "3", gy = "0", w = "0.30", cost = "12000", tier = "3" },
		{ sec = "zbc_bodycam_item", hud = "zbc_bodycam_anim_hud",   ogf = "zbc_bodycam.ogf",   hud_ogf = "zbc_bodycam_hud.ogf",   hand = "zbc_bodycam", omf = "zbc_bodycam_hud_animation.omf",  gx = "0", gy = "0", w = "0.32", cost = "16000", tier = "4" },
		{ sec = "zbc_bodycam_5",    hud = "zbc_bodycam_5_anim_hud", ogf = "zbc_bodycam_5.ogf", hud_ogf = "zbc_bodycam_5_hud.ogf", hand = "zbc_bodycam_5", omf = "zbc_bodycam_5_hud_animation.omf", gx = "4", gy = "0", w = "0.33", cost = "24000", tier = "5" },
	}
	for _, e in ipairs(expected_ltx) do
		local s = ltx[e.sec]
		check(s ~= nil, "items_zbc_bodycam.ltx defines [" .. e.sec .. "]")
		if s then
			check(s.visual == "dynamics\\devices\\zbc_bodycam\\" .. e.ogf, e.sec .. " visual")
			check(s.inv_grid_x == e.gx and s.inv_grid_y == e.gy, e.sec .. " inv_grid_x,y")
			check(s.inv_grid_width == "1" and s.inv_grid_height == "1", e.sec .. " 1x1 grid size")
			check(s.inv_weight == e.w, e.sec .. " inv_weight")
			check(s.cost == e.cost, e.sec .. " cost")
			check(s.tier == e.tier, e.sec .. " tier")
			check(s.power_critical == "0.05", e.sec .. " power_critical")
			check(s.use6_functor == "item_device.menu_battery", e.sec .. " use6_functor")
		end
		local h = ltx[e.hud]
		check(h ~= nil, "items_zbc_bodycam.ltx defines [" .. e.hud .. "]")
		if h then
			check(h.item_visual == "dynamics\\devices\\zbc_bodycam\\" .. e.hud_ogf, e.hud .. " item_visual")
			-- each camera plays its own hand motions (grips fitted to its shell); the item motions share names
			check(h.anm_zbc_dead == e.hand .. "_dead, zbc_bodycam_dead_item", e.hud .. " anm_zbc_dead")
			check(h.anm_zbc_insert == e.hand .. "_insert, zbc_bodycam_insert_item", e.hud .. " anm_zbc_insert")
		end
	end

	local dev_dltx = read_text("optional/bodycam_item/gamedata/configs/items/settings/mod_devices_zbc_bodycam.ltx") or ""
	check(dev_dltx:find("!%[power_consumption%]") ~= nil, "mod_devices_zbc_bodycam.ltx patches ![power_consumption]")
	for _, sec in ipairs(M.CAMERA_ORDER) do
		check(dev_dltx:find(sec .. "%s*=%s*0,0,0") ~= nil, "mod_devices_zbc_bodycam.ltx registers " .. sec)
	end

	local traders = {
		"renegade", "bandit_basic", "stalker_basic",
		"bandit", "stalker_sidorovich", "stalker_loris",
		"csky_spore", "stalker_owl", "military_esc", "freedom_ashot",
		"duty", "freedom", "military", "monolith_basic", "monolith", "greh",
		"mercenary_basic", "mercenary", "ecolog_sakharov", "ecolog_hermann", "isg",
	}
	for _, tr in ipairs(traders) do
		local p = "optional/bodycam_item/gamedata/configs/items/trade/mod_trade_" .. tr .. "_zbc_bodycam.ltx"
		local t = read_text(p)
		check(t ~= nil and t:find("@%[supplies_1%]") ~= nil, "trade DLTX valid: " .. tr)
		if t then
			local has_cam = false
			for sec in t:gmatch("^(zbc_bodycam[%w_]*)%s*=") do
				check(M.CAMERAS[sec] ~= nil, tr .. " references known camera " .. sec)
				has_cam = true
			end
			for sec in t:gmatch("\n(zbc_bodycam[%w_]*)%s*=") do
				check(M.CAMERAS[sec] ~= nil, tr .. " references known camera " .. sec)
				has_cam = true
			end
			check(has_cam, tr .. " stocks at least one camera")
		end
	end

	for _, cam in ipairs({ "ab1", "ab2", "ab3", "ab4", "ab5" }) do
		local png = "tools/bodycam_item/icons/icon_" .. cam .. ".png"
		check(read_text(png) ~= nil, "icon source render " .. png .. " exists")
	end

	local skip_assets = (arg and arg[1] == "--logic-only") or os.getenv("ZBC_SKIP_ASSET_CHECK") == "1"
	if not skip_assets then
		local mesh_dir = "optional/bodycam_item/gamedata/meshes/dynamics/devices/zbc_bodycam/"
		for _, e in ipairs(expected_ltx) do
			local w_ogf = read_text(mesh_dir .. e.ogf)
			local h_ogf = read_text(mesh_dir .. e.hud_ogf)
			check(w_ogf ~= nil and #w_ogf > 256, "world OGF exists and non-empty: " .. e.ogf)
			check(h_ogf ~= nil and #h_ogf > 256, "HUD OGF exists and non-empty: " .. e.hud_ogf)
		end
		-- every camera's hand motions are in its OMF with the stop-at-end flag (else they loop and
		-- get_motion_length returns 0), and its HUD model carries idle + both item motions
		local function motion_flags(data, name)
			local i = 1
			while true do
				local s = data:find(name .. " ", i, true)
				if not s then return nil end
				i = s + 1
				local prev = s > 1 and data:byte(s - 1) or 0
				if not (prev > 32 and prev < 127) then
					local p = s + #name + 1
					local b1, b2, b3, b4 = data:byte(p, p + 3)
					local sp = { data:byte(p + 8, p + 11) }
					if b4 and sp[4] == 0x3F and sp[3] == 0x80 and sp[2] == 0 and sp[1] == 0 then   -- speed 1.0
						return b1 + b2 * 256 + b3 * 65536 + b4 * 16777216
					end
				end
			end
		end
		for _, e in ipairs(expected_ltx) do
			local omf = read_text("optional/bodycam_item/gamedata/meshes/anomaly_weapons/hud_hands_animation/" .. e.omf)
			check(omf ~= nil and #omf > 256, "hand animation OMF exists: " .. e.omf)
			local h_ogf = read_text(mesh_dir .. e.hud_ogf) or ""
			for _, t in ipairs({ "dead", "insert" }) do
				local fl = omf and motion_flags(omf, e.hand .. "_" .. t)
				check(fl ~= nil and fl % 4 >= 2, e.omf .. " has " .. e.hand .. "_" .. t .. " with stop-at-end")
				check(h_ogf:find("zbc_bodycam_" .. t .. "_item ", 1, true) ~= nil, e.hud_ogf .. " has zbc_bodycam_" .. t .. "_item")
			end
			check(h_ogf:find("idle ", 1, true) ~= nil, e.hud_ogf .. " has idle")
		end

		local dds = read_text("optional/bodycam_item/gamedata/textures/ui/ui_icon_zbc_bodycam.dds")
		check(dds ~= nil and #dds >= 128 and dds:sub(1, 4) == "DDS ", "ui_icon_zbc_bodycam.dds exists with DDS magic")
		if dds and #dds >= 20 then
			local function u32le(s, i)
				local b1, b2, b3, b4 = s:byte(i, i + 3)
				return b1 + b2 * 256 + b3 * 65536 + b4 * 16777216
			end
			local h, w = u32le(dds, 13), u32le(dds, 17)
			check(w == 256 and h == 64, ("ui_icon_zbc_bodycam.dds is the 256x64 1x1 5-camera atlas, got %dx%d"):format(w, h))
		end
	end
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_item_test: all checks passed")
