-- Tests the compression effect: a steady amount set by the camera tier (zbc_tiers.script), built up
-- while the camera turns and eased back after (zbc_fx.compression_env / compression_level), never
-- snapping. Regression for "it builds up and then instantly disappears": the shader reset its shadow
-- blocking on every keyframe (a 1.6 s sawtooth) and the swing boost fell back linearly in ~0.3 s.
--
-- Usage (from the repo root): lua tools/tests/zbc_compression_test.lua

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end
local function near(a, b, e) return type(a) == "number" and math.abs(a - b) <= (e or 1e-9) end

local function load(path)
	local env = setmetatable({}, { __index = _G })
	local chunk = assert(loadfile(path))
	setfenv(chunk, env)
	local ok, err = pcall(chunk)
	check(ok, path .. " loads: " .. tostring(err))
	return env
end
local function read(path)
	local f = assert(io.open(path, "rb"))
	local s = f:read("*a")
	f:close()
	return (s:gsub("\r\n", "\n"))
end

local fx = load("gamedata/scripts/zbc_fx.script")
local T  = load("gamedata/scripts/zbc_tiers.script")

---------------------------------------------------------------------------------------------------
-- Tier baselines: Body 1 the most, Body 5 the least; Body 4, no item or tier limits off = the MCM value
---------------------------------------------------------------------------------------------------
local MCM = 0.35
local clamps = { compression = { 0, 1 } }
local function base(tier) return T.apply({ compression = MCM }, tier, clamps).compression end
local b = {}
for t = 1, 5 do b[t] = base(t) end
check(b[1] > b[2] and b[2] > b[3] and b[3] > b[4] and b[4] > b[5],
	"baseline falls from Body 1 to Body 5 (" .. table.concat(b, ", ") .. ")")
check(near(b[4], MCM), "Body 4 baseline = the MCM value")
check(near(base(nil), b[4]), "no item / tier limits off: the Body 4 baseline")
check(b[5] > 0, "Body 5 still has some compression")
check(T.apply({ compression = 0 }, 1, clamps).compression == 0, "compression off in the MCM stays off on every tier")

---------------------------------------------------------------------------------------------------
-- The envelope: attack while turning, smooth exponential release, never below the baseline
---------------------------------------------------------------------------------------------------
local dt = 1 / 60
local env, lvl = 0, {}
local function run(shake, secs)
	for _ = 1, math.floor(secs / dt + 0.5) do
		env = fx.compression_env(env, shake, dt)
		lvl[#lvl + 1] = fx.compression_level(b[4], env)
	end
end
run(0, 1)
check(near(lvl[#lvl], b[4]), "still camera: the steady baseline")
check(near(lvl[1], lvl[#lvl]), "the baseline holds steady while still")
local n0 = #lvl
run(1, 1.0)
local peak = lvl[#lvl]
check(peak > b[4] * 1.7, "a turn builds it up (" .. peak .. ")")
local t_half
for i = n0 + 1, #lvl do
	check(lvl[i] >= lvl[i - 1] - 1e-12, "builds up without dipping")
	if not t_half and lvl[i] - b[4] >= 0.5 * (peak - b[4]) then t_half = (i - n0) * dt end
end
check(t_half and t_half > 0.08 and t_half < 0.4, "builds up over a fraction of a second (half way at " .. tostring(t_half) .. " s)")
local n1 = #lvl
run(0, 4)
local max_drop = 0
for i = n1 + 1, #lvl do
	max_drop = math.max(max_drop, lvl[i - 1] - lvl[i])
	check(lvl[i] <= lvl[i - 1] + 1e-12, "falls off without bouncing")
	check(lvl[i] >= b[4] - 1e-12, "never below the baseline")
end
check(max_drop < (peak - b[4]) * 0.03, "no snap: the biggest one-frame drop is under 3% of the build-up (" .. max_drop .. ")")
local after = function(s) return lvl[n1 + math.floor(s / dt + 0.5)] end
check(after(0.5) - b[4] > 0.45 * (peak - b[4]), "still well above the baseline 0.5 s after the turn")
check(after(1.5) - b[4] < 0.25 * (peak - b[4]), "mostly settled 1.5 s after the turn")
check(after(4) - b[4] < 0.02 * (peak - b[4]), "back to the baseline after a few seconds")
-- frame-to-frame jitter in the turn rate is smoothed, not passed through
env = 0.5
local e1 = fx.compression_env(env, 1, dt)
local e2 = fx.compression_env(e1, 0, dt)
check(math.abs(e1 - 0.5) < 0.05 and math.abs(e2 - e1) < 0.05, "a one-frame spike in the turn rate barely moves it")
check(fx.compression_env(0.4, 1, 0) == 0.4 and fx.compression_env(nil, nil, dt) == 0, "no time, no change; nil-safe")
check(fx.compression_level(1, 1) == 1 and fx.compression_level(0, 1) == 0, "capped at 1; off stays off")
-- every tier keeps its order while turning too
check(fx.compression_level(b[1], 1) > fx.compression_level(b[5], 1), "Body 1 blocks up more than Body 5 in a turn")

---------------------------------------------------------------------------------------------------
-- Wiring: zbc_fx runs the envelope each frame, zbc_bodycam sends it, the shader holds it steady
---------------------------------------------------------------------------------------------------
local fxs = read("gamedata/scripts/zbc_fx.script")
check(fxs:find("F%.shake, F%.comp, F%.cdx, F%.cdy, F%.cdz = 0, 0, nil, nil, nil") ~= nil, "reset clears the envelope")
check(fxs:find("F%.comp = compression_env%(F%.comp, shake_now, dt%)") ~= nil, "zbc_fx runs the envelope every frame")
local bc = read("gamedata/scripts/zbc_bodycam.script")
check(bc:find("compression_level%(cfg%.compression, fx_comp%)") ~= nil, "the sensor lane gets the tier baseline + envelope")
check(bc:find("fx_shake") == nil, "the raw swing value no longer drives compression")
local lens = read("gamedata/shaders/r3/zbc_lens.h")
check(lens:find("frac%(zbc_time%(%) / 1%.6%)") == nil and lens:find("gop") == nil,
	"the shader no longer resets the shadow blocking every keyframe (the sawtooth snap)")
check(lens:find("zbc_shadow_blocks%(y_out, uv, dc %* 0%.7%)") ~= nil, "shadow blocking is a steady share of the compression level")

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_compression_test: all checks passed")
