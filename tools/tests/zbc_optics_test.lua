-- Unit & shader regression tests for Feature 3: Optical & Sensor Realism
-- (gamedata/scripts/zbc_optics.script + bus_zbc_optics in zbc_lens.h / postprocess*.ps).
--
-- Usage (from the repo root): lua tools/tests/zbc_optics_test.lua

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

local function load_optics(bus_mock)
	local env = setmetatable({ shader_bus = bus_mock }, { __index = _G })
	local chunk = assert(loadfile("gamedata/scripts/zbc_optics.script"))
	setfenv(chunk, env)
	local ok, err = pcall(chunk)
	check(ok, "zbc_optics.script loads: " .. tostring(err))
	return env
end

---------------------------------------------------------------------------------------------------
-- 1. Blowout peak (dark vs daylight) & tier-scaled recovery (Body 1 ~0.65s, Body 4 ~0.35s, Body 5 ~0.25s)
---------------------------------------------------------------------------------------------------
do
	local opt = load_optics(nil)

	-- Daylight vs pitch dark gunshot peak
	opt.reset()
	local peak_day = opt.on_gunshot(0.0, 4, nil)
	opt.reset()
	local peak_dark = opt.on_gunshot(1.0, 4, nil)
	check(peak_day > 0 and peak_day < 0.15, "daylight gunshot gives subtle blowout (" .. peak_day .. ")")
	check(peak_dark > 0.55 and peak_dark <= 1.0, "dark gunshot gives strong blowout (" .. peak_dark .. ")")
	check(peak_dark > peak_day * 5, "blowout is much stronger in the dark than in daylight")

	-- Rapid fire stacks slightly without exceeding 1
	local stacked = opt.on_gunshot(1.0, 4, nil)
	check(stacked > peak_dark and stacked <= 1.0, "rapid follow-up shot boosts blowout cleanly (" .. stacked .. ")")

	-- Tier-scaled recovery times: measure time to decay below 6% of initial peak
	local function measure_recovery(tier)
		opt.reset()
		local p0 = opt.on_gunshot(1.0, tier, { optics_blowout = true, optics_blowout_strength = 1.0 })
		local t, dt = 0, 0.01
		local val = p0
		while t < 2.0 and val > p0 * 0.055 do
			t = t + dt
			val = select(1, opt.update(dt, 1.0, 0, false, false, tier, { optics_blowout = true, optics_blowout_strength = 1.0 }))
		end
		return t, val
	end

	local t1 = measure_recovery(1)
	local t4 = measure_recovery(4)
	local t5 = measure_recovery(5)
	check(t1 >= 0.58 and t1 <= 0.72, "Body 1 recovery ~0.65s (" .. t1 .. "s)")
	check(t4 >= 0.30 and t4 <= 0.42, "Body 4 recovery ~0.35s (" .. t4 .. "s)")
	check(t5 >= 0.20 and t5 <= 0.30, "Body 5 recovery ~0.25s (" .. t5 .. "s)")
	check(t1 > t4 and t4 > t5, "recovery gets snappier across tiers: Body 1 > Body 4 > Body 5")

	-- Decays all the way to exact 0
	opt.reset()
	opt.on_gunshot(1.0, 5, nil)
	local x = 1
	for _ = 1, 80 do
		x = select(1, opt.update(0.02, 1.0, 0, false, false, 5, nil))
	end
	check(x == 0, "blowout snaps cleanly to 0 after recovery (" .. x .. ")")

	-- Disabled via cfg
	opt.reset()
	local off_peak = opt.on_gunshot(1.0, 1, { optics_blowout = false })
	check(off_peak == 0, "optics_blowout=false suppresses gunshot blowout")
end

