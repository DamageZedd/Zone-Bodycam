-- Tests for Polish #2 (Safe Hub DOCK/SYNC) & Feature #2 (Sellable Found Footage Intel):
-- zbc_intel.script, zbc_found_footage.script redeemed tracking, and zbc_review.script intel UI.
--
-- Usage (from the repo root): lua tools/tests/zbc_intel_test.lua

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
-- 1. Safe hub detection (GetEvent, sr_no_weapon, trader proximity, level_name)
---------------------------------------------------------------------------------------------------
do
	local safe_ev = false
	local no_wep = { inside = false }
	local intel = load_mod("gamedata/scripts/zbc_intel.script", {
		GetEvent = function(name)
			if name == "current_safe_zone" then return safe_ev end
			return nil
		end,
		sr_no_weapon = no_wep,
		game_object = { enemy = 2 },
	})

	check(intel.DEFAULTS.hub_sync == true and intel.DEFAULTS.intel_sell_enabled == true,
		"DEFAULTS sets hub_sync=true and intel_sell_enabled=true")
	check(intel.is_at_safe_hub(nil, "l01_escape") == false, "field level returns false when not in safe zone")
	check(intel.is_at_safe_hub(nil, "l05_bar") == true, "Rostok (l05_bar) safe-hub level check returns true")

	safe_ev = "1"
	check(intel.is_at_safe_hub(nil, "l01_escape") == true, "GetEvent(current_safe_zone) detects safe hub")
	safe_ev = false

	no_wep.inside = true
	check(intel.is_at_safe_hub(nil, "l01_escape") == true, "sr_no_weapon.inside detects safe hub")
	no_wep.inside = false

	local actor = { pos = { x = 100, y = 0, z = 100 } }
	local friendly_trader = {
		pos = { x = 110, y = 0, z = 100 },
		section = "esc_m_trader",
		alive = true,
	}
	local far_trader = {
		pos = { x = 300, y = 0, z = 100 },
		section = "esc_m_trader",
		alive = true,
	}
	local hostile_trader = {
		pos = { x = 105, y = 0, z = 100 },
		section = "esc_m_trader",
		alive = true,
		hostile = true,
	}
	check(intel.is_at_safe_hub(actor, "l01_escape", { traders = { friendly_trader } }) == true,
		"near friendly hub trader detects safe hub")
	check(intel.is_at_safe_hub(actor, "l01_escape", { traders = { far_trader } }) == false,
		"distant trader does not trigger safe hub")
	check(intel.is_at_safe_hub(actor, "l01_escape", { traders = { hostile_trader } }) == false,
		"hostile trader does not trigger safe hub")
end

---------------------------------------------------------------------------------------------------
-- 2. Hub SYNC state machine: Body 3+ / tiers off gating, 4.0s duration, 1x/visit, 120s cooldown
---------------------------------------------------------------------------------------------------
do
	local intel = load_mod("gamedata/scripts/zbc_intel.script")
	local sync_calls = 0
	intel.set_callbacks({
		on_sync = function() sync_calls = sync_calls + 1 end,
	})

	-- Body 1 & Body 2 must NOT trigger hub sync
	intel.update_hub_sync(0.1, true, 1)
	check(intel.is_syncing() == false and sync_calls == 0, "Body 1 does not trigger hub SYNC")
	intel.update_hub_sync(0.1, false, 1)

	intel.update_hub_sync(0.1, true, 2)
	check(intel.is_syncing() == false and sync_calls == 0, "Body 2 does not trigger hub SYNC")
	intel.update_hub_sync(0.1, false, 2)

	-- Body 3 triggers SYNC for 4.0s once per hub visit
	intel.update_hub_sync(0.1, true, 3)
	check(intel.is_syncing() == true and sync_calls == 1, "Body 3 triggers SYNC on hub entry")
	intel.update_hub_sync(2.0, true, 3)
	check(intel.is_syncing() == true and sync_calls == 1, "SYNC remains active at 2.0s")
	intel.update_hub_sync(2.1, true, 3)
	check(intel.is_syncing() == false and sync_calls == 1, "SYNC ends after 4.0s and does not re-fire in same visit")

	-- Staying in hub does not re-trigger
	intel.update_hub_sync(30.0, true, 5)
	check(intel.is_syncing() == false and sync_calls == 1, "staying in hub does not re-trigger SYNC")

	-- Leaving hub starts 120s cooldown
	intel.update_hub_sync(0.1, false, 3)
	check(intel.get_cooldown_remaining() == 120.0, "leaving hub starts 120s cooldown")
	intel.update_hub_sync(60.0, false, 3)
	check(intel.get_cooldown_remaining() == 60.0, "60s outside hub leaves 60s cooldown")

	-- Re-entering during cooldown must NOT sync
	intel.update_hub_sync(0.1, true, 4)
	check(intel.is_syncing() == false and sync_calls == 1, "re-entering hub during cooldown does not re-sync")

	-- Leave again and finish remaining 60s cooldown
	intel.update_hub_sync(60.0, false, 4)
	check(intel.get_cooldown_remaining() == 0, "cooldown reaches 0 after 120s outside hub")

	-- Tiers off (tier == nil) still allows sync
	intel.update_hub_sync(0.1, true, nil)
	check(intel.is_syncing() == true and sync_calls == 2, "tiers off (nil) allows SYNC after cooldown expires")

	-- Disabled hub_sync config prevents sync
	intel.reset()
	sync_calls = 0
	intel.update_hub_sync(0.1, true, 5, { hub_sync = false })
	check(intel.is_syncing() == false and sync_calls == 0, "hub_sync=false disables hub SYNC")
