-- Tests the device name on the overlay (zbc_bodycam.script pick_device_label / effective_device_label):
-- by default it is the real model name of the carried Axon Body camera (zbc_item.active_device_label) and
-- follows the camera; the MCM device name replaces it only with the "custom device name" toggle on, which
-- is off by default (so a save that never touched the setting gets the real name).
--
-- Usage (from the repo root): lua tools/tests/zbc_device_label_test.lua

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
	return (s:gsub("\r\n", "\n"))
end

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

local B = load_script("gamedata/scripts/zbc_bodycam.script")
local I = load_script("optional/bodycam_item/gamedata/scripts/zbc_item.script")
local pick = rawget(B, "pick_device_label")
check(type(pick) == "function", "pick_device_label exists")

local defaults = rawget(B, "defaults")
check(defaults.custom_device_label == false, "custom device name is off by default")
check(defaults.device_label == "AXON BODY 4", "without a camera item the overlay reads AXON BODY 4")

-- the real model names, one per camera section (docs/real_specs.md)
local REAL = { zbc_bodycam_1 = "AXON BODY", zbc_bodycam_2 = "AXON BODY 2", zbc_bodycam_3 = "AXON BODY 3",
	zbc_bodycam_item = "AXON BODY 4", zbc_bodycam_5 = "AXON BODY 5" }
for sec, name in pairs(REAL) do
	check(I.CAMERAS[sec] and I.CAMERAS[sec].label == name, sec .. " is labelled " .. name)
	-- toggle off: the carried camera's name wins over any MCM text, old customised saves included
	check(pick(false, "MY CAM", name, "AXON BODY 4") == name, sec .. ": auto name with the toggle off")
	check(pick(nil, "MY CAM", name, "AXON BODY 4") == name, sec .. ": auto name when the toggle was never set")
	-- toggle on: the custom text wins
	check(pick(true, "MY CAM", name, "AXON BODY 4") == "MY CAM", sec .. ": custom name with the toggle on")
end
check(pick(true, "   ", "AXON BODY 2", "AXON BODY 4") == "AXON BODY 2", "blank custom text falls back to the auto name")
check(pick(true, nil, "AXON BODY 2", "AXON BODY 4") == "AXON BODY 2", "missing custom text falls back to the auto name")
check(pick(false, "MY CAM", nil, "AXON BODY 4") == "AXON BODY 4", "no camera item: the default name")
check(pick(true, "MY CAM", nil, "AXON BODY 4") == "MY CAM", "no camera item, toggle on: the custom name")
check(pick(false, "AXON BODY 4", "", "AXON BODY 4") == "AXON BODY 4", "empty auto label: the default name")

-- effective_device_label follows the registered camera source as it changes
do
	local cur = "AXON BODY 2"
	B.set_device_source(function() return cur end)
	check(B.effective_device_label() == "AXON BODY 2", "overlay shows the carried camera")
	cur = "AXON BODY 5"
	check(B.effective_device_label() == "AXON BODY 5", "overlay switches with the camera")
	B.set_device_source(function() error("boom") end)
	check(B.effective_device_label() == "AXON BODY 4", "a failing source falls back to the default name")
	B.set_device_source(nil)
end

-- wiring: the MCM has the toggle before the text, and effective_device_label passes the toggle
do
	local mcm = read("gamedata/scripts/zbc_bodycam_mcm.script")
	local a = mcm:find('id = "custom_device_label", type = "check"', 1, true)
	local b = mcm:find('id = "device_label",', 1, true)
	check(a and b and a < b, "MCM: custom device name toggle right before the device name field")
	local src = read("gamedata/scripts/zbc_bodycam.script")
	check(src:find("pick_device_label(cfg.custom_device_label, cfg.device_label, auto, defaults.device_label)", 1, true),
		"effective_device_label uses the toggle")
	for _, lang in ipairs({ "eng", "rus" }) do
		local s = read("gamedata/configs/text/" .. lang .. "/ui_st_zbc_bodycam.xml")
		check(s:find('"ui_mcm_zone_bodycam_custom_device_label"', 1, true) and s:find('"ui_mcm_zone_bodycam_custom_device_label_desc"', 1, true),
			lang .. ": custom device name strings")
	end
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_device_label_test: all checks passed")
