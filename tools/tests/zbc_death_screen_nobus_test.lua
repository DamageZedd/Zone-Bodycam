-- Regression test: a death always has a death screen, also without the Shader Bus.
-- While signal lost is on, zbc_fx takes Death Like Romeo's death handler off actor_on_before_death
-- and calls it only when signal lost does not play. zbc_bodycam.signal_lost returns early without
-- the Shader Bus (older exes), and zbc_fx did not notice: neither signal lost nor Romeo's screen
-- played. Now signal_lost says whether it played and zbc_fx falls back to the other death screen.
-- Uses the real zbc_bodycam.script and zbc_fx.script.
--
-- Usage (from the repo root): lua tools/tests/zbc_death_screen_nobus_test.lua

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

local function load_plain(path)
	local e = setmetatable({}, { __index = _G })
	local c = assert(loadfile(path))
	setfenv(c, e)
	c()
	return e
end

local now_ms = 1000
local registered = {}

-- a stand-in for true_first_person_death.script: its death handler is a local upvalue of on_game_start
local romeo_calls = 0
local romeo
do
	local function on_actor_before_death() romeo_calls = romeo_calls + 1 end
	romeo = { on_game_start = function() registered[on_actor_before_death] = true end }
	romeo.on_game_start()
end
_G.true_first_person_death = romeo

-- the real zbc_bodycam.script; bus: a Shader Bus mock, or nil for exes without one
local function load_bodycam(bus)
	local stub_vec = { x = 0, y = 0, z = 0, set = function(self) return self end }
	local hud = { AddDialogToRender = function() end, RemoveDialogToRender = function() end }
	local bc_env
	local mock = {
		device = function() return { width = 1920, height = 1080, fov = 75, cam_pos = stub_vec, cam_dir = stub_vec, cam_right = stub_vec, cam_top = stub_vec } end,
		time_global = function() return now_ms end,
		time_continual = function() return now_ms end,
		vector = function() return { x = 0, y = 0, z = 0, set = function(self) return self end } end,
		vector2 = function() return { set = function(self) return self end } end,
		Frect = function() return { set = function(self) return self end } end,
		db = { actor = { alive = function() return true end, position = function() return stub_vec end, character_name = function() return "Strelok" end } },
		level = { present = function() return true end, get_time_hours = function() return 12 end },
		game = {
			get_game_time = function() return { get = function() return 2012, 5, 1, 12, 0, 0, 0 end } end,
			translate_string = function(s) return s end,
		},
		shader_bus = bus or false,
		zbc_osd_atlas = { ROWS = { { 1, 2, 3, 4 } } },
		zbc_font_metrics = load_plain("gamedata/scripts/zbc_font_metrics.script"),
		zbc_allies = { build = function() return {} end, update = function() end, clear_known = function() end, upper_cp1251 = function(s) return s end },
		zbc_faces = { reset = function() end, update = function() return {}, 0, 16 / 9 end },
		zbc_fx = { frame = function() return { glitch = 0, burst = 0, death_t = 0, ir = 0, event = false } end },
		load_var = function(_, _, d) return d end,
		save_var = function() end,
		get_hud = function() return hud end,
		CScriptXmlInit = function() return {
			ParseFile = function() end,
			InitStatic = function()
				local w = {}
				return setmetatable(w, { __index = function() return function() return w end end })
			end,
		} end,
		CUIScriptWnd = { SetWndRect = function() end, SetAutoDelete = function() end, Show = function() end, Update = function() end },
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
		RegisterScriptCallback = function() end,
		ui_mcm = false,
		actor_menu = false,
		main_menu = false,
		printf = function() end,
	}
	bc_env = setmetatable(mock, { __index = function(_, k) local v = _G[k]; if v ~= nil then return v end; return stub end })
	local c = assert(loadfile("gamedata/scripts/zbc_bodycam.script"))
	setfenv(c, bc_env)
	local ok, err = pcall(c)
	check(ok, "zbc_bodycam.script loads: " .. tostring(err))
	bc_env.on_game_start()
	pcall(bc_env.actor_on_first_update)
	return bc_env
end

-- the real zbc_fx.script, wired to that zbc_bodycam
local function load_fx(bc)
	local env = setmetatable({
		zbc_bodycam = bc,
		RegisterScriptCallback = function(name, f) if name == "actor_on_before_death" then registered[f] = true end end,
		UnregisterScriptCallback = function(name, f) if name == "actor_on_before_death" then registered[f] = nil end end,
		printf = function() end,
		time_global = function() return now_ms end,
	}, { __index = _G })
	local c = assert(loadfile("gamedata/scripts/zbc_fx.script"))
	setfenv(c, env)
	local ok, err = pcall(c)
	check(ok, "zbc_fx.script loads: " .. tostring(err))
	return env
end

local present = function(name) return name == "true_first_person_death" end
local bus = {
	version = function() return 7 end,
	try_register = function(id) return id end,
	set = function() end,
	set_array_uint = function() end,
}

-- exes without the Shader Bus: Romeo's handler is taken, signal lost cannot play, Romeo's screen plays
do
	local bc = load_bodycam(nil)
	local fx = load_fx(bc)
	fx.take_death_screens(true, present)
	local held = 0
	for _ in pairs(registered) do held = held + 1 end
	check(held == 0, "no bus: Romeo's handler is taken off the callback while signal lost is on")
	check(bc.signal_lost(1.0) == false, "no bus: signal_lost says it did not play")
	romeo_calls = 0
	fx.actor_on_before_death(nil, {})
	check(romeo_calls == 1, "no bus: Romeo's death screen plays instead (called " .. romeo_calls .. " times)")
	fx.take_death_screens(false, present)
end

-- with the Shader Bus: signal lost plays, Romeo's screen does not
do
	local bc = load_bodycam(bus)
	local fx = load_fx(bc)
	fx.take_death_screens(true, present)
	romeo_calls = 0
	fx.actor_on_before_death(nil, {})
	check(romeo_calls == 0, "with the bus: only signal lost plays")
	check(bc.signal_lost(2.0) == true, "with the bus: a second call while it plays still counts as played")
	fx.take_death_screens(false, present)
end

if failures == 0 then
	print("zbc_death_screen_nobus_test: all passed")
else
	print("zbc_death_screen_nobus_test: " .. failures .. " failure(s)")
	os.exit(1)
end
