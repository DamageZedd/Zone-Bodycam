-- Regression test: identified people stay identified after loading a save or changing level.
-- zbc_allies keeps them in the save (save_state / load_state) and clears them itself only for a game
-- started without that data (pending_clear). zbc_bodycam.script used to call zbc_allies.clear_known()
-- from its own actor_on_first_update, which runs after load_state, so every load and level change
-- wiped what load_state had just restored, whichever first-update callback ran first.
--
-- Usage (from the repo root): lua tools/tests/zbc_saved_ids_test.lua

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

-- the real zbc_allies.script, its callbacks captured
local allies_cbs = {}
local ae = setmetatable({
	time_global = function() return now_ms end,
	RegisterScriptCallback = function(name, fn) allies_cbs[name] = fn end,
}, { __index = _G })
do
	local c = assert(loadfile("gamedata/scripts/zbc_allies.script"))
	setfenv(c, ae)
	local ok, err = pcall(c)
	check(ok, "zbc_allies.script loads: " .. tostring(err))
	ae.on_game_start()
end

-- the real zbc_bodycam.script, with that zbc_allies
local bc_cbs = {}
local stub_vec = { x = 0, y = 0, z = 0, set = function(self) return self end }
local hud = { AddDialogToRender = function() end, RemoveDialogToRender = function() end }
local bc_env
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
	zbc_allies = {
		build = function() return {} end, update = function() end, upper_cp1251 = function(s) return s end,
		clear_known = function(...) return ae.clear_known(...) end,
	},
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
bc_env = setmetatable(mock, { __index = function(_, k) local v = _G[k]; if v ~= nil then return v end; return stub end })
do
	local c = assert(loadfile("gamedata/scripts/zbc_bodycam.script"))
	setfenv(c, bc_env)
	local ok, err = pcall(c)
	check(ok, "zbc_bodycam.script loads: " .. tostring(err))
	bc_env.on_game_start()
end

check(type(allies_cbs.actor_on_first_update) == "function" and type(bc_cbs.actor_on_first_update) == "function",
	"both scripts register actor_on_first_update")

-- a save made with person 42 identified
ae.load_state({ zbc_known = { 42 } })
check(ae.is_known_id(42), "setup: 42 is identified")
local saved = {}
ae.save_state(saved)

-- leave the level (or quit to the menu), load the save, first update: in either callback order
local orders = {
	{ "zbc_bodycam first", bc_cbs, allies_cbs },
	{ "zbc_allies first", allies_cbs, bc_cbs },
}
for _, o in ipairs(orders) do
	local name, a, b = o[1], o[2], o[3]
	pcall(a.actor_on_net_destroy)
	pcall(b.actor_on_net_destroy)
	ae.load_state(saved)
	now_ms = now_ms + 16
	local ok1, e1 = pcall(a.actor_on_first_update)
	local ok2, e2 = pcall(b.actor_on_first_update)
	check(ok1 and ok2, name .. ": first updates run without an error (" .. tostring(e1) .. ", " .. tostring(e2) .. ")")
	check(ae.is_known_id(42), name .. ": 42 is still identified after the load")
end

-- a new game (no load_state): nobody known
pcall(bc_cbs.actor_on_net_destroy)
pcall(allies_cbs.actor_on_net_destroy)
pcall(bc_cbs.actor_on_first_update)
pcall(allies_cbs.actor_on_first_update)
check(not ae.is_known_id(42), "a game started without the saved data: nobody known")

if failures == 0 then
	print("zbc_saved_ids_test: all passed")
else
	print("zbc_saved_ids_test: " .. failures .. " failure(s)")
	os.exit(1)
end