end

---------------------------------------------------------------------------------------------------
-- 3. Payout math across tiers & factions
---------------------------------------------------------------------------------------------------
do
	local intel = load_mod("gamedata/scripts/zbc_intel.script")

	local cases = {
		{ tier = 1, faction = "stalker",  exp_ru = 1200 },
		{ tier = 1, faction = "bandit",   exp_ru = 1200 },
		{ tier = 2, faction = "army",     exp_ru = 2500 },
		{ tier = 3, faction = "ecolog",   exp_ru = 4000 },
		{ tier = 4, faction = "killer",   exp_ru = 6000 },
		{ tier = 4, faction = "stalker",  exp_ru = 4800 },
		{ tier = 5, faction = "monolith", exp_ru = 10500 },
		{ tier = 5, faction = "isg",      exp_ru = 10500 },
		{ tier = 5, faction = "stalker",  exp_ru = 7000 },
	}
	for _, c in ipairs(cases) do
		local ru, gw = intel.estimate_payout({ tier = c.tier, faction = c.faction })
		check(ru == c.exp_ru, string.format("tier %d %s payout == %d (got %d)", c.tier, c.faction, c.exp_ru, ru))
		check(gw >= 15 and gw <= 50, string.format("tier %d %s goodwill in 15..50 (got %d)", c.tier, c.faction, gw))
	end
end

