-- Tests Feature #4 (Axon Flex POV helmet/collar mount for Body 4 & 5) and
-- Polish #1 (Persistent lens crack across battery swaps + toolkit repair helper).
--
-- Usage (from the repo root): lua tools/tests/zbc_flex_pov_test.lua

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

local function parse_ltx(path)
	local txt = read(path)
	local secs = {}
	local cur = nil
	for raw in txt:gmatch("[^\r\n]+") do
		local line = raw:gsub(";.*$", ""):match("^%s*(.-)%s*$")
		if line ~= "" then
			local name, parent = line:match("^%[([^%]]+)%]%s*:%s*([%w_]+)$")
			if not name then name = line:match("^%[([^%]]+)%]$") end
			if name then
				cur = { _parent = parent }
				if parent and secs[parent] then
					for k, v in pairs(secs[parent]) do cur[k] = v end
				end
				secs[name] = cur
			elseif cur then
				local k, v = line:match("^([%w_%$]+)%s*=%s*(.-)%s*$")
				if k then cur[k] = v end
			end
		end
	end
	return secs
end

-- 1. Item config [zbc_flex_pov]
do
	local ltx = parse_ltx("optional/bodycam_item/gamedata/configs/items/items/items_zbc_flex_pov.ltx")
	local s = ltx.zbc_flex_pov
	check(s ~= nil, "[zbc_flex_pov] section exists")
	if s then
		check(s._parent == "identity_immunities", "[zbc_flex_pov] inherits identity_immunities")
		check(s.inv_weight == "0.08", "inv_weight is 0.08")
		check(s.cost == "14000", "cost is 14000")
		check(s.inv_grid_width == "1" and s.inv_grid_height == "1", "1x1 inventory grid")
		check(s.icons_texture == "ui\\ui_icon_zbc_bodycam", "uses ui_icon_zbc_bodycam atlas")
		check(s.inv_grid_x == "0" and s.inv_grid_y == "0", "valid 1x1 icon coordinates")
		check(s.inv_name == "st_zbc_flex_pov_name" and s.description == "st_zbc_flex_pov_descr", "EN/RU string IDs wired")
	end
end

