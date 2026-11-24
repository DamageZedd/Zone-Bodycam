-- Tests that the camera effects move instead of sitting still: interference swells and spikes,
-- storms build up, hit jolts, blood drips, the EVENT blink (zbc_fx.script), and a source check that
-- no shader hashes the raw game clock (float32 freezes that noise after ~15 minutes of play).
--
-- Usage (from the repo root): lua tools/tests/zbc_dynamic_fx_test.lua

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end

local function read(path)
	local f = assert(io.open(path, "rb"))
	local s = f:read("*a")
	f:close()
	return s
end

local function load(path)
	local env = setmetatable({}, { __index = _G })
	local chunk = assert(loadfile(path))
	setfenv(chunk, env)
	local ok, err = pcall(chunk)
	check(ok, path .. " loads: " .. tostring(err))
	return env
end

local fx = load("gamedata/scripts/zbc_fx.script")
local function near(a, b, e) return math.abs(a - b) < (e or 1e-9) end

---------------------------------------------------------------------------------------------------
-- Shaders: the clock
---------------------------------------------------------------------------------------------------
local SHADERS = {
	"gamedata/shaders/r3/zbc_lens.h", "gamedata/shaders/r3/zbc_osd.h", "gamedata/shaders/r3/zbc_ring.ps",
	"gamedata/shaders/r3/postprocess.ps", "gamedata/shaders/r3/postprocess_cm.ps",
}
for _, path in ipairs(SHADERS) do
	local n = 0
	for line in read(path):gmatch("[^\n]+") do
		n = n + 1
		local code = line:gsub("//.*$", "")
		if code:find("timers%.x") then
			local ok = code:find("float zbc_time%(%)") or code:find("timers%.x %- bus_zbc_") or code:find("timers%.x %- t0;")
			check(ok, path .. ":" .. n .. " uses the raw game clock; use zbc_time()/zbc_tstep() (or an age): " .. line)
		end
		check(not code:find("t_off"), path .. ":" .. n .. " noise shifted by a time offset is the same pattern moving; hash the frame in")
	end
end
local lens = read("gamedata/shaders/r3/zbc_lens.h")
check(not lens:find("443%.897"), "zbc_hash no longer multiplies big inputs by ~443 (float32 fraction lost)")
check(lens:find("#define ZBC_TWRAP") ~= nil, "the animation clock wraps")
-- the interference is digital codec damage, not analog tape/CRT tricks
check(lens:find("zbc_codec_cell%(") ~= nil, "codec damage: slices, bad blocks, broken frames")
for _, gone in ipairs({ "zbc_track_band", "zbc_glitch_split", "zbc_death_snow", "zbc_death_squeeze" }) do
	check(not lens:find(gone), "analog effect removed: " .. gone)
end
check(lens:find("zbc_death_block%(") ~= nil, "signal lost dies block by block")
-- face pixelation survives: no texture taps besides the snapped ones in the lens/plain samplers
local _, taps = lens:gsub("SampleLevel", "")
check(taps == 9, "zbc_lens.h texture taps unchanged (" .. taps .. "), all behind zbc_face_snap")
for _, path in ipairs({ "gamedata/shaders/r3/postprocess.ps", "gamedata/shaders/r3/postprocess_cm.ps" }) do
	local s = read(path)
	check(not s:find("SampleLevel"), path .. ": no extra taps (the analog colour split is gone)")
	check(s:find("zbc_osd_composite") > s:find("zbc_fx_color"), path .. ": the overlay is drawn after the damage, on top")
end

