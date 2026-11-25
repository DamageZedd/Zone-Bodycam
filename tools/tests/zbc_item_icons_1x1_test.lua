-- Tests the optional 1x1 inventory icons (optional/bodycam_item_icons_1x1): the DLTX patch covers exactly the
-- camera sections of items_zbc_bodycam.ltx, each points at its own 50x50 cell of the 256x64 atlas, the atlas
-- has a camera in every cell and nothing outside them, and the FOMOD installs it only with the item component.
--
-- Usage (from the repo root): lua tools/tests/zbc_item_icons_1x1_test.lua

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

-- { section = { key = value } }, in file order; "![name]" (DLTX override) and "[name]:parent" both count
local function parse_ltx(s)
	local sections, order, cur = {}, {}, nil
	for line in (s .. "\n"):gmatch("([^\n]*)\n") do
		line = line:gsub("\r$", ""):gsub(";.*$", "")
		local name = line:match("^%s*!?%[([^%]]+)%]")
		if name then
			cur = {}
			sections[name] = cur
			order[#order + 1] = name
		elseif cur then
			local k, v = line:match("^%s*([%w_$]+)%s*=%s*(.-)%s*$")
			if k then cur[k] = v end
		end
	end
	return sections, order
end

local ITEMS = "optional/bodycam_item/gamedata/configs/items/items/items_zbc_bodycam.ltx"
local PATCH = "optional/bodycam_item_icons_1x1/gamedata/configs/mod_system_zbc_bodycam_icons_1x1.ltx"
local ATLAS = "optional/bodycam_item_icons_1x1/gamedata/textures/ui/ui_icon_zbc_bodycam_1x1.dds"

-- camera -> cell column, same camera order as the 2x2 atlas (make_item_textures.py ATLAS_1X1_X)
local CELLS = { zbc_bodycam_item = 0, zbc_bodycam_1 = 1, zbc_bodycam_2 = 2, zbc_bodycam_3 = 3, zbc_bodycam_5 = 4 }

-- the patch covers exactly the camera sections (not the *_anim_hud ones) of the item config
local items = parse_ltx(read(ITEMS))
local patch, patch_order = parse_ltx(read(PATCH))
check(read(PATCH):find("![zbc_bodycam_item]", 1, true) ~= nil, "patch uses DLTX ![section] overrides")
for name in pairs(items) do
	if not name:match("_anim_hud$") then
		check(patch[name] ~= nil, "patch covers item section " .. name)
		check(CELLS[name] ~= nil, "test knows item section " .. name)
	end
end
check(#patch_order == 5, "patch has 5 sections, got " .. #patch_order)
for name, col in pairs(CELLS) do
	local p = patch[name]
	check(items[name] ~= nil, name .. " exists in the item config")
	check(p ~= nil, name .. " is in the patch")
	if p then
		check(p.icons_texture == "ui\\ui_icon_zbc_bodycam_1x1", name .. " icons_texture")
		check(p.inv_grid_width == "1" and p.inv_grid_height == "1", name .. " is 1x1")
		check(tonumber(p.inv_grid_x) == col, name .. " inv_grid_x = " .. col .. ", got " .. tostring(p.inv_grid_x))
		check(tonumber(p.inv_grid_y) == 0, name .. " inv_grid_y = 0")
	end
end
-- cells are unique
do
	local seen = {}
	for name, p in pairs(patch) do
		local key = tostring(p.inv_grid_x) .. "," .. tostring(p.inv_grid_y)
		check(not seen[key], name .. " shares cell " .. key .. " with " .. tostring(seen[key]))
		seen[key] = name
	end
end

-- atlas: uncompressed 32-bit BGRA DDS, 256x64, alpha in every camera cell, empty outside 5 x 50x50 cells
local function u32(s, i)
	local a, b, c, d = s:byte(i, i + 3)
	return a + b * 256 + c * 65536 + d * 16777216
end
local dds = read(ATLAS)
check(dds:sub(1, 4) == "DDS ", "atlas is a DDS")
local H, W = u32(dds, 13), u32(dds, 17)
check(W == 256 and H == 64, "atlas is 256x64, got " .. W .. "x" .. H)
check(u32(dds, 85) == 0, "atlas is uncompressed (no fourCC)")
check(u32(dds, 89) == 32, "atlas is 32 bits per pixel")
check(u32(dds, 105) == 0xFF000000, "alpha mask is the top byte")
local function alpha(x, y) return dds:byte(128 + (y * W + x) * 4 + 4) end
if W == 256 and H == 64 and #dds >= 128 + W * H * 4 then
	for name, col in pairs(CELLS) do
		local opaque, x0 = 0, col * 50
		for y = 0, 49 do
			for x = x0, x0 + 49 do
				if alpha(x, y) > 128 then opaque = opaque + 1 end
			end
		end
		-- a camera fills most of its cell (Row B: 46 px on the long side)
		check(opaque > 50 * 50 * 0.4, name .. " cell has a camera (" .. opaque .. " opaque px)")
	end
	local stray = 0
	for y = 0, H - 1 do
		for x = 0, W - 1 do
			if (x >= 250 or y >= 50) and alpha(x, y) ~= 0 then stray = stray + 1 end
		end
	end
	check(stray == 0, "nothing outside the 5 cells, got " .. stray .. " px")
else
	check(false, "atlas pixel data is missing")
end

-- FOMOD: the 1x1 step installs the component and is only shown with the bodycam item
local fomod = read("fomod/ModuleConfig.xml")
check(fomod:find('source="optional\\bodycam_item_icons_1x1\\gamedata"', 1, true) ~= nil, "FOMOD installs the 1x1 component")
check(fomod:find('<flag name="zbc_bodycam_item">On</flag>', 1, true) ~= nil, "item plugin sets the flag")
check(fomod:find('<flagDependency flag="zbc_bodycam_item" value="On" />', 1, true) ~= nil, "1x1 step needs the item")

if failures == 0 then
	print("zbc_item_icons_1x1_test: all passed")
else
	print("zbc_item_icons_1x1_test: " .. failures .. " failure(s)")
	os.exit(1)
end