---------------------------------------------------------------------------------------------------
-- 2. Low-light chroma noise scaling across Body 1..5
---------------------------------------------------------------------------------------------------
do
	local opt = load_optics(nil)

	-- Zero in bright daylight
	local _, y_day = opt.update(0.05, 0.0, 0, false, false, 1, nil)
	check(y_day == 0, "no low-light chroma noise in bright daylight")
	local _, y_dim = opt.update(0.05, 0.14, 0, false, false, 1, nil)
	check(y_dim == 0, "no low-light chroma noise below darkness threshold")

	-- Strictly monotonic across Body 1 > Body 2 > Body 3 > Body 4 > Body 5 in darkness
	local vals = {}
	for tier = 1, 5 do
		local _, y = opt.update(0.05, 1.0, 0, false, false, tier, { optics_chroma = true, optics_chroma_strength = 1.0 })
		vals[tier] = y
	end
	check(vals[1] > 0.9, "Body 1 has strongest low-light chroma noise (" .. vals[1] .. ")")
	check(vals[5] > 0.05 and vals[5] < 0.25, "Body 5 has cleanest low-light chroma noise (" .. vals[5] .. ")")
	for tier = 1, 4 do
		check(vals[tier] > vals[tier + 1],
			("chroma noise decreases from Body %d (%.3f) to Body %d (%.3f)"):format(tier, vals[tier], tier + 1, vals[tier + 1]))
	end

	-- Disabled via cfg
	local _, y_off = opt.update(0.05, 1.0, 0, false, false, 1, { optics_chroma = false })
	check(y_off == 0, "optics_chroma=false zeros chroma lane")
end

---------------------------------------------------------------------------------------------------
-- 3. Condensation buildup (rain, cold-to-warm indoor entry, sprinting), decay, and wipe clear
---------------------------------------------------------------------------------------------------
do
	local opt = load_optics(nil)
	local cfg = { optics_condensation = true, optics_condensation_strength = 1.0 }

	-- Rain outdoors builds condensation
	opt.reset()
	local z = 0
	for _ = 1, 100 do
		_, _, z = opt.update(0.1, 0.2, 1.0, false, false, 3, cfg)
	end
	check(z > 0.25 and z <= 1.0, "outdoor rain builds condensation (" .. z .. ")")

	-- Lens wipe rapidly clears condensation within ~0.4s
	opt.on_lens_wipe()
	local z_after_wipe = z
	for _ = 1, 20 do
		_, _, z_after_wipe = opt.update(0.025, 0.2, 1.0, false, false, 3, cfg)
	end
	check(z_after_wipe == 0, "on_lens_wipe() rapidly clears condensation (" .. z_after_wipe .. ")")

	-- Cold-to-warm transition: outdoors -> indoors triggers condensation surge
	opt.reset()
	opt.update(0.1, 0.5, 0.8, false, false, 3, cfg)   -- outdoors in rain
	local z_before = select(3, opt.update(0.01, 0.5, 0.8, false, false, 3, cfg))
	local z_indoor = z_before
	for _ = 1, 30 do
		_, _, z_indoor = opt.update(0.1, 0.5, 0.8, true, false, 3, cfg)   -- stepped indoors
	end
	check(z_indoor > z_before + 0.25, "stepping indoors from cold/rainy outdoors fogs lens (" .. z_before .. " -> " .. z_indoor .. ")")

	-- Natural evaporation indoors once thermal shock finishes
	local z_evap = z_indoor
	for _ = 1, 200 do
		_, _, z_evap = opt.update(0.2, 0.5, 0.0, true, false, 3, cfg)
	end
	check(z_evap < z_indoor and z_evap == 0, "condensation evaporates cleanly when dry/acclimatized (" .. z_evap .. ")")

	-- Heavy sprinting builds condensation
	opt.reset()
	local z_sprint = 0
	for _ = 1, 100 do
		_, _, z_sprint = opt.update(0.1, 0.0, 0.0, false, true, 3, cfg)
	end
	check(z_sprint > 0.20, "heavy sprinting builds condensation (" .. z_sprint .. ")")

	-- Instant wipe option
	opt.on_lens_wipe(true)
	local z_inst = select(3, opt.update(0.0, 0.0, 0.0, false, false, 3, cfg))
	check(z_inst == 0, "on_lens_wipe(true) clears instantly")
