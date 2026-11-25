-- Tests the camera-effects logic: interference sources (zbc_fx.script), low-light mode, GPS line, the
-- EVENT marker in the recording timer text (zbc_bodycam.script) and the low-battery warning
-- (optional zbc_item.script).
--
-- Usage (from the repo root): lua tools/tests/zbc_fx_test.lua

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end

local stub
stub = setmetatable({}, {
	__index = function() return stub end,
	__call = function() return stub end,
	__add = function() return 0 end, __sub = function() return 0 end,
	__mul = function() return 0 end, __div = function() return 0 end,
	__unm = function() return 0 end, __concat = function() return "" end,
	__lt = function() return false end, __le = function() return false end,
})
local function load(path, stubbed)
	local env = setmetatable({}, { __index = function(_, k)
		local v = _G[k]
		if v ~= nil then return v end
		return stubbed and stub or nil
	end })
	local chunk = assert(loadfile(path))
	setfenv(chunk, env)
	local ok, err = pcall(chunk)
	check(ok, path .. " loads: " .. tostring(err))
	return env
end

-- zbc_fx.script
local fx = load("gamedata/scripts/zbc_fx.script", false)
local function near(a, b) return math.abs(a - b) < 1e-9 end

check(fx.approach(0, 1, 2, 0.25) == 0.5 and fx.approach(1, 0, 2, 0.25) == 0.5, "approach moves by rate x dt")
check(fx.approach(0.9, 1, 2, 0.25) == 1 and fx.approach(0.1, 0, 2, 0.25) == 0, "approach never overshoots")

check(fx.anomaly_interference(fx.ANOMALY_RANGE) == 0 and fx.anomaly_interference(20) == 0, "no anomaly interference out of range")
check(near(fx.anomaly_interference(1.5), 0.6) and near(fx.anomaly_interference(0.5), 0.6), "strongest right next to an anomaly")
check(fx.anomaly_interference(3) > fx.anomaly_interference(5), "stronger closer")
check(fx.anomaly_interference(nil) == 0, "no anomaly: none")

check(fx.interference(0, 0, 0, 0) == 0, "calm: no interference")
check(fx.interference(1, 0, 0, 0) > 0.5, "emission or psy storm: strong")
check(fx.interference(0, 1, 0, 0) > 0.85, "deep in a psy field: very strong")
check(fx.interference(0, 0, 0.2, 0) == 0, "light radiation: none")
check(fx.interference(0, 0, 1, 0) > 0.4, "heavy radiation: some")
check(fx.interference(1, 1, 1, 1) <= 1, "never above 1")