-- 2. Craft recipe x_zbc_flex_pov
do
	local craft = read("optional/bodycam_item/gamedata/configs/items/settings/mod_craft_zbc_bodycam.ltx"):gsub("\r\n", "\n")
	check(craft:find("!%[1%]") ~= nil, "craft patches workshop Devices tab ![1]")
	local val = craft:match("\nx_zbc_flex_pov%s*=%s*([^\n]+)")
	check(val ~= nil, "x_zbc_flex_pov recipe exists")
	if val then
		local PARTS = { prt_i_copper = true, prt_i_capacitors = true, prt_i_transistors = true, prt_i_plastic = true }
		local f = {}
		for v in val:gmatch("[^,]+") do f[#f + 1] = v:match("^%s*(.-)%s*$") end
		check(tonumber(f[1]) == 2, "x_zbc_flex_pov uses advanced toolkit (2)")
		check(f[2] == "recipe_advanced_2", "x_zbc_flex_pov uses recipe_advanced_2")
		check((#f - 2) % 2 == 0 and (#f - 2) / 2 >= 1 and (#f - 2) / 2 <= 4, "1..4 part pairs")
		for j = 3, #f, 2 do
			check(PARTS[f[j]] == true, "valid GAMMA part: " .. tostring(f[j]))
			check(tonumber(f[j + 1]) and tonumber(f[j + 1]) >= 1, "positive count for " .. tostring(f[j]))
		end
	end
end

-- 3. EN and RU (windows-1251) localization strings
do
	local eng = read("optional/bodycam_item/gamedata/configs/text/eng/ui_st_zbc_bodycam_item.xml")
	local rus = read("optional/bodycam_item/gamedata/configs/text/rus/ui_st_zbc_bodycam_item.xml")
	for _, id in ipairs({ "st_zbc_flex_pov_name", "st_zbc_flex_pov_descr" }) do
		check(eng:find('id="' .. id .. '"', 1, true) ~= nil, "EN has " .. id)
		check(rus:find('id="' .. id .. '"', 1, true) ~= nil, "RU has " .. id)
	end
	check(eng:find("AXON FLEX POV", 1, true) ~= nil, "EN mentions AXON FLEX POV")
	check(eng:find("Axon Body 4", 1, true) ~= nil and eng:find("Axon Body 5", 1, true) ~= nil, "EN mentions Body 4 and Body 5")
	check(rus:find('encoding="windows-1251"', 1, true) ~= nil, "RU declares windows-1251")
	-- Check RU has cp1251 Cyrillic bytes (0xC0..0xFF) and is NOT UTF-8 (which uses 0xD0/0xD1 two-byte sequences)
	local has_cp1251_upper, has_utf8_cyr = false, false
	for i = 1, #rus do
		local b = rus:byte(i)
		if b >= 0xC0 and b <= 0xFF then has_cp1251_upper = true end
		if i < #rus and (b == 0xD0 or b == 0xD1) then
			local b2 = rus:byte(i + 1)
			if b2 >= 0x80 and b2 <= 0xBF then has_utf8_cyr = true end
		end
	end
	check(has_cp1251_upper and not has_utf8_cyr, "RU XML is encoded in cp1251, not UTF-8")
end

-- 4. Runtime: has_flex_pov(), Body 4-5 gating, AXON FLEX POV label, and Polish #1 lens crack persistence
do
	local function make_env()
		local cbs = {}
		local now_ms = 0
		local items = {}
		local by_id = {}
		local repair_calls = 0
		local anim_calls = {}

		local function add_item(id, sec, cond)
			local o = { _cond = cond or 1.0, _parent = 0 }
			function o:id() return id end
			function o:section() return sec end
			function o:condition() return self._cond end
			function o:set_condition(c) self._cond = c end
			function o:parent() return self._parent and { id = function() return self._parent end } or nil end
			items[#items + 1] = o
			by_id[id] = o
			return o
		end

		local env = setmetatable({
			AC_ID = 0,
			db = {
				actor = {
					iterate_inventory = function(_, fn, ctx)
						for i = 1, #items do
							if items[i]._parent == 0 then fn(ctx, items[i]) end
						end
					end,
				},
			},
			time_global = function() return now_ms end,
			level = { object_by_id = function(id) return by_id[id] end },
			ui_mcm = { get = function(k)
				if k == "zone_bodycam/enabled" then return true end
				if k == "zone_bodycam_item/battery_game_hours" then return 14 end
				return nil
			end },
			item_device = { get_power_critical = function() return 0.05 end },
			game_difficulties = { get_eco_factor = function() return 1 end },
			actor_menu = { set_msg = function() end },
			game = { translate_string = function(s) return s end },
			zbc_bodycam = {
				set_power_gate = function() end,
				set_battery_source = function() end,
				set_device_source = function() end,
				set_tier_source = function() end,
			},
			zbc_optics = {
				on_repair = function() repair_calls = repair_calls + 1 end,
			},
			zbc_item_anim = {
				holding_power = function() return false end,
				is_insert = function(prev, cur) return prev and cur and (cur - prev > 0.02) end,
				request = function(what, t, hud) anim_calls[#anim_calls + 1] = { what = what, t = t, hud = hud } end,
				reset = function() end,
				update = function() end,
			},
			RegisterScriptCallback = function(name, fn) cbs[name] = fn end,
			printf = function() end,
		}, { __index = _G })

		local chunk = assert(loadfile("optional/bodycam_item/gamedata/scripts/zbc_item.script"))
		setfenv(chunk, env)
		chunk()
		env.on_game_start()

		return env, {
			cbs = cbs,
			add_item = add_item,
			set_time = function(t) now_ms = t end,
			get_repairs = function() return repair_calls end,
			get_anims = function() return anim_calls end,
		}
	end

	-- 4a. Gating across Body 1..5
	local M, H = make_env()
	H.cbs.actor_on_first_update()
	check(M.has_flex_pov() == false and M.active_device_label() == nil, "empty inventory: no flex pov, nil label")

	local flex = H.add_item(900, "zbc_flex_pov", 1.0)
	H.cbs.actor_on_item_take()
	H.set_time(1000)
	H.cbs.actor_on_update()
	check(M.has_flex_pov() == false and M.active_device_label() == nil, "flex pov alone without camera: false / nil")

	local cases = {
		{ id = 101, sec = "zbc_bodycam_1",    want_flex = false, want_label = "AXON BODY" },
		{ id = 102, sec = "zbc_bodycam_2",    want_flex = false, want_label = "AXON BODY 2" },
		{ id = 103, sec = "zbc_bodycam_3",    want_flex = false, want_label = "AXON BODY 3" },
		{ id = 104, sec = "zbc_bodycam_item", want_flex = true,  want_label = "AXON FLEX POV" },
		{ id = 105, sec = "zbc_bodycam_5",    want_flex = true,  want_label = "AXON FLEX POV" },
	}
	local t = 2000
	for _, c in ipairs(cases) do
		local cam = H.add_item(c.id, c.sec, 0.90)
		H.cbs.actor_on_item_take()
		t = t + 1000
		H.set_time(t)
		H.cbs.actor_on_update()
		check(M.has_flex_pov() == c.want_flex, c.sec .. " with zbc_flex_pov: has_flex_pov() == " .. tostring(c.want_flex))
		check(M.active_device_label() == c.want_label, c.sec .. " label == " .. c.want_label .. ", got " .. tostring(M.active_device_label()))
		cam._parent = nil
		H.cbs.actor_on_item_drop()
	end

	-- Body 4 active with flex pov, then drop flex pov -> immediately reverts to AXON BODY 4
	local b4 = H.add_item(114, "zbc_bodycam_item", 0.90)
	H.cbs.actor_on_item_take()
	t = t + 1000
	H.set_time(t)
	H.cbs.actor_on_update()
	check(M.has_flex_pov() == true and M.active_device_label() == "AXON FLEX POV", "Body 4 + flex pov active")
	flex._parent = nil
	check(M.has_flex_pov() == false and M.active_device_label() == "AXON BODY 4", "dropping flex pov reverts label to AXON BODY 4")
	b4._parent = nil

	-- 4b. Polish #1: battery swap on same camera MUST NOT clear lens crack; switching camera DOES; toolkit repair DOES
	local M2, H2 = make_env()
	local cam4 = H2.add_item(204, "zbc_bodycam_item", 0.50)
	H2.cbs.actor_on_first_update()
	check(H2.get_repairs() == 0, "initial first_update does not call on_repair")

	-- Simulate battery insert on cam4
	cam4._cond = 1.0
	H2.set_time(1500)
	H2.cbs.actor_on_update()
	check(#H2.get_anims() == 1 and H2.get_anims()[1].what == "insert", "battery insert detected and queued")
	check(H2.get_repairs() == 0, "battery insert on same camera does NOT call zbc_optics.on_repair()")

	-- Simulate switching to a different camera (cam5 with full charge while cam4 is low)
	cam4._cond = 0.20
	H2.set_time(2500)
	H2.cbs.actor_on_update()
	H2.add_item(205, "zbc_bodycam_5", 1.0)
	H2.cbs.actor_on_item_take()
	H2.set_time(3500)
	H2.cbs.actor_on_update()
	check(M2.active_device_label() == "AXON BODY 5", "switched to Body 5")
	check(H2.get_repairs() == 1, "switching to a different camera calls zbc_optics.on_repair()")

	-- Toolkit repair helper
	check(M2.repair_lens_with_toolkit() == false, "repair_lens_with_toolkit fails without a toolkit/repair kit")
	check(H2.get_repairs() == 1, "no repair call without toolkit")

	local kit = H2.add_item(301, "itm_basickit", 1.0)
	check(M2.repair_lens_with_toolkit() == true, "repair_lens_with_toolkit succeeds with itm_basickit")
	check(H2.get_repairs() == 2, "itm_basickit triggers zbc_optics.on_repair()")
	kit._parent = nil

	local clean = H2.add_item(302, "cleaning_kit_u", 1.0)
	check(M2.repair_lens_with_toolkit() == true, "repair_lens_with_toolkit succeeds with cleaning_kit_u")
	check(H2.get_repairs() == 3, "cleaning_kit_u triggers zbc_optics.on_repair()")
	clean._parent = nil
end

if failures > 0 then
	print("zbc_flex_pov_test: " .. failures .. " failure(s)")
	os.exit(1)
end
print("zbc_flex_pov_test: all checks passed")