end

---------------------------------------------------------------------------------------------------
-- 4. Hairline lens crack, Body 5 sapphire 80% resistance, and repair
---------------------------------------------------------------------------------------------------
do
	local opt = load_optics(nil)

	-- Minor hit below threshold never cracks
	opt.reset()
	local hit, cr = opt.on_heavy_hit(0.15, 1, nil, function() return 0.0 end)
	check(not hit and cr == 0, "sub-threshold hit never cracks lens")

	-- Body 1 vs Body 5 deterministic resistance check:
	-- At power=1.0: base_chance = 0.72.
	--   Body 1 (resist 0.00): chance = 0.72
	--   Body 5 (resist 0.80): chance = 0.72 * 0.20 = 0.144
	-- A roll of 0.20 cracks Body 1, but Body 5 sapphire shrugs it off!
	opt.reset()
	local hit_b1, cr_b1 = opt.on_heavy_hit(1.0, 1, nil, function() return 0.20 end)
	check(hit_b1 and cr_b1 > 0.3, "Body 1 cracks on roll 0.20 (crack=" .. cr_b1 .. ")")

	opt.reset()
	local hit_b5_blocked, cr_b5_blocked = opt.on_heavy_hit(1.0, 5, nil, function() return 0.20 end)
	check(not hit_b5_blocked and cr_b5_blocked == 0, "Body 5 sapphire resists roll 0.20 (80% crack resistance)")

	-- Statistical check over 1000 evenly spaced rolls: Body 5 crack rate is exactly 20% of Body 1
	local cracks_b1, cracks_b5 = 0, 0
	local N = 1000
	for i = 0, N - 1 do
		local r = (i + 0.5) / N
		opt.reset()
		if opt.on_heavy_hit(0.85, 1, nil, function() return r end) then cracks_b1 = cracks_b1 + 1 end
		opt.reset()
		if opt.on_heavy_hit(0.85, 5, nil, function() return r end) then cracks_b5 = cracks_b5 + 1 end
	end
	local ratio = cracks_b5 / math.max(cracks_b1, 1)
	check(math.abs(ratio - 0.20) < 0.02,
		("Body 5 sapphire has 80%% crack resistance (cracks %d vs Body 1 %d, ratio=%.3f)"):format(cracks_b5, cracks_b1, ratio))

	-- Repair clears crack completely
	opt.reset()
	opt.on_heavy_hit(1.0, 1, nil, function() return 0.01 end)
	check(opt.get_crack() > 0, "crack is active before repair")
	opt.on_repair()
	check(opt.get_crack() == 0, "on_repair() clears lens crack")
	local _, _, _, w = opt.update(0.05, 0, 0, false, false, 1, nil)
	check(w == 0, "w lane reports 0 after repair")
end

---------------------------------------------------------------------------------------------------
-- 5. Save / load persistence of lens crack state
---------------------------------------------------------------------------------------------------
do
	local opt = load_optics(nil)
	opt.reset()
	opt.on_heavy_hit(0.9, 1, nil, function() return 0.01 end)
	local saved_crack = opt.get_crack()
	check(saved_crack > 0.3, "cracked lens before save (" .. saved_crack .. ")")

	local m_data = {}
	opt.save_state(m_data)
	check(type(m_data.zbc_optics) == "table" and m_data.zbc_optics.crack == saved_crack, "save_state stores crack in m_data.zbc_optics")

	-- Simulate fresh session / load
	opt.reset()
	check(opt.get_crack() == 0, "reset clears crack")
	opt.load_state(m_data)
	check(math.abs(opt.get_crack() - saved_crack) < 1e-9, "load_state restores persisted crack (" .. opt.get_crack() .. ")")

	-- Loading empty save clears crack cleanly
	opt.load_state({})
	check(opt.get_crack() == 0, "load_state with empty m_data starts uncracked")
