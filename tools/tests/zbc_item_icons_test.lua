-- Tests the bodycam item inventory icons:
--  * default (optional/bodycam_item): every camera is 1x1, each in its own 50x50 cell of the 256x64 atlas;
--  * HD option (optional/bodycam_item_hd_icons, for HD Inventory Icons Framework): a DLTX patch for exactly the
--    camera sections, 2x2-cell (100x100) icons from the 512x128 atlas at inv_grid_scale 2 = one 1x1 slot;
--  * FOMOD: the camera items are preselected (Recommended), the icon step only shows with them, standard 1x1
--    icons are the default and the HD option installs the HD folder.
--
-- Usage (from the repo root): lua tools/tests/zbc_item_icons_test.lua

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
		local name = line:match("^%s*!?%[([^%]:]+)%]")
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

local ITEMS    = "optional/bodycam_item/gamedata/configs/items/items/items_zbc_bodycam.ltx"
local ATLAS    = "optional/bodycam_item/gamedata/textures/ui/ui_icon_zbc_bodycam.dds"
local HD_PATCH = "optional/bodycam_item_hd_icons/gamedata/configs/mod_system_zbc_bodycam_hd_icons.ltx"
local HD_ATLAS = "optional/bodycam_item_hd_icons/gamedata/textures/ui/ui_icon_zbc_bodycam_hd.dds"

-- camera -> atlas column, same order in both atlases (make_item_textures.py ATLAS_SLOTS / ATLAS_1X1_X)
local COLS = { zbc_bodycam_item = 0, zbc_bodycam_1 = 1, zbc_bodycam_2 = 2, zbc_bodycam_3 = 3, zbc_bodycam_5 = 4 }

-- an item key, from the section or the parent [zbc_bodycam_item]
local items = parse_ltx(read(ITEMS))
local function item_key(name, key)
	local s = items[name]
	if s and s[key] ~= nil then return s[key] end
	return items.zbc_bodycam_item and items.zbc_bodycam_item[key]
end

-- every camera section (not the *_anim_hud ones) is known to the test
for name in pairs(items) do
	if not name:match("_anim_hud$") then
		check(COLS[name] ~= nil, "test knows item section " .. name)
	end
end

-- default: 1x1, own cell
for name, col in pairs(COLS) do
	check(items[name] ~= nil, name .. " exists in the item config")
	check(item_key(name, "icons_texture") == "ui\\ui_icon_zbc_bodycam", name .. " icons_texture")
	check(item_key(name, "inv_grid_width") == "1" and item_key(name, "inv_grid_height") == "1", name .. " is 1x1 by default")
	check(tonumber(item_key(name, "inv_grid_x")) == col, name .. " inv_grid_x = " .. col .. ", got " .. tostring(item_key(name, "inv_grid_x")))
	check(tonumber(item_key(name, "inv_grid_y")) == 0, name .. " inv_grid_y = 0")
	check(item_key(name, "inv_grid_scale") == nil, name .. " has no inv_grid_scale by default")
end

