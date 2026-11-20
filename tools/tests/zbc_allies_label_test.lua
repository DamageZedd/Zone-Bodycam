-- Tests the ally name label text in gamedata/scripts/zbc_allies.script: upper case like the overlay,
-- trimmed, cut to the label length, and safe on missing names.
--
-- Usage (from the repo root): lua tools/tests/zbc_allies_label_test.lua

local PATH = "gamedata/scripts/zbc_allies.script"

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end

local env = setmetatable({}, { __index = _G })
local chunk = assert(loadfile(PATH))
setfenv(chunk, env)
local ok, err = pcall(chunk)
check(ok, "script loads: " .. tostring(err))
local lt = rawget(env, "label_text")
check(type(lt) == "function", "label_text exists")

if type(lt) == "function" then
	check(lt("Vova Tramp") == "VOVA TRAMP", "upper case")
	check(lt("  Artyom Favorite \t") == "ARTYOM FAVORITE", "trimmed")
	check(#lt(string.rep("Ab", 40)) == 24, "cut to 24 characters")
	check(lt(nil) == "" and lt(42) == "", "no name: empty label")
	check(lt("") == "", "empty name: empty label")
end

-- decode effect
local dt = rawget(env, "decode_text")
check(type(dt) == "function", "decode_text exists")
if type(dt) == "function" then
	local name = "VOVA TRAMP"
	local s0, done0 = dt(name, 0, 5)
	check(#s0 == #name and not done0, "starts scrambled, same length")
	check(s0:sub(5, 5) == " ", "spaces stay spaces while scrambled")
	check(s0 ~= name, "the start is not the plain name")
	local full = env.DECODE_DELAY + #name * env.DECODE_STEP
	local s1, done1 = dt(name, full, 5)
	check(s1 == name and done1, "fully decoded after the reveal time")
	-- letters lock one after another from the left
	local mid = env.DECODE_DELAY + 3.5 * env.DECODE_STEP
	local sm = dt(name, mid, 5)
	check(sm:sub(1, 4) == "VOVA", "the first letters have locked")
	local prev_locked = 0
	for k = 0, 40 do
		local t = k * 0.01
		local s = dt(name, t, 5)
		local locked = 0
		for i = 1, #name do
			if s:sub(i, i) == name:sub(i, i) and t >= env.DECODE_DELAY + (i - 1) * env.DECODE_STEP then locked = i else break end
		end
		check(locked >= prev_locked, ("t=%.2f: locked letters never go back"):format(t))
		prev_locked = locked
	end
	check(dt("ABC", -1, 1) ~= nil, "negative time (faction delay) is fine")
	check(dt("", 0, 1) == "", "empty text stays empty")
	-- the scramble changes over time and differs per NPC
	check(dt(name, 0.0, 5) ~= dt(name, 0.06, 5), "scramble flickers")
	check(dt(name, 0.0, 5) ~= dt(name, 0.0, 6), "different NPCs scramble differently")
	-- only drawable characters
	for k = 0, 30 do
		local s = dt("XXXXXXXXXXXXXXXXXXXX", k * 0.013, k)
		check(not s:find("[^%w%+=/<>#%%]"), "scramble uses only glyph-atlas characters: " .. s)
	end
end

-- faction text
local ft = rawget(env, "faction_text")
check(type(ft) == "function", "faction_text exists")
if type(ft) == "function" then
	env.game = { translate_string = function(id) return ({ csky = "Clear Sky", dolg = "Duty" })[id] or id end }
	local function npc(comm) return { character_community = function() return comm end } end
	check(ft(npc("csky")) == "CLEAR SKY", "translated and upper case")
	check(ft(npc("monolith")) == "MONOLITH", "untranslated id falls back to the id")
	check(ft(npc(nil)) == "" and ft(nil) == "", "no community: empty")
	check(#ft(npc(string.rep("x", 50))) == env.FACTION_CHARS, "cut to FACTION_CHARS")
end

-- box colour reveal: white first, then the relation colour once the name has decoded
local rm = rawget(env, "reveal_mix")
check(type(rm) == "function", "reveal_mix exists")
if type(rm) == "function" then
	check(rm(0, 10) == 0, "white when the box appears")
	local name_done = env.DECODE_DELAY + 20 * env.DECODE_STEP
	check(rm(name_done - 0.01, 20) == 0, "still white while a long name decodes")
	check(rm(name_done + env.COLOR_FADE + 0.01, 20) == 1, "full colour after the fade")
	check(rm(env.REVEAL_MIN - 0.01, 1) == 0, "short names still stay white for REVEAL_MIN")
	local prev = 0
	for k = 0, 200 do
		local v = rm(k * 0.01, 12)
		check(v >= prev and v >= 0 and v <= 1, "reveal only moves towards the colour")
		prev = v
	end
	check(rm(nil, nil) == 0, "no timer yet: white")
end

-- identification by distance (after the Identification UI mod)
local ir, rs = rawget(env, "identify_rate"), rawget(env, "reveal_speed")
check(type(ir) == "function" and type(rs) == "function", "identification functions exist")
if type(ir) == "function" and type(rs) == "function" then
	local function near(a, b) return math.abs(a - b) < 1e-6 end
	check(ir(30, 75) == math.huge and ir(50, 75) == math.huge, "within 50 m: identified at once")
	-- the mod: 100 / ((d^2 - 2500) * 0.1) / fov * 20 * 0.2 per 0.2 s tick
	local per_tick = 100 / ((60 * 60 - 2500) * 0.1) / 75 * 20 * 0.2
	check(near(ir(60, 75), per_tick * 5), "60 m matches the mod's per-tick gain x 5 ticks a second")
	check(ir(100, 75) < ir(60, 75), "further away identifies slower")
	check(ir(100, 18) > ir(100, 75), "through a scope (smaller fov) identifies faster")
	check(ir(100, nil) > 0, "missing fov falls back to 75")
	local t_full = 0.5
	check(rs(t_full, true, 300, false, 75) == 1, "known stalker: quick decode wherever they are")
	check(rs(t_full, false, 40, false, 75) == 1, "near stalker: quick decode even when not looked at")
	check(rs(t_full, false, 120, false, 75) == 0, "far stalker you are not looking at: paused")
	local s = rs(t_full, false, 120, true, 75)
	check(s > 0 and s < 1 and near(s, ir(120, 75) * t_full), "far stalker you look at: decodes at the mod's rate")
	check(rs(t_full, false, 51, true, 1) == 1, "never faster than the quick decode")
	-- seconds to identify at 100 m: about 28 s plain, about 7 s through a 4x scope
	local plain, scoped = 1 / ir(100, 75), 1 / ir(100, 75 / 4)
	check(plain > 25 and plain < 31 and scoped > 6 and scoped < 8, ("100 m: %.1f s plain, %.1f s scoped"):format(plain, scoped))
end

-- scope zoom
local zf = rawget(env, "zoom_factor")
check(type(zf) == "function", "zoom_factor exists")
if type(zf) == "function" then
	local function near(a, b) return math.abs(a - b) < 1e-6 end
	check(zf(75, 75) == 1, "no scope: 1")
	check(zf(75, 80) == 1, "wider than normal: 1")
	check(near(zf(90, 2 * math.deg(math.atan(0.25))), 4), "4x scope from 90 degrees")
	check(zf(75, 0.1) == 1 and zf(nil, 30) == 1 and zf(75, nil) == 1, "bad input: 1")
	check(zf(170, 0.6) <= 40, "capped at MAX_ZOOM")
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_allies_label_test: all checks passed")
