-- Tests the camera generations (tiers): gamedata/scripts/zbc_tiers.script (profiles and how they meet the
-- MCM), which tier the item component reports (optional/bodycam_item/.../zbc_item.script), the hook in
-- zbc_bodycam.script, and the item configs: only Body 1 is sold and given on a new game, Body 2-5 are
-- crafted in a chain like GAMMA's night vision goggles.
--
-- Usage (from the repo root): lua tools/tests/zbc_tiers_test.lua

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
	__add = function() return 0 end, __sub = function() return 0 end,
	__mul = function() return 0 end, __div = function() return 0 end,
	__unm = function() return 0 end, __concat = function() return "" end,
	__lt = function() return false end, __le = function() return false end,
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
local function read(path)
	local f = assert(io.open(path, "rb"))
	local s = f:read("*a")
	f:close()
	return (s:gsub("\r\n", "\n"))
end

local T = load_script("gamedata/scripts/zbc_tiers.script")
local B = load_script("gamedata/scripts/zbc_bodycam.script", { zbc_tiers = T })
local I = load_script("optional/bodycam_item/gamedata/scripts/zbc_item.script")

local defaults = rawget(B, "defaults")
check(type(defaults) == "table", "zbc_bodycam defaults exist")
local CLAMPS = {   -- the MCM ranges of the scaled keys (zbc_bodycam CLAMPS)
	grain = { 0, 1 }, compression = { 0, 1 }, sharpen = { 0, 1 }, edge_soft_blur = { 0, 1 },
	aberration = { 0, 1 }, rolling_shutter = { 0, 1.5 }, highlight_blowout = { 0, 1 },
	walk_bob = { 0, 5 }, impacts = { 0, 5 }, fx_glitch_strength = { 0, 1 }, zoom = { 0.25, 1.5 },
}
local DERIVED = { allies_decode_mult = true, allies_pip = true, dark_grain = true, zoom_mult = true }
local function copy(t) local o = {} for k, v in pairs(t) do o[k] = v end return o end

-- valid_tier
check(T.valid_tier(1) == 1 and T.valid_tier(5) == 5 and T.valid_tier("3") == 3, "valid tiers read")
check(T.valid_tier(0) == nil and T.valid_tier(6) == nil and T.valid_tier(nil) == nil and T.valid_tier(0 / 0) == nil,
	"out of range / nil / NaN: no tier")

-- no tier (the core mod alone) and Axon Body 4 (the reference) change nothing
for _, tier in ipairs({ false, 4 }) do
	local out = T.apply(defaults, tier or nil, CLAMPS)
	local same = true
	for k, v in pairs(defaults) do
		if out[k] ~= v then same = false; print("  differs: " .. k) end
	end
	for k in pairs(out) do
		if defaults[k] == nil and not DERIVED[k] then same = false; print("  extra key: " .. k) end
	end
	check(same, "tier " .. tostring(tier) .. ": the settings are the MCM's, unchanged")
	check(out.allies_decode_mult == 1 and out.allies_pip == true and out.dark_grain == 0 and out.zoom_mult == 1,
		"tier " .. tostring(tier) .. ": neutral decode speed, scope tags on, no dark grain, Body 4 field of view")
end

