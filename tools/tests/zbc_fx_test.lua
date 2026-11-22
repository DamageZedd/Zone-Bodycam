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
	fx_env.surge_manager = nil
	fx_env.psi_storm_manager = nil

	-- Unpowered decay: glitch, ir, and wet decay toward 0/rain instead of freezing
	fx_env.level = { get_time_hours = function() return 23 end, rain_factor = function() return 1 end }
	local cfg_fx = { fx_glitch = false, night_mode = 1, lens_dirt = true, lens_rain = true }
	for _ = 1, 20 do fx_env.frame(cfg_fx, 0.1, true) end
	check(st.ir > 0.5 and st.wet > 0.1, "powered frame builds up ir and wet")
	fx_env.level = { get_time_hours = function() return 23 end, rain_factor = function() return 0 end }
	local ir_before, wet_before = st.ir, st.wet
	fx_env.frame(cfg_fx, 0.1, false)
	check(st.ir < ir_before and st.wet < wet_before, "unpowered frame continues decaying ir and wet")

	-- rain under a roof (rain_hemi low) does not reach the lens: no build-up, marker set
	fx_env.reset()
	fx_env.level = { get_time_hours = function() return 12 end, rain_factor = function() return 1 end,
		rain_hemi = function() return 0.05 end }
	for _ = 1, 20 do fx_env.frame(cfg_fx, 0.1, true) end
	check(st.wet == 0 and st.rain_mark > 0, "covered: lens stays dry and arrivals are stopped")
	fx_env.level.rain_hemi = function() return 1 end
	fx_env.frame(cfg_fx, 0.1, true)
	check(st.wet > 0 and st.rain_mark < 0, "back in the rain: water builds, marker says uncovered")
	fx_env.frame({ lens_dirt = false, lens_rain = true }, 0.1, true)
	check(st.wet > 0, "blood option off leaves the rain alone")
	st.blood_t = 5
	fx_env.frame({ lens_dirt = true, lens_rain = false }, 0.1, true)
	check(st.wet == 0 and st.rain_mark == 0 and st.blood_t == 5, "rain option off clears the rain at once, blood stays")

	-- a mask that shows its own visor rain switches our lens drops off; a mask without it does not
	fx_env.reset()
	local mask_on, droplets_opt = true, true
	fx_env.actor_effects = { is_mask_on = function() return mask_on end }
	fx_env.ui_options = { get = function(k) if k == "video/player/rain_droplets" then return droplets_opt end end }
	for _ = 1, 10 do fx_env.frame(cfg_fx, 0.1, true) end
	check(st.wet == 0, "mask with visor rain: no lens drops")
	droplets_opt = false
	for _ = 1, 10 do fx_env.frame(cfg_fx, 0.1, true) end
	check(st.wet > 0, "mask without visor rain (droplets option off): lens drops")
	mask_on, droplets_opt = false, true
	local w0 = st.wet
	fx_env.frame(cfg_fx, 0.1, true)
	check(st.wet > w0, "no mask: lens drops keep building")
	mask_on = true
	fx_env.frame(cfg_fx, 0.1, true)
	check(st.wet == 0 and st.rain_mark == 0, "putting on a visor-rain mask clears the lens drops at once")

	-- the mask-wipe key wipes the lens: hooked into actor_effects.Hit_MaskCleaning, works without a mask
	mask_on = false
	local mask_wipes = 0
	fx_env.actor_effects.Hit_MaskCleaning = function() mask_wipes = mask_wipes + 1 end
	fx_env.reset()
	for _ = 1, 10 do fx_env.frame(cfg_fx, 0.1, true) end
	local cbs = {}
	fx_env.RegisterScriptCallback = function(name, fn) cbs[name] = fn end
	fx_env.on_game_start()
	cbs.actor_on_first_update()
	cbs.actor_on_first_update()   -- loading a save again must not hook twice
	for _ = 1, 10 do fx_env.frame(cfg_fx, 0.1, true) end
	check(st.wet > 0 and st.wipe_t == 0, "wet lens before the wipe")
	fx_env.actor_effects.Hit_MaskCleaning()
	check(mask_wipes == 1, "the game's own mask wipe still runs, once")
	check(st.wipe_t == t_ms / 1000, "wipe key starts the lens wipe sweep")
	local wet_mid = st.wet
	t_ms = t_ms + 300
	fx_env.frame(cfg_fx, 0.3, true)
	check(st.wipe_t > 0 and st.wet == wet_mid, "mid-sweep: water held while the hand passes")
	t_ms = t_ms + 400
	fx_env.frame(cfg_fx, 0.4, true)
	check(st.wet == 0 and st.wipe_t == 0 and st.rain_mark < 0, "after the sweep: lens clean, only new drops fall")
	fx_env.frame(cfg_fx, 0.1, true)
	check(st.wet > 0, "rain builds up again after the wipe")
	fx_env.wipe_lens()
	fx_env.reset()
	fx_env.wipe_lens()
	check(st.wipe_t == 0, "wiping a dry lens does nothing")

	-- the wipe key (T = cam_zoom_in) wipes on its own, even when the game's handler gives up
	-- (Mask HUD off, so it never sees a mask) or a mod replaced it after our hook
	local DIK_T, DIK_Y = 20, 21
	fx_env.key_bindings = { kCAM_ZOOM_IN = 7 }
	fx_env.dik_to_bind = function(k) return (k == DIK_T) and 7 or 99 end
	fx_env.actor_effects.Hit_MaskCleaning = function() end   -- bails out, no lens wipe in it
	for _ = 1, 10 do fx_env.frame(cfg_fx, 0.1, true) end
	check(st.wet > 0 and st.wipe_t == 0, "wet lens before the key press")
	cbs.on_key_release(DIK_Y)
	check(st.wipe_t == 0, "another key does not wipe")
	cbs.on_key_release(DIK_T)
	check(st.wipe_t == t_ms / 1000, "the wipe key starts the sweep without the game's handler")
	t_ms = t_ms + 100
	cbs.on_key_release(DIK_T)
	check(st.wipe_t == (t_ms - 100) / 1000, "a second press during the sweep does not restart it")
	fx_env.key_bindings, fx_env.dik_to_bind = nil, nil
	cbs.on_key_release(DIK_T)   -- missing engine globals: no error
