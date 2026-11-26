-- Unit & static shader regression tests for shader-ext:
--   - Polish #3: Shader-side OSD tags (bus_zbc_ext.w -> SIGNAL/MUTE/BUF/SYNC/ALERT in zbc_osd.h)
--   - Feature #1: Weapon/Chest occlusion (bus_zbc_ext.x in zbc_lens.h, Flex POV zeroing)
--   - Feature #3: Anomaly Electro/Thermal shader artifacts (bus_zbc_ext.y / .z in zbc_lens.h)
--   - gamedata/scripts/zbc_anomalies.script
--
-- Usage (from the repo root): lua tools/tests/zbc_anomalies_test.lua

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

local function load_anomalies(bus_mock, db_mock)
	local env = setmetatable({ shader_bus = bus_mock, db = db_mock }, { __index = _G })
	local chunk = assert(loadfile("gamedata/scripts/zbc_anomalies.script"))
	setfenv(chunk, env)
	local ok, err = pcall(chunk)
	check(ok, "zbc_anomalies.script loads: " .. tostring(err))
	return env
end

---------------------------------------------------------------------------------------------------
-- 1. Defaults & OSD tag encoding
---------------------------------------------------------------------------------------------------
do
	local mod = load_anomalies(nil, nil)
	check(mod.DEFAULTS.chest_occlusion == true, "default chest_occlusion = true")
	check(math.abs(mod.DEFAULTS.chest_occlusion_strength - 0.75) < 1e-9, "default chest_occlusion_strength = 0.75")
	check(mod.DEFAULTS.anomaly_artifacts == true, "default anomaly_artifacts = true")

	check(mod.encode_osd_tag("SIGNAL") == 1, "SIGNAL -> 1")
	check(mod.encode_osd_tag("MUTE")   == 2, "MUTE -> 2")
	check(mod.encode_osd_tag("BUF")    == 3, "BUF -> 3")
	check(mod.encode_osd_tag("SYNC")   == 4, "SYNC -> 4")
	check(mod.encode_osd_tag("ALERT")  == 5, "ALERT -> 5")
	check(mod.encode_osd_tag("signal") == 1, "lowercase signal -> 1")
	check(mod.encode_osd_tag("  BUF ") == 3, "whitespace-padded BUF -> 3")
	check(mod.encode_osd_tag("")       == 0, "empty string -> 0")
	check(mod.encode_osd_tag("OTHER")  == 0, "unknown tag -> 0")
	check(mod.encode_osd_tag(nil)      == 0, "nil -> 0")
	check(mod.encode_osd_tag(42)       == 0, "non-string -> 0")
end

---------------------------------------------------------------------------------------------------
-- 2. ADS & reload chest occlusion smoothing, and Flex POV / config zeroing
---------------------------------------------------------------------------------------------------
do
	local mod = load_anomalies(nil, nil)
	mod.reset()

	-- At rest: zero occlusion
	local x0 = select(1, mod.update(0.05, false, false, false, 0, 0, nil, nil))
	check(x0 == 0, "at rest chest_occlusion is 0 (" .. x0 .. ")")

	-- ADS rises smoothly (monotonically increasing, not instantaneous snap)
	local prev = 0
	local vals = {}
	for i = 1, 20 do
		local x = select(1, mod.update(0.03, true, false, false, 0, 0, nil, nil))
		vals[i] = x
		check(x > prev, "ADS occlusion rises smoothly step " .. i .. " (" .. prev .. " -> " .. x .. ")")
		prev = x
	end
	check(vals[1] < vals[20] * 0.5, "ADS occlusion eases in smoothly rather than snapping (" .. vals[1] .. " vs " .. vals[20] .. ")")
	-- Default strength 0.75 * 0.78 = 0.585
	check(vals[20] > 0.50 and vals[20] <= 0.60, "ADS occlusion settles near 0.78 * 0.75 (" .. vals[20] .. ")")

	-- Reloading rises even higher than ADS (1.0 * 0.75 = 0.75)
	local x_reload = vals[20]
	for _ = 1, 30 do
		x_reload = select(1, mod.update(0.03, false, true, false, 0, 0, nil, nil))
	end
	check(x_reload > vals[20] and x_reload > 0.70 and x_reload <= 0.76, "reload occlusion settles higher than ADS (" .. x_reload .. ")")

	-- Releasing ADS/reload decays smoothly all the way back to exact 0
	local x_prev = x_reload
	local x_rel = x_reload
	for i = 1, 5 do
		x_rel = select(1, mod.update(0.04, false, false, false, 0, 0, nil, nil))
		check(x_rel < x_prev and x_rel > 0, "occlusion decays smoothly step " .. i .. " (" .. x_rel .. ")")
		x_prev = x_rel
	end
	for _ = 1, 80 do
		x_rel = select(1, mod.update(0.05, false, false, false, 0, 0, nil, nil))
	end
	check(x_rel == 0, "occlusion decays cleanly to exact 0 (" .. x_rel .. ")")

	-- Flex POV automatically zeros chest_occlusion even while aiming & reloading!
	mod.update(0.2, true, true, false, 0, 0, nil, nil)
	local x_flex = select(1, mod.update(0.05, true, true, true, 0, 0, nil, nil))
	check(x_flex == 0, "has_flex_pov=true automatically forces chest_occlusion = 0 (" .. x_flex .. ")")

	-- cfg.chest_occlusion = false automatically zeros chest_occlusion
	mod.update(0.2, true, true, false, 0, 0, nil, nil)
	local x_off = select(1, mod.update(0.05, true, true, false, 0, 0, nil, { chest_occlusion = false }))
	check(x_off == 0, "cfg.chest_occlusion=false forces chest_occlusion = 0 (" .. x_off .. ")")