-- features: MCM AND camera, from the real cameras' specs
do
	local user = copy(defaults)
	user.night_mode = 0   -- IR set to auto in the MCM
	for t = 1, 5 do
		local c = T.apply(user, t, CLAMPS)
		check(c.show_name == (t >= 2) and c.gps_line == (t >= 3), ("Body %d: name from Body 2, GPS line from Body 3 (onboard GPS)"):format(t))
		check(c.night_mode == 0, ("Body %d: IR is the MCM's choice (no Axon Body has IR)"):format(t))
		check(c.auto_exposure == true and c.review_key == user.review_key and c.face_blur == user.face_blur,
			("Body %d: auto-exposure, footage review and face blur on every camera"):format(t))
		check(c.rec_timer and c.battery_gauge and c.event_marker and c.signal_lost,
			("Body %d keeps REC, battery gauge, EVENT and signal lost"):format(t))
	end
	local b1, b2 = T.apply(user, 1, CLAMPS), T.apply(user, 2, CLAMPS)
	for t, c in pairs({ b1, b2 }) do
		check(c.allies == false and c.allies_companion_edge == false and c.event_log == false,
			("Body %d: no LTE, so no live-map markers and no alerts log"):format(t))
	end
	local b3 = T.apply(user, 3, CLAMPS)
	check(b3.allies and b3.allies_companion_edge and b3.event_log, "Body 3: LTE live map and alerts")
	check(b3.allies_enemies == true and b3.allies_mutants == false and b3.allies_pip == false,
		"Body 3: enemies, no mutants, no scope tags (Watch Me is Body 4)")
	check(b3.allies_range == user.allies_range, "Body 3: LTE has no range cap")
	local b5 = T.apply(user, 5, CLAMPS)
	check(b5.allies_mutants and b5.allies_pip and b5.allies_decode_mult == 1.5, "Body 5: everything, fastest ID")
	-- the MCM switch still wins on the best camera
	local off = copy(defaults)
	off.face_blur, off.event_log = false, false
	local b5off = T.apply(off, 5, CLAMPS)
	check(b5off.face_blur == false and b5off.event_log == false, "an MCM feature turned off stays off on Body 5")
	check(defaults.night_mode == 2, "IR night look is off by default")
end

-- effects: MCM x multiplier from the real specs, clamped; 0 stays 0
do
	local user = copy(defaults)
	local function x(t, k) return T.apply(user, t, CLAMPS)[k] / defaults[k] end
	-- resolution: 480 / 1080 / 1080 / 1440 / 2160 lines against Body 4's 1440
	local lines = { 480, 1080, 1080, 1440, 2160 }
	for t = 1, 5 do
		check(math.abs(x(t, "sharpen") - lines[t] / 1440) < 0.01, ("Body %d sharpening follows %dp"):format(t, lines[t]))
	end
	-- field of view: 130 / 143 / 143 / 160 / 160 deg; a narrower lens zooms in
	local fov = { 130, 143, 143, 160, 160 }
	for t = 1, 5 do
		local c = T.apply(user, t, CLAMPS)
		check(near(c.zoom_mult, 160 / fov[t], 1e-6) and c.zoom == defaults.zoom, ("Body %d zoom follows %d deg"):format(t, fov[t]))
	end
	-- the ratio is applied to the lens zoom the camera ends up with (after the distortion fill)
	check(read("gamedata/scripts/zbc_bodycam.script"):find("return max(z, fill_zoom(max(d, 0))) * (tonumber(cfg.zoom_mult) or 1)", 1, true) ~= nil,
		"lens_zoom multiplies the final zoom by the camera's field of view")
	-- compression: Body 1 at ~0.12 bits per pixel against Body 2's ~0.22
	check(near(x(1, "compression") / x(2, "compression"), 2.4 / 1.4), "Body 1 compresses ~1.7x Body 2")
	check(near(T.apply(user, 1, CLAMPS).dark_grain, T.apply(user, 2, CLAMPS).dark_grain), "Body 1 and 2: same low light")
	-- no generation publishes stabilization or interference differences
	for t = 1, 5 do
		local c = T.apply(user, t, CLAMPS)
		check(c.walk_bob == defaults.walk_bob and c.impacts == defaults.impacts and c.fx_glitch_strength == defaults.fx_glitch_strength,
			("Body %d: same shake and interference"):format(t))
		check(c.distortion == defaults.distortion and c.vignette == defaults.vignette, ("Body %d: lens shape is the MCM's"):format(t))
	end
	local hi = copy(defaults)
	hi.grain, hi.rolling_shutter = 0.9, 1.4
	local c = T.apply(hi, 1, CLAMPS)
	check(c.grain == 1 and c.rolling_shutter == 1.5, "scaled values stay in the MCM range")
	local zero = copy(defaults)
	zero.grain, zero.compression = 0, 0
	local z = T.apply(zero, 1, CLAMPS)
	check(z.grain == 0 and z.compression == 0, "an effect at 0 in the MCM stays off")
end

