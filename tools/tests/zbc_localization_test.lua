-- Tests the Russian localization: every English string has a Russian one (main mod and the optional
-- item), every MCM list option has its ui_mcm_lst_ string in both languages, the Russian files are
-- Windows-1251, the overlay font has every Russian letter, and the shader atlas rows fit the array.
--
-- Usage (from the repo root): lua tools/tests/zbc_localization_test.lua

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end

local function read(path)
	local f = io.open(path, "rb")
	if not f then return nil end
	local s = f:read("*a")
	f:close()
	return s
end

local function ids(path)
	local s = read(path)
	check(s ~= nil, "file exists: " .. path)
	local t, n = {}, 0
	if s then
		for id in s:gmatch('<string id="([^"]+)">') do t[id] = true; n = n + 1 end
	end
	return t, n, s
end

local function same_ids(eng, rus, what)
	local e, ne = ids(eng)
	local r, nr, rs = ids(rus)
	for id in pairs(e) do check(r[id], what .. ": Russian is missing " .. id) end
	for id in pairs(r) do check(e[id], what .. ": Russian has an id English lacks: " .. id) end
	check(ne > 0 and ne == nr, ("%s: %d English strings, %d Russian"):format(what, ne, nr))
	if rs then
		check(rs:find('encoding="windows%-1251"') ~= nil, what .. ": Russian file declares windows-1251")
		check(rs:find("[\192-\255]") ~= nil, what .. ": Russian file has Cyrillic bytes")
		check(not rs:find("\208[\144-\191]"), what .. ": Russian file is not UTF-8")
		for body in rs:gmatch("<text>(.-)</text>") do check(#body > 0, what .. ": empty text") end
	end
	return e
end

local main_eng = same_ids("gamedata/configs/text/eng/ui_st_zbc_bodycam.xml",
	"gamedata/configs/text/rus/ui_st_zbc_bodycam.xml", "main")
same_ids("optional/bodycam_item/gamedata/configs/text/eng/ui_st_zbc_bodycam_item.xml",
	"optional/bodycam_item/gamedata/configs/text/rus/ui_st_zbc_bodycam_item.xml", "item")

-- MCM list options are string keys now (no no_str), each with a ui_mcm_lst_ string
local mcm = read("gamedata/scripts/zbc_bodycam_mcm.script") or ""
check(not mcm:find("no_str"), "no MCM list shows untranslated text (no_str)")
local keys = 0
for key in mcm:gmatch('{%s*%d+,%s*"(zbc_[%w_]+)"%s*}') do
	keys = keys + 1
	check(main_eng["ui_mcm_lst_" .. key], "list option has an English string: " .. key)
end
check(keys >= 19, "list options found: " .. keys)
for id, kind in mcm:gmatch('{ id = "([%w_]+)",%s*type = "(%w+)"') do
	if kind ~= "line" and kind ~= "title" then       -- dividers and the title text need no label
		check(main_eng["ui_mcm_zone_bodycam_" .. id], "MCM option has a label: " .. id)
	end
end

-- every mutant class the markers know has a display name in both languages
do
	local aenv = setmetatable({}, { __index = _G })
	local ac = assert(loadfile("gamedata/scripts/zbc_allies.script"))
	setfenv(ac, aenv)
	ac()
	local kinds = rawget(aenv, "MUTANT_KINDS")
	check(type(kinds) == "table" and #kinds >= 18, "MUTANT_KINDS listed")
	local rus = ids("gamedata/configs/text/rus/ui_st_zbc_bodycam.xml")
	check(main_eng["st_zbc_mutant"] and rus["st_zbc_mutant"], "the MUTANT label exists in both languages")
	for _, k in ipairs(kinds or {}) do
		check(main_eng["st_zbc_mutant_" .. k], "English name for mutant " .. k)
		check(rus["st_zbc_mutant_" .. k], "Russian name for mutant " .. k)
	end
	local ba = rawget(aenv, "box_aspect")
	check(type(ba) == "function", "box_aspect exists")
	if type(ba) == "function" then
		aenv.IsStalker = function() return false end
		check(ba({}, "pseudodog") > 1 and ba({}, "snork") < 1 and ba({}, nil) < 1, "four-legged mutants get wide boxes")
		aenv.IsStalker = function() return true end
		check(ba({}) == 0.42, "stalkers keep the upright box")
	end
end

-- upper case for Windows-1251 text (zbc_allies.upper_cp1251)
local env = setmetatable({}, { __index = _G })
local chunk = assert(loadfile("gamedata/scripts/zbc_allies.script"))
setfenv(chunk, env)
check(pcall(chunk), "zbc_allies loads")
local up = rawget(env, "upper_cp1251")
check(type(up) == "function", "upper_cp1251 exists")
if type(up) == "function" then
	check(up("vova tramp") == "VOVA TRAMP", "ASCII upper case")
	check(up("\226\238\226\224") == "\194\206\194\192", "Russian lower to upper case")
	check(up("\184\230") == "\168\198", "yo and zhe to upper case")
	check(up("\192\193 AB 12-") == "\192\193 AB 12-", "upper case and other characters unchanged")
	local lower, upper = {}, {}
	for c = 224, 255 do lower[#lower + 1] = string.char(c); upper[#upper + 1] = string.char(c - 32) end
	check(up(table.concat(lower)) == table.concat(upper), "all 32 Russian lower-case letters")
	check(up(nil) == "", "nil is safe")
end

-- the overlay font has every Russian letter
local fenv = {}
local fchunk = assert(loadfile("gamedata/scripts/zbc_font_metrics.script"))
setfenv(fchunk, fenv)
fchunk()
check(type(fenv.index) == "function", "zbc_font_metrics.index exists")
if type(fenv.index) == "function" then
	local seen = {}
	local function cell(code)
		local k = fenv.index(code)
		if k then
			check(not seen[k], "each glyph has its own atlas cell: " .. code)
			seen[k] = true
			local rows = math.floor(fenv.tex_h / fenv.cell_h)
			check(k >= 0 and k < fenv.cols * rows, "cell inside the atlas: " .. code)
		end
		return k
	end
	for c = 33, 126 do check(cell(c) == c - 32, "ASCII cell unchanged: " .. c) end
	check(cell(32) == nil, "space has no glyph")
	check(cell(168) and cell(184), "Yo and yo have glyphs")
	for c = 192, 255 do check(cell(c) ~= nil, "Russian letter has a glyph: " .. c) end
	for _, c in ipairs({ 0, 31, 127, 150, 167, 191 }) do check(fenv.index(c) == nil, "no glyph for " .. c) end
end

-- shader atlas: the Russian rows go after the ASCII glyphs and the logo, inside the array
local function load_rows(path)
	local t = {}
	local c = assert(loadfile(path))
	setfenv(c, t)
	c()
	return t
end
local cyr = load_rows("gamedata/scripts/zbc_osd_atlas_cyr.script")
local ascii = load_rows("gamedata/scripts/zbc_osd_atlas.script")
local osd = read("gamedata/shaders/r3/zbc_osd.h") or ""
local size = tonumber(osd:match("bus_zbc_osd_atlas%[(%d+)%]"))
check(cyr.OFFSET == #ascii.ROWS, ("Russian rows start right after the existing %d"):format(#ascii.ROWS))
check(#cyr.ROWS == 66 * 8, "66 Russian letters x 8 rows")
check(size and cyr.OFFSET + #cyr.ROWS <= size, ("rows fit bus_zbc_osd_atlas[%s]"):format(tostring(size)))
check(osd:find("return 816u;", 1, true) and osd:find("return 824u;", 1, true) and osd:find("832u +", 1, true),
	"shader maps Yo, yo, A..ya to rows 816, 824, 832..")
for i, r in ipairs(cyr.ROWS) do
	for c = 1, 4 do
		local v = r[c]
		check(type(v) == "number" and v >= 0 and v < 4294967296 and v % 1 == 0, "row " .. i .. " holds uint32 values")
	end
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_localization_test: all checks passed")
