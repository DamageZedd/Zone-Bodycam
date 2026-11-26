-- Tests for Feature 4: zbc_found_footage.script, zbc_eventlog.script upgrades, and zbc_review.script upgrades.
--
-- Usage (from the repo root): lua tools/tests/zbc_found_footage_test.lua

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end

local function load_mod(path, extra)
	local env = setmetatable(extra or {}, { __index = _G })
	local c = assert(loadfile(path))
	setfenv(c, env)
	local ok, err = pcall(c)
	check(ok, path .. " loads: " .. tostring(err))
	return env
end

---------------------------------------------------------------------------------------------------
-- 1. Eventlog: typed tags, optional metadata, and Body 5 Incident Summary
---------------------------------------------------------------------------------------------------
do
	local ev = load_mod("gamedata/scripts/zbc_eventlog.script")

	ev.add("shots", "Shots fired", true, 100, "14:00", 10, { weapon = "AK-74M", location = "Radar" })
	ev.add("hit", "Officer hit", true, 105, "14:00", 15, { location = "Radar" })
	ev.add("kill", "Subject down", true, 110, "14:00", 20, { weapon = "AK-74M", target = "Bloodsucker", location = "Radar", is_mutant = true })
	ev.add("kill", "Subject down", true, 118, "14:01", 28, { weapon = "AK-74M", target = "Monolith Scout", location = "Radar" })
	ev.add("storm", "Emission", true, 125, "14:01", 35, { location = "Radar" })
	ev.signal_trigger("Weapon draw", "Radar")
	ev.audio_mute(true, "Radar")

	-- Mock fx_enabled + fx_option so signal_trigger/audio_mute log through enabled()
	local ev2 = load_mod("gamedata/scripts/zbc_eventlog.script", {
		time_global = function() return 200000 end,
		level = { get_time_hours = function() return 14 end, get_time_minutes = function() return 5 end, name = function() return "l10_radar" end },
		zbc_bodycam = {
			fx_enabled = function() return true end,
			fx_option = function() return true end,
			rec_seconds = function() return 55 end,
		},
	})
	ev2.add("shots", "SHOT FIRED", true, 100, "14:00", 10, { weapon = "AK-74M", location = "Radar" })
	ev2.add("hit", "HIT TAKEN", true, 105, "14:00", 15, { location = "Radar" })
	ev2.add("kill", "KILL", true, 112, "14:00", 22, { weapon = "AK-74M", target = "Bloodsucker", location = "Radar", is_mutant = true })
	ev2.add("kill", "KILL", true, 118, "14:01", 28, { weapon = "AK-74M", target = "Mercenary", location = "Radar" })
	ev2.add("storm", "EMISSION", true, 124, "14:01", 34, { location = "Radar" })
	local sig = ev2.signal_trigger("Holster draw", "Radar")
	local mute = ev2.audio_mute(true, "Radar")
	local ff_ev = ev2.found_footage({ stalker_name = "Sidor", level_name = "Radar" })

	check(sig and sig.tag == "SIGNAL TRIGGER", "signal_trigger sets SIGNAL TRIGGER tag")
	check(mute and mute.tag == "AUDIO MUTE", "audio_mute sets AUDIO MUTE tag")
	check(ff_ev and ff_ev.tag == "FOUND FOOTAGE", "found_footage sets FOUND FOOTAGE tag")
	check(ev2.history[1].weapon == "AK-74M" and ev2.history[1].location == "Radar", "metadata preserved on event")
	check(ev2.format_entry(ev2.history[3]):find("TGT:BLOODSUCKER", 1, true) ~= nil, "format_entry includes target metadata")

	-- Body 5 summary gating
	check(ev2.build_incident_summary(ev2.history, nil) == nil, "no summary without tier")
	check(ev2.build_incident_summary(ev2.history, 4) == nil, "no summary on Body 4")
	local summary, stats = ev2.build_incident_summary(ev2.history, 5)
	check(type(summary) == "string" and summary:find("DRAFT ONE BRIEF", 1, true) ~= nil, "Body 5 generates Draft One summary")
	check(summary:find("LOC: RADAR", 1, true) ~= nil, "Body 5 summary includes location")
	check(summary:find("SHOTS: 1", 1, true) ~= nil, "Body 5 summary includes shots fired")
	check(summary:find("HITS: 1", 1, true) ~= nil, "Body 5 summary includes hits taken")
	check(summary:find("KILLS: 2 (1 MUTANT)", 1, true) ~= nil, "Body 5 summary includes kills and mutant breakdown")
	check(summary:find("SIGNAL TRIGGERS: 1", 1, true) ~= nil, "Body 5 summary includes signal triggers")
	check(stats and stats.duration_s == 45, "Body 5 summary computes engagement duration (55 - 10 = 45s)")