-- every generation is at least as good as the one before
do
	local user = copy(defaults)
	local worse_up = { "grain", "compression", "edge_soft_blur", "aberration", "rolling_shutter", "highlight_blowout",
		"walk_bob", "impacts", "fx_glitch_strength", "dark_grain", "zoom_mult" }
	-- the identification options count only when identification is on at all
	local function eff(c)
		local o = copy(c)
		for k, v in pairs(c) do
			if k:match("^allies_") and not c.allies then
				if v == true then o[k] = false elseif type(v) == "number" then o[k] = 0 end
			end
		end
		return o
	end
	local prev = nil
	for t = 1, 5 do
		local cur = eff(T.apply(user, t, CLAMPS))
		if prev then
			for _, k in ipairs(worse_up) do
				check(cur[k] <= prev[k] + 1e-9, ("tier %d %s not worse than tier %d"):format(t, k, t - 1))
			end
			check(cur.sharpen >= prev.sharpen and cur.allies_decode_mult >= prev.allies_decode_mult
				and cur.allies_range >= prev.allies_range, ("tier %d sharper, faster, farther"):format(t))
			for k, v in pairs(prev) do
				if v == true then check(cur[k] == true, ("tier %d keeps %s of tier %d"):format(t, k, t - 1)) end
			end
		end
		prev = cur
	end
end

-- has_feature
check(T.has_feature(2, "allies") == false and T.has_feature(3, "allies") == true, "live-map markers from Body 3")
check(T.has_feature(2, "gps_line") == false and T.has_feature(3, "gps_line") == true, "GPS line from Body 3")
check(T.has_feature(1, "night_mode") == true and T.has_feature(1, "face_blur") == true, "IR and face blur: MCM options on every camera")

-- low-light grain
check(T.grain_in_dark(0.35, 0.6, 0) == 0.35, "lit: grain as set")
check(near(T.grain_in_dark(0.35, 0.6, 1), 0.56), "dark with a 0.6 boost: 60% more")
check(near(T.grain_in_dark(0.35, -0.2, 1), 0.28), "dark on Body 5: 20% less")
check(T.grain_in_dark(0.9, 0.6, 1) == 1 and T.grain_in_dark(0, 0.6, 1) == 0, "clamped, 0 stays 0")
check(T.grain_in_dark(0.35, 0, 1) == 0.35, "no boost: unchanged")

-- which tier the item reports
check(I.tier_of("zbc_bodycam_1") == 1 and I.tier_of("zbc_bodycam_2") == 2 and I.tier_of("zbc_bodycam_3") == 3,
	"Body 1-3 sections are tiers 1-3")
check(I.tier_of("zbc_bodycam_item") == 4 and I.tier_of("zbc_bodycam_5") == 5, "Body 4 (save-compatible section) is 4, Body 5 is 5")
check(I.tier_of(nil) == nil and I.tier_of("device_torch") == nil, "no camera: no tier")
check(I.tier_of("zbc_bodycam_1", false) == nil, "generation limits off in the MCM: no tier (works like Body 4)")

-- the hook in zbc_bodycam.script
do
	check(type(rawget(B, "set_tier_source")) == "function" and type(rawget(B, "active_tier")) == "function", "tier hook exists")
	local src = read("gamedata/scripts/zbc_bodycam.script")
	check(src:find("T.apply(user_cfg, cur_tier, CLAMPS, cfg)", 1, true) ~= nil, "load_settings applies the tier")
	check(src:find("function actor_on_update()\n\tif not cfg.enabled or in_menu then return end\n\tretier()", 1, true) ~= nil,
		"every update checks for a different camera generation")
	check(src:find("cur_tier = t\n\tclear_send_cache()\n\tload_settings()\n\tsync_lens_settings()", 1, true) ~= nil,
		"a new generation re-sends the lens lanes")
	local isrc = read("optional/bodycam_item/gamedata/scripts/zbc_item.script")
	check(isrc:find("zbc_bodycam.set_tier_source(active_tier)", 1, true) ~= nil, "the item registers its tier source")
end

-- configs
local CFG = "optional/bodycam_item/gamedata/configs/items/"
do
	local items = read(CFG .. "items/items_zbc_bodycam.ltx")
	local b1 = items:match("%[zbc_bodycam_1%]:zbc_bodycam_item\n(.-)\n\n")
	check(b1 and b1:match("cost%s*=%s*(%d+)") == "5000", "Body 1 costs 5,000")
