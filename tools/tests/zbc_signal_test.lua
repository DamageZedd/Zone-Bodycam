-- Tests gamedata/scripts/zbc_signal.script: standby BUFFER vs REC, battery drain multiplier,
-- Axon Signal auto-trigger (Body 2+ gating), signal_flash 3s expiry, signal_hold_sec auto-return,
-- manual standby/mute toggles, OSD tag priority, callbacks, and save/load persistence.
--
-- Usage (from the repo root): lua tools/tests/zbc_signal_test.lua

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end
local function near(a, b, eps) return type(a) == "number" and math.abs(a - b) <= (eps or 1e-9) end

local stub
stub = setmetatable({}, {
	__index = function() return stub end,
	__call = function() return stub end,
})
local function load_script(path, extra)
	local chunk = assert(loadfile(path))
	local env = setmetatable(extra or {}, { __index = function(_, k)
		local v = _G[k]
		if v ~= nil then return v end
		return stub
	end })
	setfenv(chunk, env)
	local ok, err = pcall(chunk)
	check(ok, path .. " loads: " .. tostring(err))
	return env
end

local T = load_script("gamedata/scripts/zbc_tiers.script")
local function new_signal()
	return load_script("gamedata/scripts/zbc_signal.script", { zbc_tiers = T })
end