-- float32 check of the new hash: consecutive frames give different values hours into the game
do
	local function frac(x) return x - math.floor(x) end
	-- float32 rounding of x (enough for the magnitudes here)
	local function f32(x)
		if x == 0 then return 0 end
		local m, e = math.frexp(x)
		return math.ldexp(math.floor(m * 2 ^ 24 + 0.5) / 2 ^ 24, e)
	end
	local function hash(px, py)
		local a, b, c = f32(frac(f32(px * 0.1031))), f32(frac(f32(py * 0.1031))), f32(frac(f32(px * 0.1031)))
		local d = f32(a * (b + 33.33) + b * (c + 33.33) + c * (a + 33.33))
		a, b, c = f32(a + d), f32(b + d), f32(c + d)
		return f32(frac(f32((a + b) * c)))
	end
	for _, T in ipairs({ 60, 900, 3600, 7200 }) do
		local wrapped = T % 600
		local seen, distinct = {}, 0
		for i = 0, 5 do
			local v = hash(math.floor((wrapped + i / 24) * 24), 3.1)
			if not seen[v] then seen[v], distinct = true, distinct + 1 end
		end
		check(distinct >= 5, "tearing layout still changes every frame " .. T .. " s in (" .. distinct .. "/6)")
	end
end

-- death: Lua leaves the timing to the shader
local bodycam = read("gamedata/scripts/zbc_bodycam.script")
check(bodycam:find('send%("glitch", 0, 0, death_t, 0%)') ~= nil, "signal lost: the shader times the break-up, not a flat 1")
check(bodycam:find("compression_now%(%)") ~= nil, "compression follows the camera swing")
check(bodycam:find("fx_event and fx_event_on") ~= nil, "HUD-drawn timer blinks EVENT too")

---------------------------------------------------------------------------------------------------
-- Storm build-up and swells
---------------------------------------------------------------------------------------------------
check(fx.storm_level(nil) == 0 and fx.storm_level(-1) == 0, "no storm: 0")
check(near(fx.storm_level(0), 0.35), "a storm starts faint")
check(near(fx.storm_level(fx.STORM_BUILD), 1) and near(fx.storm_level(500), 1), "full once built up")
local prev = -1
for i = 0, 50 do
	local v = fx.storm_level(i)
	check(v >= prev, "storm never weakens while it builds (" .. i .. ")")
	prev = v
end

local lo, hi = 1, 0
for i = 0, 600 do
	local s = fx.swell(i * 0.1)
	check(s >= 0 and s <= 1, "swell stays in 0..1")
	lo, hi = math.min(lo, s), math.max(hi, s)
end
check(hi - lo > 0.6, "swell really rises and falls (" .. lo .. ".." .. hi .. ")")
check(fx.interference_out(0, 3) == 0, "no interference: none sent")
for i = 0, 100 do
	local v = fx.interference_out(0.5, i * 0.37)
	check(v >= 0.5 * 0.6 - 1e-9 and v <= 0.5 * 1.25 + 1e-9, "swelling stays within 0.6x..1.25x")
end
check(fx.interference_out(1, 1.2) <= 1, "never above 1")

---------------------------------------------------------------------------------------------------
-- Spikes
---------------------------------------------------------------------------------------------------
check(fx.spike_gap(1, 0.5) < fx.spike_gap(0.2, 0.5), "spikes come more often in strong interference")
check(fx.spike_gap(1, 0) >= 0.199 and fx.spike_gap(0, 1) <= 4, "spike gaps stay sensible")
check(fx.spike_amp(0.5, 1) > fx.spike_amp(0.5, 0) and fx.spike_amp(1, 1) <= 1, "spike height varies, capped at 1")
check(fx.spike_env(-0.1) == 0 and fx.spike_env(0) == 0, "a spike starts at 0")
check(near(fx.spike_env(fx.SPIKE_ATTACK), 1), "a spike peaks after its attack")
check(fx.spike_env(0.3) < 0.05, "a spike has died away after 0.3 s")
check(fx.spike_env(fx.SPIKE_LIFE) == 0, "a spike is over after its life")
prev = 2
for i = 1, 20 do
	local v = fx.spike_env(fx.SPIKE_ATTACK + i * 0.02)
	check(v < prev, "a spike only decays after its peak (" .. i .. ")")
	prev = v
end

local function seq(...)
	local v, i = { ... }, 0
	return function() i = i % #v + 1; return v[i] end