end

---------------------------------------------------------------------------------------------------
-- 6. Shader Bus emission & change-threshold caching
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

	local opt = load_optics(mock_bus)
	opt.reset()

	-- First update registers "zbc_optics" and sends
	opt.update(0.05, 0.0, 0.0, false, false, 4, nil)
	check(registered.zbc_optics ~= nil, "registers Shader Bus lane 'zbc_optics'")
	check(#calls == 1 and calls[1].tok == "tok_zbc_optics", "first update sends to Shader Bus")
	check(calls[1].x == 0 and calls[1].y == 0 and calls[1].z == 0 and calls[1].w == 0, "inactive update sends (0,0,0,0)")

	-- Repeated identical updates are suppressed by change-threshold cache
	for _ = 1, 10 do
		opt.update(0.05, 0.0, 0.0, false, false, 4, nil)
	end
	check(#calls == 1, "identical frames do not spam shader_bus.set (" .. #calls .. " calls)")

	-- Gunshot triggers a new send
	opt.on_gunshot(1.0, 4, nil)
	opt.update(0.01, 1.0, 0.0, false, false, 4, nil)
	check(#calls == 2 and calls[2].x > 0.4 and calls[2].y > 0.2, "active blowout + dark chroma sends new values")

	-- Master disabled forces (0,0,0,0) send
	local x, y, z, w = opt.update(0.05, 1.0, 1.0, false, true, 1, { enabled = false })
	check(x == 0 and y == 0 and z == 0 and w == 0, "enabled=false outputs (0,0,0,0)")
	check(#calls == 3 and calls[3].x == 0 and calls[3].y == 0 and calls[3].z == 0 and calls[3].w == 0, "enabled=false zeroes Shader Bus")
end

---------------------------------------------------------------------------------------------------
-- 7. Static shader verification (SM5 safety, bus_zbc_optics guards, no extra SampleLevel taps)
---------------------------------------------------------------------------------------------------
do
	local lens = read("gamedata/shaders/r3/zbc_lens.h")
	check(lens:find("uniform float4 bus_zbc_optics;", 1, true) ~= nil, "zbc_lens.h declares uniform float4 bus_zbc_optics")
	check(lens:find("bus_zbc_optics%.x > 0%.001") ~= nil, "blowout guarded by bus_zbc_optics.x > 0.001")
	check(lens:find("bus_zbc_optics%.y > 0%.001") ~= nil, "chroma guarded by bus_zbc_optics.y > 0.001")
	check(lens:find("bus_zbc_optics%.z > 0%.001") ~= nil, "condensation guarded by bus_zbc_optics.z > 0.001")
	check(lens:find("bus_zbc_optics%.w > 0%.001") ~= nil, "lens crack guarded by bus_zbc_optics.w > 0.001")
	check(lens:find("zbc_tstep%(24%.0%)") ~= nil, "chroma noise uses wrapped zbc_tstep() clock, not raw timers.x")

	local _, taps = lens:gsub("SampleLevel", "")
	check(taps == 9, "zbc_lens.h keeps exact 9 SampleLevel taps (" .. taps .. ")")

	for _, path in ipairs({ "gamedata/shaders/r3/postprocess.ps", "gamedata/shaders/r3/postprocess_cm.ps" }) do
		local src = read(path)
		check(src:find("zbc_optics_uv", 1, true) ~= nil, path .. " calls zbc_optics_uv")
		check(src:find("zbc_optics_pass", 1, true) ~= nil, path .. " calls zbc_optics_pass")
		check(src:find("zbc_osd_composite") > src:find("zbc_optics_pass"), path .. " draws OSD on top of optical effects")
		check(not src:find("SampleLevel"), path .. " adds zero SampleLevel taps")
	end
end

if failures == 0 then
	print("ALL PASSED (zbc_optics_test)")
	os.exit(0)
else
	print("FAILED: " .. failures .. " checks")
	os.exit(1)
end