-- 1. Standby OFF (default backwards-compat): always rec, 1.0x drain, no signal wake
do
	local S = new_signal()
	local cfg = { standby_mode = false, signal_hold_sec = 60 }
	local events = {}
	S.set_callbacks({
		on_rec_start = function(src) events[#events + 1] = "start:" .. tostring(src) end,
		on_rec_stop  = function(src) events[#events + 1] = "stop:" .. tostring(src) end,
		on_signal    = function(r) events[#events + 1] = "sig:" .. tostring(r) end,
	})

	check(S.get_mode() == "rec", "initial mode defaults to rec")
	check(S.is_recording() and not S.is_buffering(), "is_recording true, is_buffering false")
	check(near(S.drain_multiplier(), 1.0), "drain_multiplier is 1.0 in rec")
	check(S.get_osd_tag() == nil, "osd tag nil when rec unmuted")

	S.update(5.0, 4, cfg)
	check(S.get_mode() == "rec" and near(S.drain_multiplier(), 1.0), "stays rec with standby_mode false")

	local triggered = S.trigger_signal("gunshot", 4, cfg)
	check(triggered == false, "trigger_signal does not trigger when standby_mode is off")
	check(not S.is_signal_active() and S.get_osd_tag() == nil, "no signal flash when standby_mode is off")

	local mode_after, changed = S.toggle_standby(cfg)
	check(mode_after == "rec" and changed == false, "toggle_standby is a no-op when standby_mode is off")
	check(#events == 0, "no rec/signal callbacks fired while standby_mode is off")
end

-- 2. Standby ON: starts in buffer (0.25x drain, BUF tag), stays in buffer without triggers
do
	local S = new_signal()
	local cfg = { standby_mode = true, signal_hold_sec = 60 }
	S.update(0.5, 4, cfg)
	check(S.get_mode() == "buffer", "standby_mode ON starts in buffer")
	check(S.is_buffering() and not S.is_recording(), "is_buffering true, is_recording false")
	check(near(S.drain_multiplier(), 0.25), "drain_multiplier is 0.25 in buffer")
	check(S.get_osd_tag() == "BUF", "osd tag is BUF in buffer")

	S.update(120, 4, cfg)
	check(S.get_mode() == "buffer", "buffer does not expire on its own")
end

-- 3. Tier gating: Body 1 (pre-Signal 2013) does NOT wake; Body 2..5 and nil tier DO wake
do
	local S = new_signal()
	local cfg = { standby_mode = true, signal_hold_sec = 60 }
	local sig_count = 0
	S.set_callbacks({ on_signal = function() sig_count = sig_count + 1 end })

	check(S.supports_signal(1) == false, "Body 1 does not support Axon Signal")
	for _, t in ipairs({ 2, 3, 4, 5 }) do
		check(S.supports_signal(t) == true, "Body " .. t .. " supports Axon Signal")
	end
	check(S.supports_signal(nil) == true, "nil tier (no item / tier limits off) supports Axon Signal like Body 4")

	S.update(0.1, 1, cfg)
	check(S.on_weapon_draw(1, cfg) == false, "Body 1 ignores weapon_draw signal")
	check(S.on_gunshot(1, cfg) == false, "Body 1 ignores gunshot signal")
	check(S.on_hit(1, cfg) == false, "Body 1 ignores hit signal")
	check(S.on_light_toggle(1, cfg) == false, "Body 1 ignores light_toggle signal")
	check(S.on_combat_sprint(1, cfg) == false, "Body 1 ignores combat_sprint signal")
	check(S.get_mode() == "buffer" and not S.is_signal_active() and sig_count == 0,
		"Body 1 stays in buffer with no signal flash or callback")

	-- Explicit axon_signal = false also suppresses signal on Body 4
	local cfg_no_sig = { standby_mode = true, signal_hold_sec = 60, axon_signal = false }
	check(S.on_gunshot(4, cfg_no_sig) == false and S.get_mode() == "buffer",
		"axon_signal=false suppresses Signal even on Body 4")

	-- Each trigger type wakes Body 2+ / nil tier
	local triggers = {
		{ fn = "on_weapon_draw",   tier = 2 },
		{ fn = "on_gunshot",       tier = 3 },
		{ fn = "on_hit",           tier = 4 },
		{ fn = "on_light_toggle",  tier = 5 },
		{ fn = "on_combat_sprint", tier = nil },
	}
	for _, tc in ipairs(triggers) do
		local Si = new_signal()
		Si.update(0.1, tc.tier, cfg)
		local ok = Si[tc.fn](tc.tier, cfg)
		check(ok == true and Si.get_mode() == "rec" and Si.is_signal_active(),
			tc.fn .. " wakes buffer -> rec on tier " .. tostring(tc.tier))
	end
end

-- 4. signal_flash 3.0s expiry and signal_hold_sec (60s) reset & auto-return to buffer
do
	local S = new_signal()
	local cfg = { standby_mode = true, signal_hold_sec = 60 }
	local log = {}
	S.set_callbacks({
		on_rec_start = function(src, reason) log[#log + 1] = "start:" .. src .. ":" .. tostring(reason) end,
		on_rec_stop  = function(src) log[#log + 1] = "stop:" .. src end,
		on_signal    = function(reason) log[#log + 1] = "sig:" .. tostring(reason) end,
	})

	S.update(0.1, 2, cfg)
	check(S.on_weapon_draw(2, cfg) == true, "weapon_draw wakes Body 2")
	check(S.get_mode() == "rec" and near(S.drain_multiplier(), 1.0), "mode rec, 1.0x drain after signal")
	check(S.is_signal_active() and S.get_osd_tag() == "SIGNAL", "SIGNAL OSD tag active immediately")
	check(#log == 2 and log[1] == "start:signal:weapon_draw" and log[2] == "sig:weapon_draw",
		"on_rec_start and on_signal fired once on wake")

	-- Still flashing at 2.9s
	S.update(2.9, 2, cfg)
	check(S.is_signal_active() and S.get_osd_tag() == "SIGNAL", "SIGNAL tag stays up at 2.9s")

	-- Expires after 3.0s
	S.update(0.2, 2, cfg)
	check(not S.is_signal_active() and S.get_osd_tag() == nil, "SIGNAL tag clears after 3.0s")
	check(S.get_mode() == "rec", "still recording after flash expires")

	-- Advance to 50s total: still recording; new gunshot resets hold to full 60s without duplicate start
	S.update(46.9, 2, cfg)
	check(S.get_mode() == "rec" and S.get_hold_remaining() > 9.9, "still rec at 50s")
	check(S.on_gunshot(2, cfg) == true, "gunshot extends hold timer")
	check(#log == 2, "extending hold timer does not re-fire on_rec_start or on_signal")
	check(near(S.get_hold_remaining(), 60.0), "hold timer reset to 60s")

	-- Advance 50s (past old 60s window, 10s left on new window) -> still recording
	S.update(50.0, 2, cfg)
	check(S.get_mode() == "rec", "still recording 50s after hold reset")

	-- Advance remaining 10.5s -> returns to buffer and fires on_rec_stop
	S.update(10.5, 2, cfg)
	check(S.get_mode() == "buffer" and near(S.drain_multiplier(), 0.25), "auto-returned to buffer after hold expiry")
	check(S.get_osd_tag() == "BUF", "OSD tag returns to BUF")
	check(#log == 3 and log[3] == "stop:hold_expired", "on_rec_stop fired on hold expiry")
end

-- 5. Manual standby toggle: manual rec does not auto-expire; toggling stops signal-rec immediately
do
	local S = new_signal()
	local cfg = { standby_mode = true, signal_hold_sec = 30 }
	local stops, starts = 0, 0
	S.set_callbacks({
		on_rec_start = function() starts = starts + 1 end,
		on_rec_stop  = function() stops = stops + 1 end,
	})

	S.update(0.1, 4, cfg)
	local m, changed = S.toggle_standby(cfg)
	check(m == "rec" and changed == true and starts == 1, "manual toggle switches buffer -> rec")
	check(S.get_osd_tag() == nil, "no BUF or SIGNAL tag on manual rec")

	-- Stays recording across long update and even if a gunshot happens
	S.update(500, 4, cfg)
	check(S.get_mode() == "rec", "manual rec never auto-expires")
	check(S.on_gunshot(4, cfg) == false, "signal does not override manual rec into auto-stop")
	S.update(500, 4, cfg)
	check(S.get_mode() == "rec", "still manual rec after signal event")

	m, changed = S.toggle_standby(cfg)
	check(m == "buffer" and changed == true and stops == 1, "manual toggle switches rec -> buffer")

	-- Manual toggle during active signal-triggered rec returns immediately to buffer
	S.on_hit(4, cfg)
	check(S.get_mode() == "rec" and S.is_signal_active(), "hit triggered signal rec")
	m = S.toggle_standby(cfg)
	check(m == "buffer" and not S.is_signal_active() and stops == 2,
		"manual toggle during signal rec returns to buffer and clears flash")
end

-- 6. Mute toggle, OSD priority (SIGNAL > MUTE > BUF), and callback
do
	local S = new_signal()
	local cfg = { standby_mode = true, signal_hold_sec = 10 }
	local mute_events = {}
	S.set_callbacks({ on_mute = function(v) mute_events[#mute_events + 1] = v end })

	S.update(0.1, 4, cfg)
	check(not S.is_muted(), "starts unmuted")
	check(S.toggle_mute(cfg) == true and S.is_muted(), "toggle_mute enables mute")
	check(S.get_osd_tag() == "MUTE", "MUTE takes priority over BUF when muted")

	-- Signal flashes SIGNAL for 3s, then falls back to MUTE while recording
	S.on_gunshot(4, cfg)
	check(S.get_osd_tag() == "SIGNAL", "SIGNAL takes priority over MUTE while flashing")
	S.update(3.5, 4, cfg)
	check(S.get_osd_tag() == "MUTE", "falls back to MUTE after signal_flash expires")

	check(S.toggle_mute(cfg) == false and not S.is_muted(), "toggle_mute disables mute")
	check(S.get_osd_tag() == nil, "OSD tag nil when recording unmuted")
	check(#mute_events == 2 and mute_events[1] == true and mute_events[2] == false, "on_mute fired with bool")
end

-- 7. Live MCM standby_mode switching
do
	local S = new_signal()
	local starts, stops = 0, 0
	S.set_callbacks({
		on_rec_start = function() starts = starts + 1 end,
		on_rec_stop  = function() stops = stops + 1 end,
	})
	S.update(0.1, 4, { standby_mode = true })
	check(S.get_mode() == "buffer" and starts == 0 and stops == 0, "initial standby sync fires no transitions")
	S.update(0.1, 4, { standby_mode = false })
	check(S.get_mode() == "rec" and starts == 1, "switching standby_mode off enters rec and fires on_rec_start")
	S.update(0.1, 4, { standby_mode = true })
	check(S.get_mode() == "buffer" and stops == 1, "switching standby_mode on enters buffer and fires on_rec_stop")
end

-- 8. Save / Load persistence
do
	local S1 = new_signal()
	local cfg = { standby_mode = true, signal_hold_sec = 60 }
	S1.update(0.1, 4, cfg)
	S1.toggle_mute(cfg)
	S1.on_gunshot(4, cfg)
	S1.update(1.5, 4, cfg) -- 1.5s signal_flash left, 58.5s hold_timer left

	local m_data = {}
	S1.save_state(m_data)

	local S2 = new_signal()
	S2.load_state(m_data)
	check(S2.get_mode() == "rec" and S2.is_muted(), "load_state restores rec mode and muted flag")
	check(near(S2.get_signal_flash_remaining(), 1.5, 1e-6), "load_state restores signal_flash")
	check(near(S2.get_hold_remaining(), 58.5, 1e-6), "load_state restores hold_timer")
	check(S2.get_osd_tag() == "SIGNAL", "OSD shows SIGNAL after load")

	-- Updating with standby_mode = true keeps restored rec state and counts down hold_timer
	S2.update(2.0, 4, cfg)
	check(S2.get_mode() == "rec" and S2.get_osd_tag() == "MUTE", "flash expired, still rec + muted")
	S2.update(57.0, 4, cfg)
	check(S2.get_mode() == "buffer", "restored hold_timer expires back to buffer")

	-- Manual rec persistence
	S1.reset(cfg)
	S1.toggle_standby(cfg)
	local m_manual = {}
	S1.save_state(m_manual)
	S2.load_state(m_manual)
	S2.update(500, 4, cfg)
	check(S2.get_mode() == "rec" and S2.is_manual_rec(), "restored manual rec never auto-expires")

	-- Empty load resets cleanly
	S2.load_state({})
	check(S2.get_mode() == "rec" and not S2.is_muted() and not S2.is_manual_rec(),
		"empty load_state resets to clean default")
end

if failures == 0 then
	print("ALL PASSED (zbc_signal_test)")
else
	print(string.format("%d FAILURE(S) (zbc_signal_test)", failures))
	os.exit(1)
end
