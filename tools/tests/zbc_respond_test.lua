-- Tests gamedata/scripts/zbc_respond.script and the 2 new Axon Respond / Sync OGG files.
--
-- Usage (from the repo root): lua tools/tests/zbc_respond_test.lua

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end
local function near(a, b, eps) return type(a) == "number" and math.abs(a - b) <= (eps or 1e-9) end

-- 1. Verify axon_respond.ogg and axon_sync.ogg exist, are non-empty, and have OggS magic bytes
local ogg_names = {
	"axon_respond",
	"axon_sync",
}

for _, name in ipairs(ogg_names) do
	local path = "gamedata/sounds/zbc/" .. name .. ".ogg"
	local f = io.open(path, "rb")
	check(f ~= nil, path .. " exists")
	if f then
		local data = f:read("*a")
		f:close()
		check(type(data) == "string" and #data > 100, path .. " is non-empty (" .. tostring(data and #data) .. " bytes)")
		check(data:sub(1, 4) == "OggS", path .. " has OggS magic bytes")
	end
end

-- 2. Verify zbc_audio.script on_respond_alert and on_sync
local function load_script(path, env_extra)
	local chunk = assert(loadfile(path))
	local env = setmetatable(env_extra or {}, { __index = _G })
	setfenv(chunk, env)
	assert(pcall(chunk))
	return env
end

do
	local played = {}
	local mock_sound_object = setmetatable({ s2d = 1 }, {
		__call = function(_, path)
			return {
				path = path,
				play_no_feedback = function(_, actor, mode, delay, pos, vol)
					played[#played + 1] = { path = path, vol = vol }
				end,
			}
		end,
	})
	local A = load_script("gamedata/scripts/zbc_audio.script", {
		sound_object = mock_sound_object,
		db = { actor = { id = 0 } },
		vector = function() return { x = 0, y = 0, z = 0 } end,
	})

	check(A.on_respond_alert({ audio_volume = 0.8 }) == true, "on_respond_alert plays")
	check(#played == 1 and played[1].path == "zbc\\axon_respond" and near(played[1].vol, 0.8), "respond sound & vol")
	check(A.on_sync({ audio_volume = 0.4 }) == true, "on_sync plays")
	check(#played == 2 and played[2].path == "zbc\\axon_sync" and near(played[2].vol, 0.4), "sync sound & vol")

	check(A.on_respond_alert({ audio_beeps = false }) == false, "audio_beeps=false blocks on_respond_alert")
	check(A.on_sync({ audio_beeps = false }) == false, "audio_beeps=false blocks on_sync")

	A.set_muted(true)
	check(A.on_respond_alert({}) == false, "muted blocks on_respond_alert")
	check(A.on_sync({}) == false, "muted blocks on_sync")
	A.set_muted(false)
end

-- 3. Load zbc_respond.script headless
local R = load_script("gamedata/scripts/zbc_respond.script", {})

check(R.DEFAULTS.respond_alerts == true, "DEFAULTS.respond_alerts is true")
check(R.DEFAULTS.psy_osd_corrupt == true, "DEFAULTS.psy_osd_corrupt is true")

-- Tier gating: Body 1-2 blocked, Body 3-5 allowed, nil allowed
check(R.supports_respond(1) == false, "Body 1 blocked")
check(R.supports_respond(2) == false, "Body 2 blocked")
check(R.supports_respond(3) == true, "Body 3 allowed")
check(R.supports_respond(4) == true, "Body 4 allowed")
check(R.supports_respond(5) == true, "Body 5 allowed")
check(R.supports_respond(nil) == true, "nil tier allowed")

R.reset()
local alerts_fired = {}
R.set_callbacks({
	on_alert = function(text, kind)
		alerts_fired[#alerts_fired + 1] = { text = text, kind = kind }
	end,
})

-- Body 1-2 alerts do not fire
check(R.on_companion_hit("Hip", 0.5, 1, {}) == false, "Body 1 companion hit blocked")
check(R.on_companion_down("Hip", 2, {}) == false, "Body 2 companion down blocked")
check(R.on_high_tier_mutant("chimera", 25, 2, {}) == false, "Body 2 mutant alert blocked")
check(R.is_alert_active() == false and R.get_active_alert() == nil, "no active alert when blocked")
check(#alerts_fired == 0, "no callbacks fired for Body 1-2")

-- Config respond_alerts = false blocks alerts
check(R.on_companion_down("Hip", 4, { respond_alerts = false }) == false, "respond_alerts=false blocks alert")

-- Body 3+ companion wounded & down alerts + callback + 5s expiry
check(R.on_companion_hit("Hip", 0.45, 3, {}) == true, "Body 3 companion hit fires")
check(R.is_alert_active() == true, "alert active after hit")
check(type(R.get_active_alert()) == "string" and R.get_active_alert():find("HIP") ~= nil, "hit alert mentions companion")
check(#alerts_fired == 1 and alerts_fired[1].kind == "companion_hit", "callback fired for companion_hit")

-- 15s per-type cooldown blocks repeat companion_hit, but allows companion_down (different type)
R.update(2.0, 3, {})
check(R.is_alert_active() == true, "alert still active at 2s")
check(R.on_companion_hit("Hip", 0.30, 3, {}) == false, "companion_hit blocked during 15s cooldown")
check(R.on_companion_down("Hip", 3, {}) == true, "companion_down allowed (different alert kind)")
check(R.get_active_alert() == "ALERT: SQUAD DOWN", "companion_down sets ALERT: SQUAD DOWN")

-- 5s expiry
R.update(3.0, 3, {})
check(R.is_alert_active() == true, "alert active at 3.0s (< 5.0s)")
R.update(2.1, 3, {})
check(R.is_alert_active() == false and R.get_active_alert() == nil, "alert expires after 5.0s")

-- After 15s total elapsed since companion_hit, companion_hit can fire again
R.update(10.0, 3, {})
check(R.on_companion_hit("Rogue", 0.6, 3, {}) == true, "companion_hit allowed after 15s cooldown")

-- High-tier mutant alerts (all 8/9 species) vs non-high-tier
R.reset()
alerts_fired = {}
R.set_callbacks({ on_alert = function(text, kind) alerts_fired[#alerts_fired + 1] = { text = text, kind = kind } end })
check(R.on_high_tier_mutant("boar", 15, 4, {}) == false, "boar is not high-tier mutant")
check(R.on_high_tier_mutant("flesh", 15, 4, {}) == false, "flesh is not high-tier mutant")
check(R.on_high_tier_mutant("chimera", 25, 4, {}) == true, "chimera triggers contact alert")
check(R.get_active_alert() == "CONTACT: CHIMERA", "chimera alert text matches")
check(R.on_high_tier_mutant("controller", 20, 4, {}) == false, "high_tier_mutant cooldown blocks immediate repeat")

local species_list = { "gigant", "pseudogiant", "controller", "burer", "bloodsucker", "psysucker", "karlik", "poltergeist" }
for _, sp in ipairs(species_list) do
	R.update(15.1, 4, {})
	check(R.on_high_tier_mutant(sp, 30, 4, {}) == true, sp .. " triggers high-tier alert after cooldown")
end

-- Headless poll_squad & get_psy_intensity safety
R.update(0.1, 4, {})
check(R.get_psy_intensity(nil) == 0.0, "headless get_psy_intensity returns 0")
check(near(R.get_psy_intensity({ psy_health = 0.25 }), 0.75), "get_psy_intensity reads 1 - psy_health")

-- Regression: poll_squad must treat alive() == false as dead even when health() > 0 (no falsy-ternary bug)
do
	local dead_npc = {
		alive = function() return false end,
		health = function() return 0.5 end,
		character_name = function() return "Fanatic" end,
	}
	local R_poll = load_script("gamedata/scripts/zbc_respond.script", {
		axr_companions = {
			companion_squads = {
				[1] = {
					squad_members = function()
						local done = false
						return function()
							if done then return nil end
							done = true
							return { id = 42 }
						end
					end,
				},
			},
		},
		level = {
			object_by_id = function(id) return id == 42 and dead_npc or nil end,
		},
	})
	R_poll.reset()
	R_poll.poll_squad(0.1, 4, {})
	check(R_poll.get_active_alert() == "ALERT: SQUAD DOWN", "poll_squad detects alive()==false even if health>0")
end

-- Psy OSD corruption threshold (<= 0.15 unchanged) & determinism
local sample_osd = "2026-11-26 19:00:42 AXON-B4-8821"
check(R.corrupt_osd_text(sample_osd, 0.0, 1) == sample_osd, "psy 0.0 leaves OSD unchanged")
check(R.corrupt_osd_text(sample_osd, 0.15, 1) == sample_osd, "psy 0.15 leaves OSD unchanged")

local glitched_a = R.corrupt_osd_text(sample_osd, 0.85, 42)
local glitched_b = R.corrupt_osd_text(sample_osd, 0.85, 42)
local glitched_c = R.corrupt_osd_text(sample_osd, 0.85, 43)
check(glitched_a == glitched_b, "corrupt_osd_text is deterministic for same seed")
check(glitched_a ~= sample_osd, "corrupt_osd_text glitches text at high psy")
check(glitched_a ~= glitched_c, "corrupt_osd_text varies with step_seed")
check(#glitched_a == #sample_osd, "corrupt_osd_text preserves string length")

-- Verify math.random state is untouched by corrupt_osd_text
math.randomseed(999)
local r1 = math.random()
R.corrupt_osd_text(sample_osd, 0.95, 7)
math.randomseed(999)
local r2 = math.random()
check(r1 == r2, "corrupt_osd_text does not touch math.random")

if failures > 0 then
	print(string.format("FAILED: %d check(s) failed", failures))
	os.exit(1)
end
print("OK: all zbc_respond checks passed")