end

---------------------------------------------------------------------------------------------------
-- 3. Electro & Thermal anomaly spikes, steady hum, and decay
---------------------------------------------------------------------------------------------------
do
	local mod = load_anomalies(nil, nil)
	mod.reset()

	-- Entering Electro proximity triggers an immediate rolling-shutter EM spike
	local _, y_first = mod.update(0.02, false, false, false, 0.85, 0, nil, nil)
	check(y_first > 0.75 and y_first <= 1.0, "Electro entry triggers immediate EM spike (" .. y_first .. ")")

	-- While staying in Electro proximity, spike decays toward hum and periodically re-spikes
	local y_min, y_max = 1, 0
	local y_prev = y_first
	local respikes = 0
	for _ = 1, 120 do
		local _, y = mod.update(0.03, false, false, false, 0.85, 0, nil, nil)
		if y < y_min then y_min = y end
		if y > y_max then y_max = y end
		if y > y_prev + 0.15 then respikes = respikes + 1 end
		y_prev = y
	end
	check(y_max - y_min > 0.25, "Electro band fluctuates between spikes and hum (" .. y_min .. ".." .. y_max .. ")")
	check(respikes >= 2, "Electro discharges re-spike periodically near anomaly (" .. respikes .. " spikes)")

	-- Leaving Electro proximity decays cleanly to exact 0
	local y_dec = y_prev
	for _ = 1, 80 do
		_, y_dec = mod.update(0.05, false, false, false, 0, 0, nil, nil)
	end
	check(y_dec == 0, "Electro band decays cleanly to exact 0 after leaving (" .. y_dec .. ")")

	-- Entering Thermal proximity flares & builds convective shimmer, then decays smoothly to exact 0
	mod.reset()
	local _, _, z_entry = mod.update(0.02, false, false, false, 0, 0.90, nil, nil)
	check(z_entry > 0.70 and z_entry <= 1.0, "Thermal entry triggers convective shimmer surge (" .. z_entry .. ")")

	local z_steady = 0
	for _ = 1, 40 do
		_, _, z_steady = mod.update(0.05, false, false, false, 0, 0.90, nil, nil)
	end
	check(z_steady > 0.65 and z_steady <= 1.0, "Thermal shimmer sustains near Burner (" .. z_steady .. ")")

	-- Leaving Thermal proximity: decays smoothly (not instant drop) then reaches exact 0
	local _, _, z_step1 = mod.update(0.05, false, false, false, 0, 0, nil, nil)
	check(z_step1 > 0.1 and z_step1 < z_steady, "Thermal shimmer lingers briefly while decaying (" .. z_step1 .. ")")
	local z_end = z_step1
	for _ = 1, 120 do
		_, _, z_end = mod.update(0.05, false, false, false, 0, 0, nil, nil)
	end
	check(z_end == 0, "Thermal shimmer decays cleanly to exact 0 (" .. z_end .. ")")

	-- anomaly_artifacts = false disables both Electro and Thermal
	local _, y_off, z_off = mod.update(0.05, false, false, false, 1.0, 1.0, nil, { anomaly_artifacts = false })
	check(y_off == 0 and z_off == 0, "cfg.anomaly_artifacts=false disables electro & thermal")