end

-- lens rain timing (the shader's drop population and arrivals follow these)
do
	local w = 0
	w = fx.lens_water(w, 1, true, 0.2)
	check(near(w, 0.1), "first drops arrive fast")
	for _ = 1, 10 do w = fx.lens_water(w, 1, true, 0.1) end
	check(w > 0.18 and w < 0.25, "then the water builds slowly")
	check(fx.lens_water(0.5, 0.3, true, 1) < 0.5 and fx.lens_water(0.5, 0.3, true, 1) > 0.3, "lighter rain: dries toward it")
	check(near(fx.lens_water(0.5, 1, false, 18), 0.5 * math.exp(-1)), "under cover: dries with an 18 s time constant")
	check(fx.lens_water(0.001, 1, false, 0.1) == 0, "nearly dry snaps to dry")
	check(fx.lens_water(0.4, 0.4, true, 1) == 0.4, "steady rain holds")
	check(fx.lens_water(0, 0, true, 1) == 0, "no rain stays dry")

	check(fx.rain_mark(0, true, 100) == 0, "raining on the lens: marker 0")
	check(fx.rain_mark(0, false, 100) == 100, "covered: marker is the time cover began")
	check(fx.rain_mark(100, false, 105) == 100, "staying covered keeps the start time")
	check(fx.rain_mark(100, true, 110) == -110, "uncovered: negative time it ended")
	check(fx.rain_mark(-110, true, 112) == -110, "within one drop life the marker holds")
	check(fx.rain_mark(-110, true, 110 + fx.RAIN_LIFE) == 0, "after one drop life back to 0")
	check(fx.rain_mark(-110, false, 111) == 111, "covered again: new start time")
	check(fx.rain_mark(0, false, 0) > 0, "time 0 still marks cover")

	local wv, wm, wt = fx.lens_wipe(0.5, 0, 10, 10.3)
	check(wv == 0.5 and wm == 0 and wt == 10, "during the sweep nothing changes")
	wv, wm, wt = fx.lens_wipe(0.5, 0, 10, 10 + fx.WIPE_TIME)
	check(wv == 0 and wm == -(10 + fx.WIPE_TIME) and wt == 0, "sweep done: clean lens, fresh drops only")
	check(fx.lens_wipe(0.5, 7, 0, 99) == 0.5, "no wipe: untouched")
	check(fx.lens_rain_allowed(true, false) and not fx.lens_rain_allowed(true, true)
		and not fx.lens_rain_allowed(false, false), "lens rain: option on and no visor rain")
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
		zbc_fx = { frame = function() return { glitch = 0, burst = 0, death_t = 0, ir = 0, wet = 0, blood_seed = 0, blood_t = 0, event = false } end },
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
