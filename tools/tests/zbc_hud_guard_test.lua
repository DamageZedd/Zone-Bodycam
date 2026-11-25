-- Regression test: zbc_bodycam.script must not throw when the game has no HUD yet (get_hud() nil
-- during a load or level change). hud_add used to create the overlay window and call
-- get_hud():AddDialogToRender unguarded: the error escaped actor_on_first_update/actor_on_update, and
-- HUD stayed set without ever being added, so the overlay never came back. Now nothing is created
-- without a HUD, and actor_on_update adds the overlay once the HUD is there.
--
-- Usage (from the repo root): lua tools/tests/zbc_hud_guard_test.lua

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

local have_hud, hud_adds, now_ms = false, 0, 1000
local hud = {
	AddDialogToRender = function() hud_adds = hud_adds + 1 end,
	RemoveDialogToRender = function() end,
}
local bc_env
local stub_vec = { x = 0, y = 0, z = 0, set = function(self) return self end }
local mock = {
	device = function() return { width = 1920, height = 1080, fov = 75, cam_pos = stub_vec, cam_dir = stub_vec, cam_right = stub_vec, cam_top = stub_vec } end,
	time_global = function() return now_ms end,
	vector = function() return { x = 0, y = 0, z = 0, set = function(self) return self end } end,
	vector2 = function() return { set = function(self) return self end } end,
	Frect = function() return { set = function(self) return self end } end,
	db = { actor = { alive = function() return true end, position = function() return stub_vec end, character_name = function() return "Strelok" end } },
	level = { present = function() return true end, get_time_hours = function() return 12 end },
	game = {
		get_game_time = function() return { get = function() return 2012, 5, 1, 12, 0, 0, 0 end } end,
		translate_string = function(s) return s end,
	},
	shader_bus = {
		version = function() return 7 end,
		try_register = function(id) return id end,
		set = function() end,
		set_array_uint = function() end,
	},
	zbc_osd_atlas = { ROWS = { { 1, 2, 3, 4 } } },
	zbc_font_metrics = load_plain("gamedata/scripts/zbc_font_metrics.script"),
	zbc_allies = { build = function() return {} end, update = function() end, clear_known = function() end, upper_cp1251 = function(s) return s end },
	zbc_faces = { reset = function() end, update = function() return {}, 0, 16 / 9 end },
	zbc_fx = { frame = function() return { glitch = 0, burst = 0, death_t = 0, ir = 0, event = false } end },
	load_var = function(_, _, d) return d end,
	save_var = function() end,
	get_hud = function() return have_hud and hud or nil end,
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
	RegisterScriptCallback = function() end,
	ui_mcm = false,
	actor_menu = false,
	main_menu = false,
	printf = function() end,
}
bc_env = setmetatable(mock, { __index = function(_, k) local v = _G[k]; if v ~= nil then return v end; return stub end })
local chunk = assert(loadfile("gamedata/scripts/zbc_bodycam.script"))
setfenv(chunk, bc_env)
local ok, err = pcall(chunk)
check(ok, "zbc_bodycam.script loads: " .. tostring(err))

-- no game HUD: first update and updates run without an error and add nothing
ok, err = pcall(bc_env.actor_on_first_update)
check(ok, "actor_on_first_update with no game HUD: no error (" .. tostring(err) .. ")")
for _ = 1, 3 do
	now_ms = now_ms + 16
	ok, err = pcall(bc_env.actor_on_update)
	check(ok, "actor_on_update with no game HUD: no error (" .. tostring(err) .. ")")
end
check(hud_adds == 0, "nothing added while there is no game HUD")

-- the HUD comes up: the overlay is added on the next update, exactly once
have_hud = true
for _ = 1, 3 do
	now_ms = now_ms + 16
	ok, err = pcall(bc_env.actor_on_update)
	check(ok, "actor_on_update with the HUD: no error (" .. tostring(err) .. ")")
end
check(hud_adds == 1, "the overlay is added once the HUD exists (added " .. hud_adds .. " times)")

-- a level unload removes it, and the next level adds it again
pcall(bc_env.actor_on_net_destroy)
have_hud = false
pcall(bc_env.actor_on_first_update)
now_ms = now_ms + 16
ok = pcall(bc_env.actor_on_update)
check(ok and hud_adds == 1, "next level, HUD not up yet: no error, nothing added")
have_hud = true
now_ms = now_ms + 16
pcall(bc_env.actor_on_update)
check(hud_adds == 2, "next level: the overlay comes back")

-- signal lost with no HUD: the death clock is skipped, no error
have_hud = false
ok, err = pcall(bc_env.signal_lost, 1.0)
check(ok, "signal_lost with no game HUD: no error (" .. tostring(err) .. ")")

if failures == 0 then
	print("zbc_hud_guard_test: all passed")
else
	print("zbc_hud_guard_test: " .. failures .. " failure(s)")
	os.exit(1)
end
