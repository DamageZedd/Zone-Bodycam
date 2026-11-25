-- Tests the bodycam item charge as the player sees it:
--  * the blue charge bar on the inventory icon: vanilla utils_ui UICellItem:Add_ProgressBar only draws it for
--    sections with use_condition, coloured by condition_bar (power_progess_bar = the blue device bar). Set on
--    [zbc_bodycam_item], inherited by Body 1/2/3/5, never overridden by them or by the HD icons DLTX patch;
--  * the real-time drain survives the engine's float32 condition (regression: at long battery life, a low
--    difficulty factor and high fps one frame of drain rounded back to the stored value and the camera
--    never drained - "the items do not use batteries").
--
-- Usage (from the repo root): lua tools/tests/zbc_item_battery_bar_test.lua

local SCRIPT = arg and arg[1] or "optional/bodycam_item/gamedata/scripts/zbc_item.script"

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

-- { section = { parents = "...", keys = { key = value } } }; "![name]" (DLTX override) counts too
local function parse_ltx(s)
	local sections, cur = {}, nil
	for line in (s .. "\n"):gmatch("([^\n]*)\n") do
		line = line:gsub("\r$", ""):gsub(";.*$", "")
		local name, parents = line:match("^%s*!?%[([^%]:]+)%]:?(%S*)")
		if name then
			cur = { parents = parents, keys = {} }
			sections[name] = cur
		elseif cur then
			local k, v = line:match("^%s*!?([%w_$]+)%s*=?%s*(.-)%s*$")
			if k and k ~= "" then cur.keys[k] = v end
		end
	end
	return sections
end

local CAMS = { "zbc_bodycam_1", "zbc_bodycam_2", "zbc_bodycam_3", "zbc_bodycam_item", "zbc_bodycam_5" }

---------------------------------------------------------------------------------------------------
-- Charge bar on the icon
---------------------------------------------------------------------------------------------------
do
	local items = parse_ltx(read("optional/bodycam_item/gamedata/configs/items/items/items_zbc_bodycam.ltx"))
	local base = items.zbc_bodycam_item
	check(base ~= nil, "items_zbc_bodycam.ltx has [zbc_bodycam_item]")
	if base then
		check(base.keys.use_condition == "true", "Body 4 base: use_condition = true (utils_ui only draws a bar with it)")
		check(base.keys.condition_bar == "power_progess_bar",
			"Body 4 base: condition_bar = power_progess_bar (the blue device bar, vanilla spelling)")
	end
	for _, sec in ipairs(CAMS) do
		local s = items[sec]
		check(s ~= nil, sec .. " exists")
		if s and sec ~= "zbc_bodycam_item" then
			check(s.parents == "zbc_bodycam_item", sec .. " inherits [zbc_bodycam_item] (and its charge bar)")
			check(s.keys.use_condition == nil and s.keys.condition_bar == nil,
				sec .. " does not override use_condition / condition_bar")
		end
	end

	-- HD icons option: a DLTX patch that must leave the bar keys alone
	local hd = parse_ltx(read("optional/bodycam_item_hd_icons/gamedata/configs/mod_system_zbc_bodycam_hd_icons.ltx"))
	for _, sec in ipairs(CAMS) do
		local s = hd[sec]
		check(s ~= nil, "HD patch covers " .. sec)
		if s then
			check(s.keys.use_condition == nil and s.keys.condition_bar == nil,
				"HD patch does not touch use_condition / condition_bar on " .. sec)
		end
	end
end

---------------------------------------------------------------------------------------------------
-- Drain through a float32 condition
---------------------------------------------------------------------------------------------------

-- round to the nearest float32, like CInventoryItem::m_fCondition
local function f32(x)
	if x == 0 then return 0 end
	local m, e = math.frexp(x)
	m = math.floor(m * 16777216 + 0.5) / 16777216
	return math.ldexp(m, e)
end

