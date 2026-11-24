-- Regression test: signal lost has to play when a death screen mod stops game time on death.
-- Death Like Romeo runs "time_factor 0" in actor_on_before_death, which stops time_global() and the
-- shader's timers.x, so a death clock on game time sat at 0 s and nothing showed. The script now
-- sends the seconds since death on the real clock (time_continual) in the glitch lane's w, ticked by a
-- HUD window, and the shader takes the larger of the two ages.
--
-- Usage (from the repo root): lua tools/tests/zbc_signal_lost_clock_test.lua

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end
local function near(a, b) return type(a) == "number" and math.abs(a - b) < 1e-6 end

local stub
stub = setmetatable({}, {
	__index = function() return stub end,
	__call = function() return stub end,
	__add = function() return 0 end, __sub = function() return 0 end,
	__mul = function() return 0 end, __div = function() return 0 end,
	__unm = function() return 0 end, __concat = function() return "" end,
	__lt = function() return false end, __le = function() return false end,
})

-- the game, with time stopped: time_global() never moves, time_continual() does
local real_ms, game_ms = 100000, 50000
local alive = false
local glitch = {}                       -- every glitch lane write, in order
local added, removed = {}, {}
local hud = {
	AddDialogToRender = function(_, w) added[#added + 1] = w end,
	RemoveDialogToRender = function(_, w) removed[#removed + 1] = w end,
}
local game = {
	time_continual = function() return real_ms end,
	time_global = function() return game_ms end,
	get_hud = function() return hud end,
	shader_bus = {
		try_register = function(id) return id end,
		set = function(tok, x, y, z, w)
			if tok == "zbc_glitch" then glitch[#glitch + 1] = { x, y, z, w } end
		end,
	},
	db = { actor = { alive = function() return alive end } },
	ui_mcm = false,                     -- settings come from the defaults (enabled)
}

local env = setmetatable({}, { __index = function(_, k)
	if game[k] ~= nil then return game[k] end
	local v = _G[k]
	if v ~= nil then return v end
	return stub
end })
local chunk = assert(loadfile("gamedata/scripts/zbc_bodycam.script"))
setfenv(chunk, env)
local ok, err = pcall(chunk)
check(ok, "zbc_bodycam.script loads: " .. tostring(err))

local signal_lost, tick, age = rawget(env, "signal_lost"), rawget(env, "death_clock_tick"), rawget(env, "death_age")
check(type(tick) == "function" and type(age) == "function", "death_clock_tick and death_age exist")

if type(signal_lost) == "function" and type(tick) == "function" and type(age) == "function" then
	pcall(env.actor_on_first_update)                -- loads the settings (the rest runs on stubs)
	added, removed, glitch = {}, {}, {}
	check(age() == 0, "alive: no death age")

	signal_lost(50)                                 -- death at game time 50 s
	local last = glitch[#glitch]
	check(last and last[3] == 50, "the death time goes to the shader (glitch.z)")
	check(#added == 1, "a window is added to tick the clock while game time is stopped")

	real_ms = real_ms + 1500                        -- 1.5 s of real time, game time stopped
	tick()
	last = glitch[#glitch]
	check(last and last[3] == 50 and near(last[4], 1.5),
		"with game time stopped the death age still grows on the real clock: " .. tostring(last and last[4]))
	check(near(age(), 1.5), "death_age is real seconds since death")

	real_ms = real_ms + 2000
	tick()
	last = glitch[#glitch]
	check(last and near(last[4], 3.5), "and keeps growing (3.5 s): " .. tostring(last and last[4]))

	-- revived (a reload or Soulslike): the clock stops and the lane is cleared
	alive = true
	pcall(env.actor_on_update)                      -- the revive branch runs first; the rest is stubs
	check(age() == 0, "revived: no death age")
	check(#removed == 1, "revived: the clock window is removed")
	local n = #glitch
	tick()
	check(#glitch == n, "revived: the clock no longer writes the lane")

	-- a level unload while dead also stops it
	alive = false
	signal_lost(80)
	real_ms = real_ms + 1000
	check(near(age(), 1), "dead again: the clock runs from the new death")
	local before = #removed
	pcall(env.actor_on_net_destroy)
	check(age() == 0 and #removed > before, "level unload stops the clock and removes the window")
end

-- the window's Update drives the tick
local bc = io.open("gamedata/scripts/zbc_bodycam.script", "rb"):read("*a")
check(bc:find("function ZbcDeathClock:Update%(%)%s+CUIScriptWnd%.Update%(self%)%s+death_clock_tick%(%)") ~= nil,
	"the ZbcDeathClock window ticks the clock every frame")
check(bc:find('send("glitch", F.glitch, F.burst, F.death_t, death_age())', 1, true) ~= nil,
	"the per-frame glitch write keeps the real-clock age instead of zeroing it")

-- the shader takes the larger of the game-clock and real-clock ages, and its animation clock runs on
local lens = io.open("gamedata/shaders/r3/zbc_lens.h", "rb"):read("*a")
check(lens:find("max(max(timers.x - bus_zbc_glitch.z, 0.0), bus_zbc_glitch.w)", 1, true) ~= nil,
	"zbc_death_age uses the real-clock age in glitch.w when game time stopped")
check(lens:find("float zbc_time() { return fmod(max(timers.x, 0.0) + zbc_death_lag(), ZBC_TWRAP); }", 1, true) ~= nil,
	"after death the animation clock keeps running (text flicker, codec damage)")

if failures == 0 then
	print("zbc_signal_lost_clock_test: all passed")
else
	print("zbc_signal_lost_clock_test: " .. failures .. " failure(s)")
	os.exit(1)
end