end

---------------------------------------------------------------------------------------------------
-- 2. Found Footage: faction drops, tier ranges, deterministic reconstruction, cap, save/load
---------------------------------------------------------------------------------------------------
do
	local spawned = {}
	local logged_events = {}
	local ff = load_mod("gamedata/scripts/zbc_found_footage.script", {
		game = {
			get_game_time = function() return { get = function() return 2012, 6, 14, 18, 42, 0, 0 end } end,
			translate_string = function(s) return s end,
		},
		level = { name = function() return "l09_deadcity" end, get_time_hours = function() return 18 end, get_time_minutes = function() return 42 end },
		IsStalker = function(o) return o and o.is_stalker ~= false end,
		IsMonster = function(o) return o and o.is_mutant == true end,
		zbc_item = {},
		alife_create_item = function(sec, npc, opts)
			spawned[#spawned + 1] = { section = sec, npc = npc, cond = opts and opts.cond }
			return true
		end,
		zbc_eventlog = {
			found_footage = function(rec, loc) logged_events[#logged_events + 1] = { rec = rec, loc = loc } end,
		},
	})

	-- Drop chance checks: high-tech (8%) vs low-tech (2%)
	local merc = { id = function() return 101 end, character_name = function() return "Wolfhound" end, character_community = function() return "killer" end }
	local loner = { id = function() return 102 end, character_name = function() return "Vasya" end, character_community = function() return "stalker" end }

	check(ff.drop_chance_for_faction("killer") == 0.08, "Mercs default to 8% drop chance")
	check(ff.drop_chance_for_faction("army") == 0.08, "Military defaults to 8% drop chance")
	check(ff.drop_chance_for_faction("monolith") == 0.08, "Monolith defaults to 8% drop chance")
	check(ff.drop_chance_for_faction("ecolog") == 0.08, "Ecolog defaults to 8% drop chance")
	check(ff.drop_chance_for_faction("isg") == 0.08, "ISG defaults to 8% drop chance")
	check(ff.drop_chance_for_faction("stalker") == 0.02, "Loners default to 2% drop chance")
	check(ff.drop_chance_for_faction("bandit") == 0.02, "Bandits default to 2% drop chance")

	check(ff.on_npc_death(merc, nil, { roll = 0.09 }) == nil, "Merc roll 0.09 misses 8% chance")
	check(ff.on_npc_death(loner, nil, { roll = 0.03 }) == nil, "Loner roll 0.03 misses 2% chance")
	check(ff.on_npc_death(merc, nil, { roll = 0.01, enabled = false }) == nil, "disabled config prevents drop")

	local rec_merc = ff.on_npc_death(merc, { is_mutant = true, section = function() return "bloodsucker_normal" end }, { roll = 0.05 })
	check(rec_merc ~= nil, "Merc roll 0.05 drops found footage")
	check(rec_merc.tier >= 3 and rec_merc.tier <= 5, "Merc tier is in Body 3-5 range")
	check(rec_merc.level_name == "Dead City", "Dead City level translated cleanly")
	check(#rec_merc.events >= 4 and #rec_merc.events <= 6, "Reconstructed log has 4-6 entries")
	check(rec_merc.events[#rec_merc.events].tag == "SIGNAL LOST" and rec_merc.events[#rec_merc.events].offset_s == 0,
		"Reconstructed log ends with SIGNAL LOST at offset 0")
	check(#spawned == 1 and spawned[1].section == rec_merc.item_section and spawned[1].cond >= 0.12 and spawned[1].cond <= 0.45,
		"Scavenged physical bodycam item spawned with partial charge")
	check(#logged_events == 1, "Found footage event forwarded to zbc_eventlog")

	-- Faction tier ranges across multiple seeds
	local ok_stalker, ok_mil, ok_high = true, true, true
	for i = 1, 25 do
		local ts = ff.pick_tier("stalker", i)
		if ts < 1 or ts > 2 then ok_stalker = false end
		local tm = ff.pick_tier("army", i)
		if tm < 2 or tm > 3 then ok_mil = false end
		local te = ff.pick_tier("ecolog", i)
		if te < 2 or te > 3 then ok_mil = false end
		local th = ff.pick_tier("monolith", i)
		if th < 3 or th > 5 then ok_high = false end
	end
	check(ok_stalker, "Stalker tier stays in 1..2")
	check(ok_mil, "Military/Ecolog tier stays in 2..3")
	check(ok_high, "Merc/Monolith/ISG tier stays in 3..5")

	-- Determinism check
	local r_a = ff.build_record({ stalker_name = "Kestrel", faction = "isg", level = "zaton", timestamp = "2012-06-14 21:10", npc_id = 555 })
	local r_b = ff.build_record({ stalker_name = "Kestrel", faction = "isg", level = "zaton", timestamp = "2012-06-14 21:10", npc_id = 555 })
	check(r_a.id == r_b.id and r_a.tier == r_b.tier and #r_a.events == #r_b.events, "build_record is deterministic")
	check(r_a.events[1].text == r_b.events[1].text and r_a.events[#r_a.events].tag == "SIGNAL LOST",
		"reconstructed timeline entries are deterministic and end in SIGNAL LOST")
	local formatted = ff.format_record(r_a)
	check(formatted:find("KESTREL", 1, true) ~= nil and formatted:find("SIGNAL LOST", 1, true) ~= nil,
		"format_record outputs stalker name and SIGNAL LOST")

	-- Cap at 12 records + save/load persistence
	ff.clear()
	for i = 1, 15 do
		local n = { id = function() return 200 + i end, character_name = function() return "Stalker_" .. i end, character_community = function() return "stalker" end }
		ff.on_npc_death(n, nil, { roll = 0.01 })
	end
	check(#ff.get_records() == 12, "Found footage capped at 12 most recent records")
	check(ff.get_record(1).stalker_name == "Stalker_15", "Most recent record is at index 1")
	check(ff.get_record(12).stalker_name == "Stalker_4", "Oldest retained record is Stalker_4")

	local save_data = {}
	ff.save_state(save_data)

	local ff_reloaded = load_mod("gamedata/scripts/zbc_found_footage.script")
	ff_reloaded.load_state(save_data)
	check(#ff_reloaded.get_records() == 12, "load_state restores all 12 records")
	check(ff_reloaded.get_record(1).stalker_name == "Stalker_15", "load_state preserves record order")
	local last_evs = ff_reloaded.get_record(1).events
	check(#last_evs >= 4 and last_evs[#last_evs].tag == "SIGNAL LOST", "load_state preserves reconstructed events")
end

---------------------------------------------------------------------------------------------------
-- 3. Review UI: typed tags, Body 5 Incident Summary panel, and Found Footage switcher
---------------------------------------------------------------------------------------------------
do
	local texts_by_ctrl = {}
	local shown_by_ctrl = {}
	local function mk_ctrl(name)
		local c = { _name = name }
		local tc = {
			SetText = function(_, t) texts_by_ctrl[c] = t end,
			SetTextColor = function() end,
		}
		return setmetatable(c, { __index = {
			SetWndPos = function() end,
			SetWndSize = function() end,
			SetTextureColor = function() end,
			Show = function(_, v) shown_by_ctrl[c] = v end,
			TextControl = function() return tc end,
		} })
	end

	local tier_now = 5
	local ff_records = {}
	local ev_mod = load_mod("gamedata/scripts/zbc_eventlog.script")
	ev_mod.add("shots", "SHOT FIRED", true, 100, "12:00", 10, { weapon = "VSS", location = "Jupiter" })
	ev_mod.add("signal_trigger", "SIGNAL TRIGGER", true, 110, "12:00", 20, { location = "Jupiter" })
	ev_mod.add("kill", "KILL", true, 120, "12:01", 30, { target = "Snork", location = "Jupiter", is_mutant = true })

	local ctrl_idx = 0
	local env = setmetatable({
		time_global = function() return 1000 end,
		Frect = function() return { set = function(s) return s end } end,
		vector2 = function() return { set = function(s) return s end } end,
		GetARGB = function() return 0 end,
		CScriptXmlInit = function()
			return {
				ParseFile = function() end,
				InitStatic = function()
					ctrl_idx = ctrl_idx + 1
					return mk_ctrl("c" .. ctrl_idx)
				end,
			}
		end,
		DIK_keys = {
			DIK_ESCAPE = 1, DIK_TAB = 15, DIK_LBRACKET = 26, DIK_RBRACKET = 27,
			DIK_LEFT = 203, DIK_RIGHT = 205, DIK_UP = 200, DIK_DOWN = 208,
			DIK_A = 30, DIK_D = 32, DIK_W = 17, DIK_S = 31, DIK_HOME = 199, DIK_END = 207,
		},
		ui_events = { WINDOW_KEY_PRESSED = 1 },
		zbc_bodycam = {
			review_key_now = function() return 211 end,
			rec_seconds = function() return 45 end,
			active_tier = function() return tier_now end,
		},
		zbc_eventlog = ev_mod,
		zbc_found_footage = { get_records = function() return ff_records end },
		Register_UI = function() end,
		Unregister_UI = function() end,
		CUIScriptWnd = { OnKeyboard = function() return false end },
		super = function() end,
	}, { __index = _G })
	env.class = function(name)
		return function()
			local cls = {}
			cls.__index = cls
			function cls:SetWndRect() end
			function cls:SetAutoDelete() end
			function cls:ShowDialog() end
			function cls:HideDialog() end
			function cls:Show() end
			function cls:IsShown() return true end
			env[name] = setmetatable(cls, {
				__call = function(t)
					local o = setmetatable({}, t)
					o:__init()
					return o
				end,
			})
		end
	end

	local rc = assert(loadfile("gamedata/scripts/zbc_review.script"))
	setfenv(rc, env)
	rc()

	local inst = env.ZbcReview()
	check(shown_by_ctrl[inst.summary] == true, "Body 5 summary panel is shown when tier == 5")
	check(type(texts_by_ctrl[inst.summary]) == "string" and texts_by_ctrl[inst.summary]:find("DRAFT ONE BRIEF", 1, true) ~= nil,
		"Body 5 summary panel displays Draft One incident brief")
	check(shown_by_ctrl[inst.mode_bar] == false, "Found footage mode bar is hidden when 0 records recovered")

	-- Non-Body 5 hides summary panel
	tier_now = 4
	inst:Refresh()
	check(shown_by_ctrl[inst.summary] == false, "Body 4 hides Body 5 incident summary panel")

	-- Pressing Tab with 0 found footage stays in live mode
	inst:OnKeyboard(15, 1)
	check(inst.mode == "live", "Tab does not enter found_footage mode when no records exist")

	-- Add two Found Footage records and verify switching + cycling
	local ff_helper = load_mod("gamedata/scripts/zbc_found_footage.script")
	ff_records[1] = ff_helper.build_record({ stalker_name = "Dima", faction = "killer", level = "zaton", timestamp = "2012-06-14 19:00", npc_id = 1 })
	ff_records[2] = ff_helper.build_record({ stalker_name = "Borya", faction = "stalker", level = "l01_escape", timestamp = "2012-06-14 18:00", npc_id = 2 })

	inst:Refresh()
	check(shown_by_ctrl[inst.mode_bar] == true, "Found footage mode bar appears once records exist")
	inst:OnKeyboard(15, 1) -- Tab -> found_footage
	check(inst.mode == "found_footage" and inst.ff_idx == 1, "Tab switches review UI to found_footage mode")
	check(texts_by_ctrl[inst.summary]:find("DIMA", 1, true) ~= nil, "Found footage header displays selected stalker Dima")
	local last_row_text = texts_by_ctrl[inst.rows[#ff_records[1].events]]
	check(type(last_row_text) == "string" and last_row_text:find("SIGNAL LOST", 1, true) ~= nil,
		"Found footage timeline displays SIGNAL LOST as final event")

	inst:OnKeyboard(27, 1) -- ']' -> next tape
	check(inst.ff_idx == 2 and texts_by_ctrl[inst.summary]:find("BORYA", 1, true) ~= nil,
		"']' cycles to second recovered tape (Borya)")
	inst:OnKeyboard(15, 1) -- Tab -> back to live
	check(inst.mode == "live", "Tab toggles back to live feed")
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_found_footage_test: all checks passed")