end

---------------------------------------------------------------------------------------------------
-- 4. detect_anomaly_proximity(actor) safety (headless + mocked Anomaly db)
---------------------------------------------------------------------------------------------------
do
	-- Headless (no db, nil actor): returns (0, 0) cleanly without errors
	local mod_nil = load_anomalies(nil, nil)
	local el0, th0 = mod_nil.detect_anomaly_proximity(nil)
	check(el0 == 0 and th0 == 0, "headless nil actor returns (0, 0)")

	local function vec(x, y, z)
		return {
			x = x, y = y, z = z,
			distance_to = function(self, other)
				local dx, dy, dz = self.x - other.x, self.y - other.y, self.z - other.z
				return math.sqrt(dx * dx + dy * dy + dz * dz)
			end,
		}
	end
	local actor = { position = function() return vec(0, 0, 0) end }
	local el_nodb, th_nodb = mod_nil.detect_anomaly_proximity(actor)
	check(el_nodb == 0 and th_nodb == 0, "headless actor without db returns (0, 0)")

	-- Mocked Anomaly db with Electro, Burner, and benign campfire
	local mock_db = {
		anomaly_by_name = {
			anm_elec_1 = {
				object = {
					section  = function() return "zone_witches_galantine_average" end,
					name     = function() return "anm_elec_1" end,
					position = function() return vec(4.0, 0, 0) end,
				},
			},
			anm_burn_1 = {
				object = {
					section  = function() return "zone_zharka_static_strong" end,
					name     = function() return "anm_burn_1" end,
					position = function() return vec(0, 0, 3.0) end,
				},
			},
			camp_1 = {
				object = {
					section  = function() return "zone_campfire_grill" end,
					name     = function() return "camp_1" end,
					position = function() return vec(0.5, 0, 0) end,
				},
			},
		},
	}
	local mod_db = load_anomalies(nil, mock_db)
	local el_p, th_p = mod_db.detect_anomaly_proximity(actor)
	check(el_p > 0.70 and el_p < 0.80, "Electro zone at 4m yields expected proximity (" .. el_p .. ")")
	check(th_p > 0.80 and th_p < 0.88, "Burner zone at 3m yields expected proximity (" .. th_p .. ")")

	-- Campfire alone must never trigger thermal anomaly shimmer
	local camp_only = load_anomalies(nil, {
		anomaly_by_name = { camp_1 = mock_db.anomaly_by_name.camp_1 },
	})
	local el_c, th_c = camp_only.detect_anomaly_proximity(actor)
	check(el_c == 0 and th_c == 0, "campfire is ignored by anomaly proximity detector")
end

