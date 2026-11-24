-- Tests that signal lost is the only death screen while it is on (zbc_fx.script): Death Like Romeo's
-- death handler (a local in true_first_person_death.script, registered by its on_game_start) is taken
-- off actor_on_before_death, called by us only when signal lost does not play, and given back when
-- signal lost is switched off.
--
-- Usage (from the repo root): lua tools/tests/zbc_death_screen_test.lua

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end

-- the callback system
local registered = {}

-- a stand-in for true_first_person_death.script: its death handler is a local upvalue of on_game_start
local romeo_calls = 0
local romeo
do
	local function on_actor_before_death() romeo_calls = romeo_calls + 1 end
	local function on_main_menu_init() end
	romeo = {
		on_game_start = function()
			registered[on_main_menu_init] = true
			registered[on_actor_before_death] = true
		end,
	}
	romeo.on_game_start()
end
_G.true_first_person_death = romeo           -- the game reaches script namespaces through _G

local opt = { signal_lost = true }
local powered = true
local lost_calls = 0
local game = {
	true_first_person_death = romeo,
	RegisterScriptCallback = function(name, f) if name == "actor_on_before_death" then registered[f] = true end end,
	UnregisterScriptCallback = function(name, f) if name == "actor_on_before_death" then registered[f] = nil end end,
	printf = function() end,
	time_global = function() return 1000 end,
	zbc_bodycam = {
		fx_option = function(id) return opt[id] and true or false end,
		fx_enabled = function() return powered end,
		signal_lost = function() lost_calls = lost_calls + 1 end,
	},
}
local env = setmetatable({}, { __index = function(_, k)
	if game[k] ~= nil then return game[k] end
	return _G[k]
end })
local chunk = assert(loadfile("gamedata/scripts/zbc_fx.script"))
setfenv(chunk, env)
local ok, err = pcall(chunk)
check(ok, "zbc_fx.script loads: " .. tostring(err))

local take, death = rawget(env, "take_death_screens"), rawget(env, "actor_on_before_death")
check(type(take) == "function", "take_death_screens exists")

local function n_registered()
	local n = 0
	for _ in pairs(registered) do n = n + 1 end
	return n
end

if type(take) == "function" then
	local present = function(name) return name == "true_first_person_death" end
	check(n_registered() == 2, "setup: Romeo registered two callbacks")

	-- Romeo not installed: nothing happens
	take(true, function() return false end)
	check(n_registered() == 2, "Romeo not installed: nothing is taken")

	-- signal lost on: Romeo's death handler comes off actor_on_before_death, nothing else does
	take(true, present)
	check(n_registered() == 1, "signal lost on: Romeo's death handler is taken off the callback")
	take(true, present)
	check(n_registered() == 1, "taking twice is harmless")

	-- death with the camera on: only signal lost plays
	death(nil, {})
	check(lost_calls == 1 and romeo_calls == 0, "death: signal lost plays, Romeo's screen does not")

	-- camera off: Romeo's screen plays instead, so there is still a death screen
	powered = false
	death(nil, {})
	check(lost_calls == 1 and romeo_calls == 1, "camera off: Romeo's death screen plays instead")
	powered = true

	-- a death another mod cancels (Soulslike respawn): Romeo's own handling runs, ours does not
	death(nil, { ret_value = false })
	check(lost_calls == 1 and romeo_calls == 2, "cancelled death: Romeo handles it, no signal lost")

	-- signal lost switched off: Romeo's handler is registered again
	take(false, present)
	check(n_registered() == 2, "signal lost off: Romeo's death handler is given back")
	opt.signal_lost = false
	death(nil, {})
	check(lost_calls == 1 and romeo_calls == 2, "signal lost off: we no longer call Romeo's handler ourselves")
end

-- the option is applied on load and when the settings change
local src = io.open("gamedata/scripts/zbc_fx.script", "rb"):read("*a")
check(src:find("pcall(take_death_screens, want_signal_lost())", 1, true) ~= nil, "taken over on the first update")
check(src:find('RegisterScriptCallback("on_option_change", on_option_change)', 1, true) ~= nil, "re-applied on option change")

if failures == 0 then
	print("zbc_death_screen_test: all passed")
else
	print("zbc_death_screen_test: " .. failures .. " failure(s)")
	os.exit(1)
end