-- HD option: patch covers exactly the camera sections, every key on every section
local hd_text = read(HD_PATCH)
local hd, hd_order = parse_ltx(hd_text)
check(#hd_order == 5, "HD patch has 5 sections, got " .. #hd_order)
for name, col in pairs(COLS) do
	check(hd_text:find("![" .. name .. "]", 1, true) ~= nil, "HD patch overrides [" .. name .. "] with DLTX ![...]")
	local p = hd[name]
	if p then
		check(p.icons_texture == "ui\\ui_icon_zbc_bodycam_hd", name .. " HD icons_texture")
		check(p.inv_grid_width == "2" and p.inv_grid_height == "2", name .. " HD icon is 2x2 cells")
		check(p.inv_grid_scale == "2", name .. " HD inv_grid_scale = 2 (one 1x1 slot)")
		check(tonumber(p.inv_grid_x) == col * 2, name .. " HD inv_grid_x = " .. col * 2 .. ", got " .. tostring(p.inv_grid_x))
		check(tonumber(p.inv_grid_y) == 0, name .. " HD inv_grid_y = 0")
	end
end
for name in pairs(hd) do
	check(COLS[name] ~= nil, "HD patch only touches camera sections, found " .. name)
end

-- atlases: uncompressed 32-bit BGRA DDS, a camera in every cell, nothing outside the cells
local function u32(s, i)
	local a, b, c, d = s:byte(i, i + 3)
	return a + b * 256 + c * 65536 + d * 16777216
end
local function check_atlas(path, want_w, want_h, cell)
	local dds = read(path)
	check(dds:sub(1, 4) == "DDS ", path .. " is a DDS")
	local H, W = u32(dds, 13), u32(dds, 17)
	check(W == want_w and H == want_h, path .. " is " .. want_w .. "x" .. want_h .. ", got " .. W .. "x" .. H)
	check(u32(dds, 85) == 0, path .. " is uncompressed (no fourCC)")
	check(u32(dds, 89) == 32, path .. " is 32 bits per pixel")
	check(u32(dds, 105) == 0xFF000000, path .. " alpha mask is the top byte")
	if W ~= want_w or H ~= want_h or #dds < 128 + W * H * 4 then
		check(false, path .. " pixel data is missing")
		return
	end
	local function alpha(x, y) return dds:byte(128 + (y * W + x) * 4 + 4) end
	for name, col in pairs(COLS) do
		local opaque, x0 = 0, col * cell
		for y = 0, cell - 1 do
			for x = x0, x0 + cell - 1 do
				if alpha(x, y) > 128 then opaque = opaque + 1 end
			end
		end
		check(opaque > cell * cell * 0.2, path .. ": " .. name .. " cell has a camera (" .. opaque .. " opaque px)")
	end
	local stray = 0
	for y = 0, H - 1 do
		for x = 0, W - 1 do
			if (x >= 5 * cell or y >= cell) and alpha(x, y) ~= 0 then stray = stray + 1 end
		end
	end
	check(stray == 0, path .. ": nothing outside the 5 cells, got " .. stray .. " px")
end
check_atlas(ATLAS, 256, 64, 50)
check_atlas(HD_ATLAS, 512, 128, 100)

-- FOMOD defaults
local fomod = read("fomod/ModuleConfig.xml")
local function plugin(name)
	return fomod:match('<plugin name="' .. name:gsub("%p", "%%%0") .. '">(.-)</plugin>')
end
local item = plugin("Bodycam item (battery powered)")
check(item ~= nil, "FOMOD has the bodycam item plugin")
if item then
	check(item:find('source="optional\\bodycam_item\\gamedata"', 1, true) ~= nil, "item plugin installs optional/bodycam_item")
	check(item:find('<type name="Recommended" />', 1, true) ~= nil, "camera items are on by default (Recommended)")
	check(item:find('<flag name="zbc_bodycam_item">On</flag>', 1, true) ~= nil, "item plugin sets the zbc_bodycam_item flag")
end
local step = fomod:match('<installStep name="Bodycam item icons">(.-)</installStep>')
check(step ~= nil, "FOMOD has the icon step")
if step then
	check(step:find('<flagDependency flag="zbc_bodycam_item" value="On" />', 1, true) ~= nil, "icon step only shows with the camera items")
	check(step:find('type="SelectExactlyOne"', 1, true) ~= nil, "icon step picks exactly one")
end
local std = plugin("Standard icons (1x1)")
check(std ~= nil, "FOMOD has the standard icon plugin")
if std then
	check(std:find('<type name="Recommended" />', 1, true) ~= nil, "standard 1x1 icons are the default")
	check(std:find("<files>", 1, true) == nil, "standard icons install nothing extra (1x1 is the base config)")
end
local hdp = plugin("HD icons (HD Inventory Icons Framework)")
check(hdp ~= nil, "FOMOD has the HD icon plugin")
if hdp then
	check(hdp:find('source="optional\\bodycam_item_hd_icons\\gamedata"', 1, true) ~= nil, "HD plugin installs optional/bodycam_item_hd_icons")
	check(hdp:find('<type name="Optional" />', 1, true) ~= nil, "HD icons are opt-in")
end
check(fomod:find("bodycam_item_icons_1x1", 1, true) == nil, "no leftover 1x1 option folder in the FOMOD")

if failures == 0 then
	print("zbc_item_icons_test: all passed")
else
	print("zbc_item_icons_test: " .. failures .. " failure(s)")
	os.exit(1)
end