---------------------------------------------------------------------------------------------------
-- 4. Found footage redeemed field, sell_record, double-sell prevention, sell_all_records, persistence
---------------------------------------------------------------------------------------------------
do
	local money_given = 0
	local goodwill_given = 0
	local logged = {}
	local sell_events = {}

	local ff = load_mod("gamedata/scripts/zbc_found_footage.script")
	local r1 = ff.build_record({ stalker_name = "Dima", faction = "killer", tier = 4, level = "zaton", timestamp = "2012-06-14 18:00", npc_id = 1 })
	local r2 = ff.build_record({ stalker_name = "Vano", faction = "monolith", tier = 5, level = "l10_radar", timestamp = "2012-06-14 19:00", npc_id = 2 })
	local r3 = ff.build_record({ stalker_name = "Petya", faction = "stalker", tier = 1, level = "l01_escape", timestamp = "2012-06-14 17:00", npc_id = 3 })
	check(r1.redeemed == false and r2.redeemed == false and r3.redeemed == false, "newly built records default to redeemed=false")
	ff.add_record(r3)
	ff.add_record(r2)
	ff.add_record(r1)
	check(ff.get_unredeemed_count() == 3, "get_unredeemed_count returns 3")

	local intel = load_mod("gamedata/scripts/zbc_intel.script", {
		zbc_found_footage = ff,
		zbc_eventlog = {
			add = function(kind, text) logged[#logged + 1] = { kind = kind, text = text } end,
		},
		db = {
			actor = {
				id = function() return 0 end,
				character_community = function() return "actor_stalker" end,
				give_money = function(_, amt) money_given = money_given + amt end,
			},
		},
		relation_registry = {
			change_community_goodwill = function(_, _, delta) goodwill_given = goodwill_given + delta end,
		},
	})
	intel.set_callbacks({
		on_sell = function(ev) sell_events[#sell_events + 1] = ev end,
	})

	-- Field guard blocks selling when not at hub
	local ok, ru, gw, msg = intel.sell_record(1, false)
	check(not ok and ru == 0 and gw == 0 and type(msg) == "string", "sell_record rejects sale in the field")
	check(ff.get_record(1).redeemed == false and money_given == 0, "failed field sale leaves record unredeemed and money unchanged")

	-- Override intel_sell_anywhere allows field sale
	ok, ru, gw, msg = intel.sell_record(3, false, { intel_sell_anywhere = true })
	check(ok and ru == 1200 and gw == 15, "intel_sell_anywhere=true permits field sale (tier 1 stalker = 1200 RU)")
	check(ff.get_record(3).redeemed == true and ff.get_unredeemed_count() == 2, "record 3 marked redeemed; 2 remain")

	-- Double-sell prevention
	local ok2, ru2, gw2 = intel.sell_record(3, true)
	check(not ok2 and ru2 == 0 and gw2 == 0, "sell_record prevents double-selling already redeemed tape")

	-- Batch sell remaining records at hub
	local bok, bru, bgw, _, bcount = intel.sell_all_records(true)
	check(bok and bcount == 2, "sell_all_records sells the 2 remaining unredeemed tapes")
	check(bru == 6000 + 10500, "sell_all_records totals 6000 (Body 4 Merc) + 10500 (Body 5 Monolith) = 16500 RU")
	check(ff.get_unredeemed_count() == 0, "all records marked redeemed after batch sale")
	check(money_given == 1200 + 16500, "db.actor:give_money awarded exact total RU")
	check(goodwill_given == 15 + bgw and bgw > 0, "goodwill awarded safely via relation_registry")
	check(#logged == 2 and #sell_events == 2, "eventlog and on_sell callback fired on sales")

	-- Batch sell when nothing left fails gracefully
	local bok2, bru2, _, _, bcount2 = intel.sell_all_records(true)
	check(not bok2 and bru2 == 0 and bcount2 == 0, "sell_all_records returns false when no unredeemed tapes remain")

	-- Save/load persistence for both zbc_found_footage (redeemed flag) and zbc_intel
	intel.update_hub_sync(0.1, true, 4)
	intel.update_hub_sync(0.1, false, 4)
	local m_data = {}
	ff.save_state(m_data)
	intel.save_state(m_data)

	local ff2 = load_mod("gamedata/scripts/zbc_found_footage.script")
	local intel2 = load_mod("gamedata/scripts/zbc_intel.script", { zbc_found_footage = ff2 })
	ff2.load_state(m_data)
	intel2.load_state(m_data)
	check(ff2.get_record(1).redeemed == true and ff2.get_unredeemed_count() == 0,
		"zbc_found_footage save/load preserves redeemed=true")
	check(intel2.get_cooldown_remaining() == 120.0 and intel2.get_stats().total_sold == 3,
		"zbc_intel save/load preserves cooldown and lifetime sale stats")
end

---------------------------------------------------------------------------------------------------
-- 5. Review UI integration: intel badge, field vs hub hint, and S/Enter hotkey sale
---------------------------------------------------------------------------------------------------
do
	local texts_by_ctrl = {}
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
			Show = function() end,
			TextControl = function() return tc end,
		} })
	end

	local at_hub_now = false
	local ff = load_mod("gamedata/scripts/zbc_found_footage.script")
	ff.add_record(ff.build_record({ stalker_name = "Sokol", faction = "stalker", tier = 4, level = "zaton", timestamp = "2012-06-14 20:00", npc_id = 77 }))

	local intel = load_mod("gamedata/scripts/zbc_intel.script", {
		zbc_found_footage = ff,
		GetEvent = function(n) return n == "current_safe_zone" and at_hub_now or false end,
		db = { actor = { give_money = function() end } },
	})

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
			DIK_ESCAPE = 1, DIK_TAB = 15, DIK_RETURN = 28, DIK_LBRACKET = 26, DIK_RBRACKET = 27,
			DIK_LEFT = 203, DIK_RIGHT = 205, DIK_UP = 200, DIK_DOWN = 208,
			DIK_A = 30, DIK_D = 32, DIK_W = 17, DIK_S = 31, DIK_HOME = 199, DIK_END = 207,
		},
		ui_events = { WINDOW_KEY_PRESSED = 1 },
		zbc_bodycam = { review_key_now = function() return 211 end, rec_seconds = function() return 30 end, active_tier = function() return 4 end },
		zbc_eventlog = { HISTORY_MAX = 8, history = {} },
		zbc_found_footage = ff,
		zbc_intel = intel,
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
	inst:OnKeyboard(15, 1) -- Tab -> found_footage
	check(inst.mode == "found_footage", "review enters found_footage mode")
	check(texts_by_ctrl[inst.summary]:find("[INTEL: 4,800 RU]", 1, true) ~= nil,
		"Found Footage summary displays [INTEL: 4,800 RU]")
	check(texts_by_ctrl[inst.hint]:find("[S] Upload intel at safe hub", 1, true) ~= nil,
		"Field hint displays '[S] Upload intel at safe hub'")

	-- Attempt sell in field with S (31) -> remains unredeemed
	inst:OnKeyboard(31, 1)
	check(ff.get_record(1).redeemed == false, "Pressing S in field does not sell record")

	-- Enter safe hub -> hint updates to +4,800 RU; pressing Enter (28) or S (31) sells it
	at_hub_now = true
	inst:Refresh()
	check(texts_by_ctrl[inst.hint]:find("[S] Upload intel (+4,800 RU)", 1, true) ~= nil,
		"Hub hint displays '[S] Upload intel (+4,800 RU)'")

	inst:OnKeyboard(28, 1) -- Enter
	check(ff.get_record(1).redeemed == true, "Pressing Enter at safe hub uploads/sells intel")
	check(texts_by_ctrl[inst.summary]:find("[UPLOADED]", 1, true) ~= nil,
		"After upload, Found Footage summary shows [UPLOADED]")
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_intel_test: all checks passed")