end
local hs = fx.hit_spikes(0.5, 1, seq(0.99, 0.5, 0.5))
check(#hs == 4, "a hard hit jolts up to 4 times (" .. #hs .. ")")
check(#fx.hit_spikes(0.5, 1, seq(0)) == 2, "at least 2 jolts")
check(hs[1][1] == 0 and near(hs[1][2], 0.8), "the first jolt is at once, as hard as the hit")
for i = 2, #hs do
	check(hs[i][1] > hs[i - 1][1], "jolts come one after another (" .. i .. ")")
	check(hs[i][2] < hs[i - 1][2], "each jolt is weaker (" .. i .. ")")
end
check(hs[#hs][1] < 1, "all jolts within a second")
check(#fx.hit_spikes(0.5, 0) == 0 and #fx.hit_spikes(0, 1) == 0, "strength 0 or no power: no jolts")
check(near(fx.hit_spikes(0.5, 0.5, seq(0))[1][2], 0.4), "strength scales the jolts")

local sp = { { 10, 1 }, { 10.5, 0.5 }, { 3, 1 } }
check(fx.spikes_value(sp, 10.03) > 0.99, "a spike peaking now shows")
check(#sp == 2, "finished spikes are dropped")
check(fx.spikes_value({ { 20, 1 } }, 19) == 0, "a jolt still to come shows nothing yet")

---------------------------------------------------------------------------------------------------
-- frame(): the interference is never one flat level
---------------------------------------------------------------------------------------------------
local t_ms = 100000
local cbs = {}
local env = load("gamedata/scripts/zbc_fx.script")
env.time_global = function() return t_ms end
env.RegisterScriptCallback = function(name, fn) cbs[name] = fn end
env.db = { actor = { alive = function() return true end, position = function() return { distance_to = function() return 99 end } end,
	psy_health = 1, radiation = 0 } }
env.zbc_bodycam = { fx_enabled = function() return true end, fx_option = function() return true end }
env.on_game_start()
local storm = true
env.surge_manager = { is_started = function() return storm end }
math.randomseed(7)

local function run(cfg, secs, dt)
	dt = dt or 0.05
	local out = {}
	for _ = 1, math.floor(secs / dt + 0.5) do
		t_ms = t_ms + dt * 1000
		local F = env.frame(cfg, dt)
		out[#out + 1] = { g = F.glitch, b = F.burst, lvl = F.level }
	end
	return out
end

env.reset()
local r = run({ fx_glitch = true }, 60)
local g_lo, g_hi, spikes_seen, lvl_end = 1, 0, 0, r[#r].lvl
for i = 400, #r do                                  -- after the smoothing has caught up
	g_lo, g_hi = math.min(g_lo, r[i].g), math.max(g_hi, r[i].g)
	if r[i].b > 0.05 and (r[i - 1].b <= 0.05) then spikes_seen = spikes_seen + 1 end
end
check(g_hi - g_lo > 0.15, "a steady storm swells (" .. g_lo .. ".." .. g_hi .. ")")
check(spikes_seen >= 10, "random spikes on a storm (" .. spikes_seen .. " in a minute)")
check(r[50].lvl < r[#r].lvl, "a storm builds up")
check(near(lvl_end, 0.55, 1e-6), "a built-up storm reaches its full level")

env.reset()
r = run({ fx_glitch = true, fx_glitch_strength = 0 }, 10)
local any = false
for _, v in ipairs(r) do any = any or v.g > 0 or v.b > 0 end
check(not any, "strength 0: no interference and no spikes at all")

storm = false
env.reset()
r = run({ fx_glitch = true }, 5)
any = false
for _, v in ipairs(r) do any = any or v.g > 0 or v.b > 0 end
check(not any, "calm: nothing")

-- a hard hit: several jolts, then quiet
env.reset()
cbs.actor_on_before_hit({ power = 0.6 })
r = run({ fx_glitch = true }, 1.5, 0.01)
local peaks = 0
for i = 2, #r - 1 do
	if r[i].b > r[i - 1].b and r[i].b >= r[i + 1].b and r[i].b > 0.05 then peaks = peaks + 1 end
end
check(peaks >= 2, "a hit jolts the picture more than once (" .. peaks .. ")")
check(r[#r].b == 0, "the jolts are over after 1.5 s")
cbs.actor_on_before_hit({ power = 0.6 })
run({ fx_glitch = false }, 0.1)
r = run({ fx_glitch = true }, 0.5)
any = false
for _, v in ipairs(r) do any = any or v.b > 0 end
check(not any, "turning interference off drops the queued jolts")

---------------------------------------------------------------------------------------------------
-- Blood drips and the camera swing
---------------------------------------------------------------------------------------------------
check(near(fx.drip_step(0, fx.DRIP_TIME, 0), 1), "drips run down in DRIP_TIME seconds")
check(fx.drip_step(0, 1, 1) > fx.drip_step(0, 1, 0) * 3, "swinging the camera makes them run faster")
check(fx.drip_step(0.99, 5, 1) > 1, "drips keep running past 1 until the blood fades")
check(fx.drip_step(2.99, 50, 1) == fx.DRIP_MAX and fx.drip_step(0.5, -1, 0) == 0.5, "drip progress capped, never runs back")
-- the drips move in stick-slip steps along gravity and leave a trail (shader source)
check(lens:find("stick%-slip") ~= nil and lens:find("teardrop") ~= nil, "drips run in stick-slip steps with a teardrop head")
check(lens:find("min%(bus_zbc_blood%[i%], 3%.0%)") ~= nil, "the shader takes drip progress past 1 (matches DRIP_MAX)")

local s0, y0 = fx.cam_turn(0, 0, 1, 0, 0, 1, 0.016)
check(s0 == 0 and y0 == 0, "camera still: no swing")
check(select(1, fx.cam_turn(nil, nil, nil, 0, 0, 1, 0.016)) == 0, "first frame: no swing")
local sh, yaw = fx.cam_turn(0, 0, 1, 1, 0, 0, 1)                -- a quarter turn to the right in 1 s
check(near(yaw, math.pi / 2, 1e-6), "yaw rate: + to the right (" .. yaw .. ")")
check(sh > 0.4 and sh < 0.6, "shake follows the angular speed (" .. sh .. ")")
local _, yw = fx.cam_turn(math.sin(3.1), 0, math.cos(3.1), math.sin(-3.1), 0, math.cos(-3.1), 1)
check(yw > 0 and yw < 0.2, "a small turn across the back is small (" .. yw .. ")")
check(fx.lean_target == nil, "drips don't lean or swing with the camera (viscous blood only moves at the head)")
local lens_now = read("gamedata/shaders/r3/zbc_lens.h")
check(not lens_now:find("float2 sway") and not lens_now:find("bus_zbc_motion%.yz %* ZBC_INTENSITY %* 0%.35"), "the blood trail never sways with the camera")
check(lens_now:find("rivulet") ~= nil and lens_now:find("stays where it was laid") ~= nil, "the rivulet behind the head stays put")
-- drips run out of the middle of the splat, and its size decides whether and how far it drips
check(lens_now:find("float2 c0   = c %+ float2%([^,]+, 0%.0%)") ~= nil, "drips start at the splat's middle, not its edge")
check(lens_now:find("n_drip = %(rb < 0%.032%) %? 0") ~= nil, "a small splat doesn't drip")
check(lens_now:find("cap    = lerp%(0%.06, 1%.6, sz %* sz%)") ~= nil and lens_now:find("tl   = min%(travel, cap%)") ~= nil,
      "a large splat runs off the bottom of the lens (cap 1.6 > lens height), a mid one stops short")
check(not lens_now:find("n_drip = %(k < 2%)"), "drip count no longer depends on the splat's slot")
-- the fresh splat is an irregular blob, not a symmetric star
check(not lens_now:find("atan2%(d%.y, d%.x%) %* 4%.0"), "no 4-point star wobble on the splat edge")
check(lens_now:find("for %(int q = 0; q < 2; q%+%+%)") ~= nil, "splat has merged side lobes")
check(lens_now:find("stretch along the flight") ~= nil, "satellite droplets are stretched along the way they flew")
check(lens_now:find("%[loop%] for %(int k = 0; k < 9; k%+%+%)") ~= nil, "splat loop is a real loop (keeps the shader small)")

check(near(fx.compression_level(0.35, 0), 0.35), "still camera: the compression set in the MCM")
check(fx.compression_level(0.35, 1) > 0.5 and fx.compression_level(1, 1) == 1, "swinging blocks it up, capped")
check(fx.compression_level(0, 1) == 0, "compression off stays off")

env.reset()
local F = env.frame({ lens_dirt = true }, 0.05)
env.blood_add(F.blood, t_ms / 1000)
for _ = 1, 20 do t_ms = t_ms + 50; env.frame({ lens_dirt = true }, 0.05) end
check(F.blood[1].drip > 0.05 and F.blood[1].drip < 0.1, "blood on the lens: the drips start running (" .. F.blood[1].drip .. ")")

-- blood stacks: every hit adds a splatter, each stays until it has faded
local list = {}
fx.blood_add(list, 10)
fx.blood_add(list, 12)
check(#list == 2 and list[1].t == 10 and list[2].t == 12, "a second hit adds blood, it doesn't restart the first")
for i = 1, 5 do fx.blood_add(list, 12 + i) end
check(#list == fx.BLOOD_SLOTS and list[1].t == 14, "with every slot full the oldest splatter gives way")
fx.blood_step(list, 14 + fx.BLOOD_LIFE - 0.1, 0.1, 0)
check(#list == fx.BLOOD_SLOTS, "splatters stay until they have faded")
fx.blood_step(list, 15 + fx.BLOOD_LIFE, 0.1, 0)
check(#list == fx.BLOOD_SLOTS - 2 and list[1].t == 16, "faded splatters are dropped, the rest stay")
check(list[1].drip > 0, "each splatter's drips run on their own")
check(lens:find("for %(int i = 0; i < 4; i%+%+%)") ~= nil and lens:find("bus_zbc_dirt%[i%]") ~= nil, "the shader draws every splatter")
check(fx.BLOOD_LIFE == 26 and lens:find("age < 26%.0") ~= nil, "Lua keeps a splatter exactly as long as the shader shows it")
local bc = read("gamedata/scripts/zbc_bodycam.script")
check(bc:find('blood      = "zbc_blood"') ~= nil and bc:find('send%("blood",  bd%(1%)') ~= nil, "the drip progress of every splatter is sent")

---------------------------------------------------------------------------------------------------
-- EVENT blinks
---------------------------------------------------------------------------------------------------
check(not fx.event_blink(nil) and not fx.event_blink(-1), "nothing to blink")
local flashes, was = 0, false
for i = 0, 59 do
	local on = fx.event_blink(i / 100 + 0.005)
	if on and not was then flashes = flashes + 1 end
	was = on
end
check(flashes == 3, "three quick flashes first (" .. flashes .. ")")
check(fx.event_blink(0.6) and fx.event_blink(1.05) and not fx.event_blink(1.15) and fx.event_blink(1.41),
	"then a steady blink (0.5 s lit of every 0.8 s)")

env.reset()
cbs.actor_on_weapon_fired(nil)
local lit, dark = 0, 0
for _ = 1, 100 do
	t_ms = t_ms + 40
	F = env.frame({ event_marker = true }, 0.04)
	if F.event then
		if F.event_on then lit = lit + 1 else dark = dark + 1 end
	end
end
check(lit > 0 and dark > 0, "EVENT blinks while it is shown (" .. lit .. " lit, " .. dark .. " dark)")
t_ms = t_ms + 2000
F = env.frame({ event_marker = true }, 0.04)
check(not F.event and not F.event_on, "EVENT goes after 5 s")
F = env.frame({ event_marker = false }, 0.04)
check(not F.event_on, "EVENT option off: never lit")

if failures == 0 then
	print("zbc_dynamic_fx_test: all checks passed")
else
	print("zbc_dynamic_fx_test: " .. failures .. " failure(s)")
	os.exit(1)
end