end
do
	local trade_dir = CFG .. "trade"
	local cmd = package.config:sub(1, 1) == "\\"
		and ('dir /b "' .. trade_dir:gsub("/", "\\") .. '"')
		or ('ls "' .. trade_dir .. '"')
	local p = io.popen(cmd)
	local n = 0
	for name in p:lines() do
		if name:match("%.ltx$") then
			n = n + 1
			local s = read(CFG .. "trade/" .. name)
			check(s:find("zbc_bodycam_1%s*=%s*1,%s*1") ~= nil, name .. ": sells Body 1, always in stock")
			for _, sec in ipairs({ "zbc_bodycam_2", "zbc_bodycam_3", "zbc_bodycam_item", "zbc_bodycam_5" }) do
				for line in s:gmatch("[^\n]+") do
					if not line:match("^%s*;") and line:match("^%s*" .. sec .. "%s*=") then
						check(false, name .. ": " .. sec .. " is craft-only, not sold")
					end
				end
			end
		end
	end
	p:close()
	check(n == 21, "all 21 trader patches checked (" .. n .. ")")
end
do
	local s = read(CFG .. "settings/mod_new_game_loadouts_zbc_bodycam.ltx")
	check(s:find("!%[shared%]\nzbc_bodycam_1%s*=%s*false,%s*1,%s*0") ~= nil, "new game: every faction gets a Body 1 in the inventory")
end
do
	local s = read(CFG .. "settings/mod_craft_zbc_bodycam.ltx")
	check(s:find("!%[1%]") ~= nil, "recipes patch the workshop's Devices tab")
	local PARTS = { prt_i_resistors = true, prt_i_capacitors = true, prt_i_transistors = true, prt_i_copper = true,
		prt_i_textolite = true, prt_i_plastic = true, prt_i_scrap = true, prt_i_fasteners = true, batteries_dead = true }
	local CHAIN = { "zbc_bodycam_1", "zbc_bodycam_2", "zbc_bodycam_3", "zbc_bodycam_item", "zbc_bodycam_5" }
	local BOOK = { "recipe_basic_0", "recipe_basic_2", "recipe_advanced_2", "recipe_advanced_2", "recipe_expert_2" }
	local KIT = { 1, 1, 2, 2, 3 }
	local rec = {}
	for sec, val in s:gmatch("\nx_([%w_]+)%s*=%s*([^\n]+)") do rec[sec] = val end
	for i, sec in ipairs(CHAIN) do
		local val = rec[sec]
		check(val ~= nil, "recipe for " .. sec)
		if val then
			local f = {}
			for v in val:gmatch("[^,]+") do f[#f + 1] = v:match("^%s*(.-)%s*$") end
			check(tonumber(f[1]) == KIT[i], sec .. ": toolkit " .. KIT[i])
			check(f[2] == BOOK[i], sec .. ": " .. BOOK[i])
			check((#f - 2) % 2 == 0 and (#f - 2) / 2 <= 4, sec .. ": item,count pairs, at most 4")
			for j = 3, #f, 2 do
				local item, n = f[j], tonumber(f[j + 1])
				check(n and n >= 1, sec .. ": count for " .. tostring(item))
				if j == 3 and i > 1 then
					check(item == CHAIN[i - 1] and n == 1, sec .. ": made from one " .. CHAIN[i - 1])
				else
					check(PARTS[item], sec .. ": " .. tostring(item) .. " is a GAMMA part")
				end
			end
		end
	end
end

-- text: every new string in both languages
do
	for _, lang in ipairs({ "eng", "rus" }) do
		local s = read("optional/bodycam_item/gamedata/configs/text/" .. lang .. "/ui_st_zbc_bodycam_item.xml")
		for _, id in ipairs({ "st_zbc_no_review", "ui_mcm_zone_bodycam_item_tier_limits", "ui_mcm_zone_bodycam_item_tier_limits_desc" }) do
			check(s:find('"' .. id .. '"', 1, true) ~= nil, lang .. ": " .. id)
		end
		local gens = 0
		for _ in s:gmatch(lang == "eng" and "Generation %d of 5" or "\207\238\234\238\235\229\237\232\229 %d \232\231 5") do gens = gens + 1 end
		check(gens == 5, lang .. ": all five descriptions name their generation (" .. gens .. ")")
	end
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_tiers_test: all checks passed")