---------------------------------------------------------------------------------------------------
-- 5. Shader Bus transport, 0.0005 change-threshold caching, zero(), disabled no-op
---------------------------------------------------------------------------------------------------
do
	local calls = {}
	local registered = {}
	local mock_bus = {
		try_register = function(lane, owner, desc)
			registered[lane] = { owner = owner, desc = desc }
			return "tok_" .. lane
		end,
		set = function(tok, x, y, z, w)
			calls[#calls + 1] = { tok = tok, x = x, y = y, z = z, w = w }
		end,
	}

	local mod = load_anomalies(mock_bus, nil)
	mod.reset()

	-- First update registers "zbc_ext" and sends (0, 0, 0, 0)
	local x, y, z, w = mod.update(0.05, false, false, false, 0, 0, nil, nil)
	check(registered.zbc_ext ~= nil, "registers Shader Bus lane 'zbc_ext'")
	check(#calls == 1 and calls[1].tok == "tok_zbc_ext", "first update sends to Shader Bus")
	check(x == 0 and y == 0 and z == 0 and w == 0, "idle update returns (0,0,0,0)")

	-- Repeated identical idle updates suppressed by 0.0005 change-threshold cache
	for _ = 1, 10 do
		mod.update(0.05, false, false, false, 0, 0, nil, nil)
	end
	check(#calls == 1, "identical idle frames do not spam shader_bus.set (" .. #calls .. ")")

	-- Active update with OSD tag sends new values
	local x2, y2, z2, w2 = mod.update(0.05, true, false, false, 0.7, 0.6, "ALERT", nil)
	check(#calls == 2, "active update sends new values to Shader Bus")
	check(x2 > 0 and y2 > 0 and z2 > 0 and w2 == 5, "active update outputs all 4 lanes")
	check(calls[2].w == 5, "Shader Bus w lane receives ALERT=5")

	-- Master disabled forces (0, 0, 0, 0) send & return
	local xd, yd, zd, wd = mod.update(0.05, true, true, false, 1.0, 1.0, "SIGNAL", { enabled = false })
	check(xd == 0 and yd == 0 and zd == 0 and wd == 0, "enabled=false returns (0,0,0,0)")
	check(#calls == 3 and calls[3].x == 0 and calls[3].y == 0 and calls[3].z == 0 and calls[3].w == 0,
		"enabled=false sends (0,0,0,0) to Shader Bus")

	-- clear_send_cache() forces next zero() to transmit again
	mod.clear_send_cache()
	mod.zero()
	check(#calls == 4 and calls[4].x == 0 and calls[4].w == 0, "clear_send_cache() + zero() re-transmits (0,0,0,0)")
end

---------------------------------------------------------------------------------------------------
-- 6. Static HLSL verification (uniform, guards, wrapped clock, OSD tags, 0 extra taps)
---------------------------------------------------------------------------------------------------
do
	local lens = read("gamedata/shaders/r3/zbc_lens.h")
	local osd  = read("gamedata/shaders/r3/zbc_osd.h")

	check(lens:find("uniform float4 bus_zbc_ext;", 1, true) ~= nil, "zbc_lens.h declares uniform float4 bus_zbc_ext")
	check(lens:find("ZBC_EXT_UV", 1, true) ~= nil, "zbc_lens.h defines ZBC_EXT_UV")
	check(lens:find("ZBC_EXT_COLOR", 1, true) ~= nil, "zbc_lens.h defines ZBC_EXT_COLOR")
	check(lens:find("bus_zbc_ext%.x > 0%.001") ~= nil, "chest_occlusion guarded by bus_zbc_ext.x > 0.001")
	check(lens:find("bus_zbc_ext%.y > 0%.001") ~= nil, "electro_band guarded by bus_zbc_ext.y > 0.001")
	check(lens:find("bus_zbc_ext%.z > 0%.001") ~= nil, "thermal_shimmer guarded by bus_zbc_ext.z > 0.001")
	check(lens:find("0%.28 %* mask") ~= nil, "chest_occlusion darkening capped at 28%")
	check(lens:find("float2 zbc_ext_uv%(", 1, false) ~= nil, "zbc_lens.h defines zbc_ext_uv()")
	check(lens:find("float3 zbc_ext_pass%(", 1, false) ~= nil, "zbc_lens.h defines zbc_ext_pass()")

	-- Exact SampleLevel count preserved (9 taps in zbc_lens.h, 0 in postprocess*.ps)
	local _, taps = lens:gsub("SampleLevel", "")
	check(taps == 9, "zbc_lens.h keeps exact 9 SampleLevel taps (" .. taps .. ")")

	-- OSD tag rendering in zbc_osd.h (all 5 tags present and gated inside SHADER_BUS >= 7)
	check(osd:find("zbc_osd_tag_code%(", 1, false) ~= nil, "zbc_osd.h defines zbc_osd_tag_code()")
	check(osd:find("zbc_osd_tag_char%(", 1, false) ~= nil, "zbc_osd.h defines zbc_osd_tag_char()")
	check(osd:find("bus_zbc_ext%.w", 1, false) ~= nil, "zbc_osd.h reads bus_zbc_ext.w")
	for _, tag in ipairs({ "SIGNAL", "MUTE", "BUF", "SYNC", "ALERT" }) do
		check(osd:find(tag, 1, true) ~= nil, "zbc_osd.h includes tag " .. tag)
	end

	-- Both postprocess shaders wire zbc_ext_uv and zbc_ext_pass before zbc_osd_composite with 0 extra taps
	for _, path in ipairs({ "gamedata/shaders/r3/postprocess.ps", "gamedata/shaders/r3/postprocess_cm.ps" }) do
		local src = read(path)
		check(src:find("zbc_ext_uv", 1, true) ~= nil, path .. " calls zbc_ext_uv")
		check(src:find("zbc_ext_pass", 1, true) ~= nil, path .. " calls zbc_ext_pass")
		check(src:find("zbc_osd_composite") > src:find("zbc_ext_pass"), path .. " draws OSD on top of zbc_ext_pass")
		check(not src:find("SampleLevel"), path .. " adds zero SampleLevel taps")
	end
end

if failures == 0 then
	print("ALL PASSED (zbc_anomalies_test)")
	os.exit(0)
else
	print("FAILED: " .. failures .. " checks")
	os.exit(1)
end