-- runs the script's real actor_on_update for `seconds` at `fps`; returns the start and end charge
local function simulate(sec, hours, eco, fps, seconds, start, mid_hook)
	local cbs = {}
	local now_ms = 1000
	local cond = f32(start or 1)
	local obj = {
		id = function() return 7 end,
		section = function() return sec end,
		condition = function() return cond end,
		set_condition = function(_, c) cond = f32(math.max(0, math.min(1, c))) end,
		parent = function() return { id = function() return 0 end } end,
	}
	local chunk = assert(loadfile(SCRIPT))
	local env = setmetatable({
		AC_ID = 0,
		db = { actor = { iterate_inventory = function(_, fn, ctx) fn(ctx, obj) end } },
		time_global = function() return now_ms end,
		level = { object_by_id = function(id) return id == 7 and obj or nil end },
		ui_mcm = { get = function(k)
			if k == "zone_bodycam/enabled" then return true end
			if k == "zone_bodycam_item/battery_game_hours" then return hours end
			return nil
		end },
		item_device = { get_power_critical = function() return 0.05 end },
		game_difficulties = { get_eco_factor = function() return eco end },
		actor_menu = { set_msg = function() end },
		game = { translate_string = function(s) return s end },
		sound_object = function() return { play = function() end } end,
		zbc_bodycam = { set_power_gate = function() end },
		RegisterScriptCallback = function(name, fn) cbs[name] = fn end,
		printf = function() end,
	}, { __index = _G })
	setfenv(chunk, env)
	chunk()
	env.on_game_start()
	cbs.actor_on_first_update()
	local frames = math.floor(seconds * fps)
	local acc = 0
	for i = 1, frames do
		acc = acc + 1000 / fps
		local step = math.floor(acc)
		acc = acc - step
		now_ms = now_ms + step
		cbs.actor_on_update()
		if mid_hook and i == math.floor(frames / 2) then
			cond = f32(mid_hook(cond))
		end
	end
	return f32(start or 1), cond
end

local function expected_loss(mult, hours, eco, seconds)
	return seconds / (hours * 3600) * eco * mult
end

-- Body 5 (0.833), longest battery (48 h), GAMMA's easiest economy (0.5), 240 fps: one frame is ~1e-8,
-- below half a float step at full charge (3e-8). Before the fix the charge never moved.
do
	local s, e = simulate("zbc_bodycam_5", 48, 0.5, 240, 600)
	local want = expected_loss(0.833, 48, 0.5, 600)
	local got = s - e
	check(got > 0, ("48 h / eco 0.5 / Body 5 at 240 fps drains at all (lost %.3g)"):format(got))
	check(math.abs(got - want) <= want * 0.05,
		("48 h / eco 0.5 / Body 5 at 240 fps drains at the set rate: lost %.4g, want %.4g"):format(got, want))
end

-- 12 h, eco 0.5, Body 5 at 165 fps (a common monitor): each frame sits right at half a float step
do
	local s, e = simulate("zbc_bodycam_5", 12, 0.5, 165, 600)
	local want = expected_loss(0.833, 12, 0.5, 600)
	check(math.abs((s - e) - want) <= want * 0.05,
		("12 h / eco 0.5 / Body 5 at 165 fps: lost %.4g, want %.4g"):format(s - e, want))
end

-- default 4 h, Body 4, eco 1 at 60 fps: the set rate, not one rounded float step per frame
do
	local s, e = simulate("zbc_bodycam_item", 4, 1, 60, 600)
	local want = expected_loss(1, 4, 1, 600)
	check(math.abs((s - e) - want) <= want * 0.05,
		("4 h / eco 1 / Body 4 at 60 fps: lost %.4g, want %.4g"):format(s - e, want))
end

-- a battery put in mid-way (the condition changed by someone else) is picked up, not overwritten by the
-- kept exact charge
do
	local _, e = simulate("zbc_bodycam_item", 4, 1, 60, 60, 0.30, function() return 0.90 end)
	check(e > 0.85 and e < 0.90, ("a new battery mid-drain is kept and drained from (now %.4f)"):format(e))
end

-- base_charge contract
do
	local chunk = assert(loadfile(SCRIPT))
	local env = setmetatable({}, { __index = _G })
	setfenv(chunk, env)
	chunk()
	check(type(env.base_charge) == "function", "zbc_item.base_charge exists")
	if type(env.base_charge) == "function" then
		check(env.base_charge(0.99999999, 1.0, 1.0) == 0.99999999, "base_charge: unchanged item -> exact charge")
		check(env.base_charge(0.99999999, 1.0, 0.5) == 0.5, "base_charge: changed item -> item's charge")
		check(env.base_charge(nil, nil, 0.4) == 0.4, "base_charge: nothing kept -> item's charge")
	end
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_item_battery_bar_test: all checks passed")