-- a steady psy field (Yantar's lab area) only flickers the picture; heavy only near the end
check(fx.interference(0, 0.3, 0, 0) <= 0.2, "light psy damage: a light flicker")
check(fx.interference(0, 0.5, 0, 0) <= 0.31, "half psy health gone: still mild")
check(fx.interference(0, 0.75, 0, 0) <= 0.31, "three quarters gone: still mild")
check(fx.interference(0, 0.95, 0, 0) > 0.6, "psy health nearly gone: heavy")
local prev = -1
for i = 0, 20 do
	local v = fx.psy_interference(i / 20)
	check(v >= prev, "psy interference never drops as psy damage grows (" .. i .. ")")
	prev = v
end
check(fx.interference(1, 1, 1, 1, 0) == 0, "strength 0: no interference at all")
check(near(fx.interference(1, 0, 0, 0, 0.5), 0.275), "strength halves it")
check(fx.interference(1, 0, 0, 0, 3) == fx.interference(1, 0, 0, 0, fx.MAX_STRENGTH), "strength is capped at MAX_STRENGTH")
check(fx.MAX_STRENGTH == 1.5 and fx.interference(1, 0, 0, 0, 1.5) > fx.interference(1, 0, 0, 0, 1), "Axon Body 1 (x1.5) gets more interference")
check(fx.interference(0, 1, 1, 1, 1.5) <= 1, "still never above 1")
check(#fx.hit_spikes(1, 1.5, function() return 0 end) > 0 and fx.hit_spikes(1, 1.5, function() return 0 end)[1][2] <= 1, "hit jolts stay at most 1")
check(fx.dark_level(0.8) == 0 and fx.dark_level(fx.DARK_LIT) == 0, "lit: not dark")
check(fx.dark_level(0.05) == 1 and fx.dark_level(fx.DARK_FULL) == 1, "very dark: fully dark")
check(fx.dark_level(0.2) > 0 and fx.dark_level(0.2) < 1 and fx.dark_level(nil) == 0, "dusk in between; unknown light: not dark")

check(fx.night_hours(22) and fx.night_hours(2) and not fx.night_hours(12) and not fx.night_hours(5), "night is 21:00-05:00")
check(fx.ir_target(0, 23, false) == 1 and fx.ir_target(0, 12, false) == 0, "auto follows the time of day")
check(fx.ir_target(0, 12, true) == 1, "auto: always on underground")
check(fx.ir_target(1, 12, false) == 1 and fx.ir_target(2, 23, true) == 0, "always / off override")

local g0 = fx.gps_text(0, 0)
check(g0 == "N51.38912 E30.09921", "origin is the NPP: " .. g0)
check(#g0 <= 40, "GPS line fits the overlay")
local g1 = fx.gps_text(0, 111320)
check(g1:find("^N52%.38912") ~= nil, "111.32 km north is one degree of latitude: " .. g1)
check(fx.gps_text(nil, "x") == g0, "bad position falls back to the origin")

-- the EVENT marker in the recording timer (zbc_bodycam.script)
local bc = load("gamedata/scripts/zbc_bodycam.script", true)
local rt = rawget(bc, "rec_text")
check(type(rt) == "function", "rec_text exists")
if type(rt) == "function" then
	check(rt(3661) == "REC 01:01:01", "plain timer")
	check(rt(3661, true) == "REC 01:01:01 EVENT", "timer with EVENT")
	check(rt(3661, false) == "REC 01:01:01", "EVENT goes away again")
	check(#rt(999 * 3600 + 3599, true) <= 22, "longest text fits REC_CHARS")
end

-- every effect can be switched off in the MCM: each setting is in the menu with an English and a
-- Russian label, and the switches added for rain, blood, the housing edge and the battery gauge work
do
	local mcm = io.open("gamedata/scripts/zbc_bodycam_mcm.script", "rb"):read("*a")
	local eng = io.open("gamedata/configs/text/eng/ui_st_zbc_bodycam.xml", "rb"):read("*a")
	local rus = io.open("gamedata/configs/text/rus/ui_st_zbc_bodycam.xml", "rb"):read("*a")
	local defs = rawget(bc, "defaults") or {}
	local n = 0
	for id in pairs(defs) do
		n = n + 1
		check(mcm:find('id = "' .. id .. '"', 1, true) ~= nil, "setting is in the MCM: " .. id)
		local sid = '"ui_mcm_zone_bodycam_' .. id .. '"'
		check(eng:find(sid, 1, true) and rus:find(sid, 1, true), "setting has eng and rus labels: " .. id)
	end
	check(n > 50, "defaults found")
	for _, id in ipairs({ "lens_rain", "lens_dirt", "lens_housing", "battery_gauge" }) do
		check(defs[id] == true, "on/off switch with default on: " .. id)
	end
	local el = rawget(bc, "edge_lane")
	check(type(el) == "function" and el(0.68, true) == 0.68 and el(0.68, false) == -0.68,
		"housing off sends the edge radius negative")
	local lens = io.open("gamedata/shaders/r3/zbc_lens.h", "rb"):read("*a")
	check(lens:find("(bus_zbc_edge.x < 0.0) ? 1.0", 1, true) and lens:find("abs(bus_zbc_edge.x)", 1, true),
		"shader: negative edge radius means no housing, vignette keeps its size")
	local src = io.open("gamedata/scripts/zbc_bodycam.script", "rb"):read("*a")
	check(src:find("cfg.rec_timer and cfg.battery_gauge and visible", 1, true) ~= nil, "battery gauge has its own switch")
end

-- the in-shader timer spells " EVENT" the same way
local osd = io.open("gamedata/shaders/r3/zbc_osd.h", "rb"):read("*a")
check(osd:find("10u + nh + ((bus_zbc_event.x > 0.5) ? 6u : 0u)", 1, true) ~= nil, "shader adds 6 characters for EVENT")

-- low-battery warning (optional item)
local it = load("optional/bodycam_item/gamedata/scripts/zbc_item.script", true)
local lw = rawget(it, "low_warning")
check(type(lw) == "function", "low_warning exists")
if type(lw) == "function" then
	local given, warn = lw(0.50, 0)
	check(given == 0 and not warn, "full battery: nothing")
	given, warn = lw(0.10, 0)
	check(given == 1 and warn, "10%: first warning")
	given, warn = lw(0.09, 1)
	check(given == 1 and not warn, "no repeat until 6%")
	given, warn = lw(0.06, 1)
	check(given == 2 and warn, "6%: second warning")
	given, warn = lw(0.03, 2)
	check(given == 2 and not warn, "nothing more after both")
	given, warn = lw(0.05, 0)
	check(given == 2 and warn, "found already low: one warning, not two in a row")
	given, warn = lw(0.90, 2)
	check(given == 0 and not warn, "new battery re-arms the warnings")
	given, warn = lw(nil, 1)
	check(given == 1 and not warn, "no charge: unchanged")
end

-- actor_on_before_death respects flags.ret_value == false and frame() clears death_t when alive
do
	local sig_calls, t_ms, alive = 0, 5000, true
	local fx_env = load("gamedata/scripts/zbc_fx.script", false)
	fx_env.time_global = function() return t_ms end
	fx_env.db = { actor = { alive = function() return alive end, position = function() return { x = 0, y = 0, z = 0 } end } }
	fx_env.zbc_bodycam = {
		fx_enabled = function() return true end,
		fx_option = function() return true end,
		signal_lost = function() sig_calls = sig_calls + 1 end,
	}
	fx_env.actor_on_before_death(nil, { ret_value = false })
	check(sig_calls == 0, "cancelled death does not trigger signal_lost")
	local st = fx_env.frame({}, 0.016)
	check(st.death_t == 0, "cancelled death leaves death_t == 0")

	alive = false
	fx_env.actor_on_before_death(nil, { ret_value = true })
	check(sig_calls == 1 and st.death_t == 5, "real death triggers signal_lost and records death_t")

	alive = true
	st = fx_env.frame({}, 0.016)
	check(st.death_t == 0, "revived/alive actor clears F.death_t")

	-- nil cfg and nil psi_storm_manager.get_psi_storm_manager() do not error; surge still drives glitch
	fx_env.surge_manager = { is_started = function() return true end }
	fx_env.psi_storm_manager = { get_psi_storm_manager = function() return nil end }
	local ok_nil = pcall(fx_env.frame, nil, 0.016)
	check(ok_nil, "frame(nil) does not error")
	local st_storm = fx_env.frame({ fx_glitch = true }, 0.05)
	check(st_storm.glitch > 0, "surge with nil psi_storm_manager still builds glitch")
	local function settle(c) fx_env.reset(); for _ = 1, 30 do fx_env.frame(c, 0.1) end; return st_storm.glitch end
	local g_full = settle({ fx_glitch = true })
	local g_half = settle({ fx_glitch = true, fx_glitch_strength = 0.5 })
	check(g_half > 0 and near(g_half, g_full * 0.5), "strength slider scales the storm interference")
	check(settle({ fx_glitch = true, fx_glitch_strength = 0 }) == 0, "strength 0: no storm interference")
	fx_env.surge_manager = nil
	fx_env.psi_storm_manager = nil

	-- Unpowered decay: glitch and ir decay instead of freezing
	fx_env.level = { get_time_hours = function() return 23 end, rain_factor = function() return 1 end }
	local cfg_fx = { fx_glitch = false, night_mode = 1, lens_dirt = true, lens_rain = true }
	for _ = 1, 20 do fx_env.frame(cfg_fx, 0.1, true) end
	check(st.ir > 0.5, "powered frame builds up ir")
	local ir_before = st.ir
	fx_env.frame(cfg_fx, 0.1, false)
	check(st.ir < ir_before, "unpowered frame continues decaying ir")
	check(st.wet == nil and st.wipe_t == nil and st.rain_mark == nil, "no rain of our own any more")
	st.blood_t = 5
	fx_env.frame({ lens_dirt = false }, 0.1, true)
	check(st.blood_t == 0, "blood option off clears the blood")

	-- rain on the lens is the game's visor drops: while the bodycam wants them, the drops update is
	-- told a mask is on and the droplets option is on (only for that call), mask or not
	local opts = { lens_enabled = true, lens_rain = true }
	local fx_on, mask_on = true, false
	fx_env.zbc_bodycam.fx_enabled = function() return fx_on end
	fx_env.zbc_bodycam.fx_option = function(id) return opts[id] and true or false end
	fx_env.actor_effects = { is_mask_on = function() return mask_on end }
	local le = { effects_droplets_enabled = false }
	local seen_mask, seen_opt, updates, resets, fail = nil, nil, 0, 0, false
	le.update_rain_droplets = function(a, b)
		updates = updates + 1
		seen_mask, seen_opt = fx_env.actor_effects.is_mask_on(), le.effects_droplets_enabled
		if fail then error("boom") end
		return a, b
	end
	le.droplets_reset = function() resets = resets + 1 end
	fx_env.level_environment = le
	local cbs = {}
	fx_env.RegisterScriptCallback = function(name, fn) cbs[name] = fn end
	fx_env.on_game_start()
	cbs.actor_on_first_update()
	cbs.actor_on_first_update()   -- loading a save again must not hook twice
	local r1, r2 = le.update_rain_droplets(1, 2)
	check(updates == 1, "the drops update runs once per call (hooked once)")
	check(r1 == 1 and r2 == 2, "arguments and results pass through")
	check(seen_mask == true and seen_opt == true, "bodycam on, no mask: the drops update sees a mask and the option on")
	check(fx_env.actor_effects.is_mask_on() == false and le.effects_droplets_enabled == false,
		"after the update the real mask state and option are back")
	opts.lens_rain = false
	le.update_rain_droplets()
	check(seen_mask == false and seen_opt == false, "Rain on the lens off: the game decides as usual")
	opts.lens_rain, opts.lens_enabled = true, false
	le.update_rain_droplets()
	check(seen_mask == false, "lens look off: no drops forced")
	opts.lens_enabled, fx_on = true, false
	le.update_rain_droplets()
	check(seen_mask == false, "bodycam off or without power: no drops forced")
	fx_on, mask_on = true, true
	le.update_rain_droplets()
	check(seen_mask == true and fx_env.actor_effects.is_mask_on() == true, "with a mask on: one effect, mask state kept")
	mask_on, fail = false, true
	local ok_err = pcall(le.update_rain_droplets)
	fail = false
	check(not ok_err and fx_env.actor_effects.is_mask_on() == false and le.effects_droplets_enabled == false,
		"an error in the drops update still restores the mask state and option")

	-- another droplet mod (Dynamic Smoother Droplets) swaps in its own update after us: wrapped too
	local smoother_seen, smoother_calls = nil, 0
	le.update_rain_droplets = function()
		smoother_calls = smoother_calls + 1
		smoother_seen = fx_env.actor_effects.is_mask_on() and le.effects_droplets_enabled
	end
	cbs.actor_on_update()
	cbs.actor_on_update()   -- already wrapped: not wrapped twice
	le.update_rain_droplets()
	check(smoother_calls == 1 and smoother_seen == true, "a droplet mod swapped in later is wrapped on the next update")
	check(fx_env.actor_effects.is_mask_on() == false, "and the real mask state is back after it")

	-- the engine draws the drops only inside the mask glass pass: with no mask on screen the intact
	-- glass (r2_mask_control 1,...) is switched on, refreshed every second, and off again afterwards
	local cmds = {}
	fx_env.exec_console_cmd = function(c) cmds[#cmds + 1] = c end
	local function last() return cmds[#cmds] end
	cbs.actor_on_update()
	check(last() == fx_env.GLASS_ON, "drops wanted, no mask: intact glass on")
	local n = #cmds
	t_ms = t_ms + 500
	cbs.actor_on_update()
	check(#cmds == n, "not sent again within a second")
	t_ms = t_ms + 600
	cbs.actor_on_update()
	check(#cmds == n + 1 and last() == fx_env.GLASS_ON, "sent again after a second (another script may have reset it)")
	mask_on = true
	n = #cmds
	cbs.actor_on_update()
	check(#cmds == n, "a real mask took over: its glass is left alone")
	mask_on = false
	cbs.actor_on_update()
	check(last() == fx_env.GLASS_ON, "mask off again: intact glass back on")
	opts.lens_rain = false
	cbs.actor_on_update()
	check(last() == fx_env.GLASS_OFF, "drops no longer wanted: glass off")
	n = #cmds
	cbs.actor_on_update()
	check(#cmds == n, "and nothing more while off")
	opts.lens_rain = true
	cbs.actor_on_update()
	cbs.actor_on_net_destroy()
	check(last() == fx_env.GLASS_OFF, "leaving the game turns the glass off")
	check(fx.glass_needed(true, false) == true and fx.glass_needed(true, true) == false
		and fx.glass_needed(false, false) == false, "glass only for wanted drops without a mask")
	fx_env.exec_console_cmd = nil

	-- the mask-wipe key (T = cam_zoom_in) wipes the drops: the visor drops' own wipe without a mask,
	-- the game's animated wipe (not ours) with one
	local DIK_T, DIK_Y = 20, 21
	fx_env.key_bindings = { kCAM_ZOOM_IN = 7 }
	fx_env.dik_to_bind = function(k) return (k == DIK_T) and 7 or 99 end
	cbs.on_key_release(DIK_Y)
	check(resets == 0, "another key does not wipe")
	cbs.on_key_release(DIK_T)
	check(resets == 1, "T without a mask wipes the drops")
	mask_on = true
	cbs.on_key_release(DIK_T)
	check(resets == 1, "T with a mask: the game's own wipe handles it")
	mask_on, opts.lens_rain = false, false
	cbs.on_key_release(DIK_T)
	check(resets == 1, "Rain on the lens off: T leaves the visor drops to the game")
	opts.lens_rain = true

	-- T without a mask plays the game's mask-wipe hand animation (which wipes the drops in step),
	-- told a mask is on only for that call; if it can't start, the plain drop wipe runs instead
	local ae = fx_env.actor_effects
	local anim_calls, anim_saw_mask, anim_allowed = 0, nil, true
	ae.mc_anm_state = 0
	ae.Hit_MaskCleaning = function()
		anim_calls = anim_calls + 1
		anim_saw_mask = ae.is_mask_on()
		if anim_allowed and ae.is_mask_on() then ae.mc_anm_state = 1 end
	end
	resets = 0
	cbs.on_key_release(DIK_T)
	check(anim_calls == 1 and anim_saw_mask == true, "T without a mask plays the wipe animation, told a mask is on")
	check(ae.is_mask_on() == false, "the real mask state is back after it")
	check(resets == 0, "the animation does the wiping: no extra plain wipe")
	cbs.on_key_release(DIK_T)
	check(anim_calls == 1, "a press while the hand is still wiping does not start another")
	ae.mc_anm_state, anim_allowed = 0, false
	cbs.on_key_release(DIK_T)
	check(anim_calls == 2 and resets == 1, "animation blocked (busy hands): the drops are still wiped")
	ae.Hit_MaskCleaning = function() error("boom") end
	cbs.on_key_release(DIK_T)
	check(ae.is_mask_on() == false and resets == 2, "an error in the animation still restores the mask state and wipes")
	mask_on, anim_calls = true, 0
	ae.Hit_MaskCleaning = function() anim_calls = anim_calls + 1 end
	cbs.on_key_release(DIK_T)
	check(anim_calls == 0, "with a mask on, T is left to the game's own handler (no second animation)")
	mask_on, ae.Hit_MaskCleaning, ae.mc_anm_state = false, nil, nil

	le.droplets_reset = nil
	check(fx_env.wipe_drops() == false, "no visor drops wipe available: nothing, no error")
	fx_env.key_bindings, fx_env.dik_to_bind = nil, nil
	cbs.on_key_release(DIK_T)   -- missing engine globals: no error
	fx_env.level_environment = nil
	cbs.actor_on_first_update()  -- no visor drops script: no error
end

-- when the bodycam drives the visor drops
do
	check(fx.drops_wanted(true, true, true) == true, "recording, lens on, rain on: drops")
	check(fx.drops_wanted(false, true, true) == false and fx.drops_wanted(true, false, true) == false
		and fx.drops_wanted(true, true, false) == false and fx.drops_wanted(nil, nil, nil) == false,
		"any of them off: no drops")
end

-- zbc_bodycam.script: dead/fx_last reload recovery & Shader Bus <= 6 uint4 gating
do
	local registered, set_calls, uint_calls, bc_cbs = {}, {}, {}, {}
	local now_ms, alive, hud_adds = 1000, true, 0
	local bc_env
	local stub_vec = { x = 0, y = 0, z = 0, set = function(self) return self end }
	local mock_globals = {
		device = function() return { width = 1920, height = 1080, fov = 75, cam_pos = stub_vec, cam_dir = stub_vec, cam_right = stub_vec, cam_top = stub_vec } end,
		time_global = function() return now_ms end,
		vector = function() return { x = 0, y = 0, z = 0, set = function(self) return self end } end,
		vector2 = function() return { set = function(self) return self end } end,
		Frect = function() return { set = function(self) return self end } end,
		db = { actor = { alive = function() return alive end, position = function() return stub_vec end, character_name = function() return "Strelok" end } },
		level = { present = function() return true end, get_time_hours = function() return 12 end },
		game = {
			get_game_time = function() return { get = function() return 2012, 5, 1, 12, 0, 0, 0 end } end,
			translate_string = function(s) return s end,
		},
		shader_bus = {
			version = function() return 6 end,
			try_register = function(id) registered[id] = true; return id end,
			set = function(tok, x, y, z, w) set_calls[tok] = { x, y, z, w } end,
			set_array_uint = function(tok) uint_calls[#uint_calls + 1] = tok end,
		},
		zbc_osd_atlas = { ROWS = { { 1, 2, 3, 4 } } },
		zbc_font_metrics = load("gamedata/scripts/zbc_font_metrics.script", false),
		zbc_allies = { build = function() return {} end, update = function() end, clear_known = function() end, upper_cp1251 = function(s) return s end },
		zbc_faces = { reset = function() end, update = function() return {}, 0, 16 / 9 end },
		zbc_fx = { frame = function() return { glitch = 0, burst = 0, death_t = 0, ir = 0, blood_seed = 0, blood_t = 0, event = false } end },
		load_var = function(_, _, d) return d end,
		save_var = function() end,
		get_hud = function() return { AddDialogToRender = function() hud_adds = hud_adds + 1 end, RemoveDialogToRender = function() end } end,
		CScriptXmlInit = function() return {
			ParseFile = function() end,
			InitStatic = function()
				local w = {}
				return setmetatable(w, { __index = function() return function() return w end end })
			end,
		} end,
		CUIScriptWnd = { SetWndRect = function() end, SetAutoDelete = function() end },
		super = function() end,
		class = function(name)
			local cls = {}
			cls.__index = cls
			setmetatable(cls, {
				__index = bc_env.CUIScriptWnd,
				__call = function(c, ...)
					local inst = setmetatable({}, c)
					if inst.__init then inst:__init(...) end
					return inst
				end,
			})
			bc_env[name] = cls
			return function() end
		end,
		RegisterScriptCallback = function(name, fn) bc_cbs[name] = fn end,
		ui_mcm = false,
		actor_menu = false,
		main_menu = false,
		printf = function() end,
	}
	bc_env = setmetatable(mock_globals, { __index = function(_, k) return _G[k] or stub end })
	local bc_chunk = assert(loadfile("gamedata/scripts/zbc_bodycam.script"))
	setfenv(bc_chunk, bc_env)
	bc_chunk()

	bc_env.actor_on_first_update()
	bc_env.actor_on_update()
	check(registered["zbc_motion"] == true and registered["zbc_lens"] == true, "Bus 6 registers float4 lanes")
	check(not registered["zbc_osd_chars"] and not registered["zbc_osd_atlas"] and not registered["zbc_face_rows"],
		"Bus 6 skips uint4 lane registration")
	check(#uint_calls == 0, "Bus 6 never calls set_array_uint")

	-- Death -> reload recovery (actor_on_first_update) and live-actor recovery (actor_on_update)
	alive = false
	bc_env.signal_lost(1.0)
	check(set_calls["zbc_glitch"] and set_calls["zbc_glitch"][3] == 1.0, "signal_lost sends death_t")

	-- Live actor recovery without reload (cancelled death / respawn)
	alive = true
	now_ms = 2000
	bc_env.actor_on_update()
	check(set_calls["zbc_glitch"] and set_calls["zbc_glitch"][3] == 0, "actor_on_update recovers when dead actor is alive")

	-- Death -> save reload (actor_on_first_update)
	alive = false
	bc_env.signal_lost(2.0)
	alive = true
	bc_env.actor_on_first_update()
	now_ms = 3000
	bc_env.actor_on_update()
	check(set_calls["zbc_glitch"] and set_calls["zbc_glitch"][3] == 0, "actor_on_first_update resets dead/fx_last across reload")

	-- main_menu_on_init zeroes zbc_batt alongside zbc_osd_info and zbc_rec
	set_calls["zbc_batt"] = { 1, 4, 1, 1 }
	bc_env.main_menu_on_init()
	check(set_calls["zbc_batt"] and set_calls["zbc_batt"][1] == 0, "main_menu_on_init hides zbc_batt")
	bc_env.main_menu_on_quit()

	-- settings_changed (on_option_change) while dead must NOT re-add HUD or push menu lens
	bc_env.on_game_start()
	alive = false
	bc_env.signal_lost(3.0)
	local adds_before = hud_adds
	set_calls["zbc_motion"] = { 0, 0, 0, 0 }
	bc_env.main_menu_on_init()
	bc_cbs.on_option_change()
	check(hud_adds == adds_before, "settings_changed while dead does not re-add HUD")
	check(set_calls["zbc_motion"][1] == 0, "settings_changed while dead does not push menu lens")
	bc_env.main_menu_on_quit()
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_fx_test: all checks passed")
