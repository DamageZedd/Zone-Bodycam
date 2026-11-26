-- Tests gamedata/scripts/zbc_audio.script and the 7 generated OGG files in gamedata/sounds/zbc/.
--
-- Usage (from the repo root): lua tools/tests/zbc_audio_test.lua

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end
local function near(a, b, eps) return type(a) == "number" and math.abs(a - b) <= (eps or 1e-9) end

-- 1. Verify all 7 .ogg files exist, are non-empty, and have OggS magic bytes
local ogg_names = {
	"axon_start",
	"axon_stop",
	"axon_interval",
	"axon_event",
	"axon_low_batt",
	"axon_mute",
	"axon_mic_clip",
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

-- 2. Verify safe no-op when sound_object / db.actor are absent
local function load_audio(env_extra)
	local chunk = assert(loadfile("gamedata/scripts/zbc_audio.script"))
	local env = setmetatable(env_extra or {}, { __index = _G })
	setfenv(chunk, env)
	assert(pcall(chunk))
	return env
end

do
	local A_headless = load_audio({})
	check(A_headless.on_rec_start() == false, "headless on_rec_start returns false safely")
	check(A_headless.on_gunshot(1) == false, "headless on_gunshot returns false safely")
	A_headless.update(125, true, 5, 1)
	check(true, "headless update does not error")
end

-- 3. Full behavioral tests with mocked X-Ray sound_object, db.actor, vector
local played = {}
local function make_mock_env()
	played = {}
	local mock_sound_object = setmetatable({ s2d = 1 }, {
		__call = function(_, path)
			return {
				path = path,
				play_no_feedback = function(_, actor, mode, delay, pos, vol)
					played[#played + 1] = { path = path, actor = actor, mode = mode, vol = vol }
				end,
			}
		end,
	})
	return load_audio({
		sound_object = mock_sound_object,
		db = { actor = { id = 0 } },
		vector = function() return { x = 0, y = 0, z = 0 } end,
	})
end

local A = make_mock_env()

-- Triggers & defaults
check(A.on_rec_start() == true, "on_rec_start plays with default cfg")
check(#played == 1 and played[1].path == "zbc\\axon_start" and near(played[1].vol, 0.5), "start sound & default vol 0.5")

check(A.on_rec_stop() == true, "on_rec_stop plays")
check(#played == 2 and played[2].path == "zbc\\axon_stop", "stop sound")

check(A.on_event() == true, "on_event plays")
check(#played == 3 and played[3].path == "zbc\\axon_event", "event sound")

check(A.on_signal() == true, "on_signal plays")
check(#played == 4 and played[4].path == "zbc\\axon_event", "signal uses axon_event")

-- audio_beeps = false suppresses UI beeps
played = {}
check(A.on_rec_start({ audio_beeps = false }) == false, "audio_beeps=false suppresses start")
check(A.on_rec_stop({ audio_beeps = false }) == false, "audio_beeps=false suppresses stop")
check(A.on_event({ audio_beeps = false }) == false, "audio_beeps=false suppresses event")
check(A.on_mute_toggle(true, { audio_beeps = false }) == false, "audio_beeps=false suppresses mute_toggle sound")
check(#played == 0, "no sounds played when audio_beeps=false")
A.set_muted(false)

-- Volume clamping
played = {}
A.on_rec_start({ audio_volume = 0 })
check(#played == 0, "audio_volume=0 plays nothing")
A.on_rec_start({ audio_volume = 2.5 })
check(#played == 1 and near(played[1].vol, 1.0), "audio_volume clamped to 1.0")

-- 2-minute interval beep: off by default, on when audio_interval_beep = true, only while recording
A.reset()
played = {}
A.update(125, true, 80, 4, {})
check(#played == 0, "interval beep off by default")

A.reset()
played = {}
A.update(125, false, 80, 4, { audio_interval_beep = true })
check(#played == 0, "interval beep does not fire when not recording")

A.update(119, true, 80, 4, { audio_interval_beep = true })
check(#played == 0, "interval beep does not fire before 120s")
A.update(2, true, 80, 4, { audio_interval_beep = true })
check(#played == 1 and played[1].path == "zbc\\axon_interval", "interval beep fires at 120s")

-- Low-battery threshold hysteresis (10%, 5%, reset > 15%)
A.reset()
played = {}
A.update(1, true, 12, 4, {})
check(#played == 0, "no low_batt above 10%")
A.update(1, true, 10, 4, {})
check(#played == 1 and played[1].path == "zbc\\axon_low_batt", "low_batt chirps at 10%")
A.update(1, true, 7, 4, {})
check(#played == 1, "low_batt does not repeat between 10% and 5%")
A.update(1, true, 5, 4, {})
check(#played == 2 and played[2].path == "zbc\\axon_low_batt", "low_batt chirps at 5%")
A.update(1, true, 2, 4, {})
check(#played == 2, "low_batt does not repeat below 5%")

-- Recharge to 15% does NOT reset (> 15% required)
A.update(1, true, 15, 4, {})
A.update(1, true, 8, 4, {})
check(#played == 2, "recharge to 15% does not reset hysteresis")

-- Recharge > 15% resets hysteresis
A.update(1, true, 16, 4, {})
A.update(1, true, 9, 4, {})
check(#played == 3 and played[3].path == "zbc\\axon_low_batt", "recharge > 15% resets low_batt hysteresis")

-- audio_low_batt = false suppresses chirp
A.reset()
played = {}
A.update(1, true, 4, 4, { audio_low_batt = false })
check(#played == 0, "audio_low_batt=false suppresses chirp")

-- Mute suppression
A.reset()
played = {}
check(A.on_mute_toggle(true, {}) == true, "on_mute_toggle(true) plays mute click")
check(A.is_muted() == true, "is_muted is true")
check(#played == 1 and played[1].path == "zbc\\axon_mute", "mute click played")

check(A.on_rec_start({}) == false, "muted suppresses start")
check(A.on_rec_stop({}) == false, "muted suppresses stop")
check(A.on_event({}) == false, "muted suppresses event")
check(A.on_signal({}) == false, "muted suppresses signal")
check(A.on_gunshot(1, {}) == false, "muted suppresses gunshot")
A.update(125, true, 4, 1, { audio_interval_beep = true, audio_low_batt = true })
check(#played == 1, "muted suppresses interval and low_batt")

check(A.on_mute_toggle(false, {}) == true, "on_mute_toggle(false) plays unmute click")
check(A.is_muted() == false, "is_muted is false")
check(#played == 2 and played[2].path == "zbc\\axon_mute", "unmute click played")

-- Gunshot mic-clip tier scaling & 150ms cooldown
A.reset()
played = {}
local tier_vols = {}
for t = 1, 5 do
	A.update(0.20, true, 80, t, {})
	check(A.on_gunshot(t, { audio_volume = 1.0 }) == true, "gunshot fires for tier " .. t)
	tier_vols[t] = played[#played].vol
end
check(
	tier_vols[1] > tier_vols[2] and tier_vols[2] > tier_vols[3]
	and tier_vols[3] > tier_vols[4] and tier_vols[4] > tier_vols[5],
	string.format("tier mic-clip volume scales down from Body 1 to 5 (%.2f > %.2f > %.2f > %.2f > %.2f)",
		tier_vols[1], tier_vols[2], tier_vols[3], tier_vols[4], tier_vols[5])
)

-- Cooldown check (150ms)
played = {}
A.update(0.20, true, 80, 1, {})
check(A.on_gunshot(1, {}) == true, "first gunshot fires")
A.update(0.05, true, 80, 1, {})
check(A.on_gunshot(1, {}) == false, "gunshot within 50ms blocked by 150ms cooldown")
A.update(0.11, true, 80, 1, {})
check(A.on_gunshot(1, {}) == true, "gunshot after 160ms total fires")
check(#played == 2, "only 2 gunshots played across cooldown test")

-- audio_mic_clip = false
A.update(0.20, true, 80, 1, {})
check(A.on_gunshot(1, { audio_mic_clip = false }) == false, "audio_mic_clip=false suppresses gunshot")

if failures > 0 then
	print(string.format("FAILED: %d check(s) failed", failures))
	os.exit(1)
end
print("OK: all zbc_audio checks passed")
