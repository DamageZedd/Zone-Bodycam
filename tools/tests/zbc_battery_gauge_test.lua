-- Tests the VHS battery gauge logic in gamedata/scripts/zbc_bodycam.script: each bar is a 25% chunk,
-- and the bar that is draining flashes once its chunk is half used up.
--
-- Usage (from the repo root): lua tools/tests/zbc_battery_gauge_test.lua

local PATH = "gamedata/scripts/zbc_bodycam.script"

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end

-- engine globals the script touches while loading: anything unknown is a harmless do-nothing stub
local stub
stub = setmetatable({}, {
	__index = function() return stub end,
	__call = function() return stub end,
	__add = function() return 0 end, __sub = function() return 0 end,
	__mul = function() return 0 end, __div = function() return 0 end,
	__unm = function() return 0 end, __concat = function() return "" end,
	__lt = function() return false end, __le = function() return false end,
})
local env = setmetatable({}, { __index = function(_, k)
	local v = _G[k]
	if v ~= nil then return v end
	return stub
end })
local chunk = assert(loadfile(PATH))
setfenv(chunk, env)
local ok, err = pcall(chunk)
check(ok, "script loads with stubs: " .. tostring(err))
local bars, flashing = rawget(env, "battery_bars"), rawget(env, "battery_flashing")
check(type(bars) == "function" and type(flashing) == "function", "gauge functions exist")

if type(bars) == "function" and type(flashing) == "function" then
	-- { charge, bars lit, draining bar flashing }
	local cases = {
		{ 1.00, 4, false }, { 0.90, 4, false }, { 0.875, 4, true }, { 0.80, 4, true }, { 0.751, 4, true },
		{ 0.75, 3, false }, { 0.63, 3, false }, { 0.625, 3, true }, { 0.55, 3, true },
		{ 0.50, 2, false }, { 0.40, 2, false }, { 0.37, 2, true }, { 0.26, 2, true },
		{ 0.25, 1, false }, { 0.13, 1, false }, { 0.12, 1, true }, { 0.01, 1, true },
		{ 0.00, 0, false }, { -1, 0, false },
	}
	for _, c in ipairs(cases) do
		local level, want_bars, want_flash = c[1], c[2], c[3]
		check(bars(level) == want_bars, ("%.3f: %d bars, got %s"):format(level, want_bars, tostring(bars(level))))
		check(flashing(level) == want_flash, ("%.3f: flashing %s, got %s"):format(level, tostring(want_flash), tostring(flashing(level))))
	end
	check(bars(nil) == 0 and flashing(nil) == false, "no battery: no bars, nothing flashes")
	check(bars("0.6") == 3, "string charge reads as a number")
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_battery_gauge_test: all checks passed")
