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

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_fx_test: all checks passed")
