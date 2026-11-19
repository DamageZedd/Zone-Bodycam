-- Regression test: modded exes older than 2026.10.11 (no Shader Bus 7) crash on start with
-- "R_constant_table::parse: unexpected shader variable type" when a shader declares a uint constant.
-- Runs a minimal C preprocessor over the post-process shaders (and the headers they include from
-- this repo) and checks that no uint constant survives without SHADER_BUS >= 7, while the overlay
-- constants are still there with it.
--
-- Usage (from the repo root): lua tools/tests/shader_uint_guard_test.lua

local DIR = "gamedata/shaders/r3/"
local ROOTS = { "postprocess.ps", "postprocess_cm.ps" }

local function read(path)
	local f = io.open(path, "rb")
	if not f then return nil end
	local s = f:read("*a")
	f:close()
	return (s:gsub("\r\n", "\n"))
end

-- evaluates the #if expressions these shaders use: defined(X), X >= N, &&, ||, !, 0/1
local function eval_if(expr, defs)
	expr = expr:gsub("//.*$", "")
	local function atom(a)
		a = a:gsub("^%s+", ""):gsub("%s+$", "")
		local neg = false
		while a:sub(1, 1) == "!" do neg = not neg; a = a:sub(2):gsub("^%s+", "") end
		local v
		local name = a:match("^defined%s*%(%s*([%w_]+)%s*%)$") or a:match("^defined%s+([%w_]+)$")
		if name then
			v = defs[name] ~= nil
		else
			local lhs, op, rhs = a:match("^([%w_]+)%s*([<>=!]=?)%s*([%w_]+)$")
			if lhs then
				local l = tonumber(lhs) or tonumber(defs[lhs]) or 0
				local r = tonumber(rhs) or tonumber(defs[rhs]) or 0
				if op == ">=" then v = l >= r elseif op == "<=" then v = l <= r
				elseif op == ">" then v = l > r elseif op == "<" then v = l < r
				elseif op == "==" then v = l == r elseif op == "!=" then v = l ~= r
				else error("unsupported operator " .. op) end
			elseif tonumber(a) then
				v = tonumber(a) ~= 0
			elseif a:match("^[%w_]+$") then
				v = (tonumber(defs[a]) or 0) ~= 0
			else
				error("unsupported #if expression: " .. a)
			end
		end
		if neg then return not v end
		return v
	end
	for alt in (expr .. "||"):gmatch("(.-)||") do
		local all = true
		for term in (alt .. "&&"):gmatch("(.-)&&") do
			if not atom(term) then all = false break end
		end
		if all then return true end
	end
	return false
end

-- returns the active source lines of a file and the repo headers it includes
local function preprocess(file, defs, out, seen)
	out, seen = out or {}, seen or {}
	if seen[file] then return out end
	seen[file] = true
	local src = read(DIR .. file)
	if not src then return out end   -- engine headers (common.h, hdr10.h) are not in this repo
	local stack = {}                 -- { active, taken, parent }
	local function active()
		local top = stack[#stack]
		return top == nil or top.active
	end
	for line in (src .. "\n"):gmatch("(.-)\n") do
		local d, rest = line:match("^%s*#%s*(%a+)%s*(.-)%s*$")
		if d == "ifdef" or d == "ifndef" then
			local name = rest:match("^([%w_]+)")
			local cond = (defs[name] ~= nil) == (d == "ifdef")
			local p = active()
			stack[#stack + 1] = { active = p and cond, taken = cond, parent = p }
		elseif d == "if" then
			local p = active()
			local cond = p and eval_if(rest, defs)
			stack[#stack + 1] = { active = cond, taken = cond, parent = p }
		elseif d == "elif" then
			local t = assert(stack[#stack], "#elif without #if in " .. file)
			local cond = t.parent and not t.taken and eval_if(rest, defs)
			t.active = cond
			t.taken = t.taken or cond
		elseif d == "else" then
			local t = assert(stack[#stack], "#else without #if in " .. file)
			t.active = t.parent and not t.taken
			t.taken = true
		elseif d == "endif" then
			assert(stack[#stack], "#endif without #if in " .. file)
			stack[#stack] = nil
		elseif not active() then
			-- skipped
		elseif d == "define" then
			local name, value = rest:match("^([%w_]+)%s*(.-)$")
			defs[name] = value
		elseif d == "include" then
			preprocess(rest:match('^"([^"]+)"'), defs, out, seen)
		elseif not d then
			out[#out + 1] = { file = file, text = line }
		end
	end
	assert(#stack == 0, "unbalanced #if in " .. file)
	return out
end

local function uint_constants(defs)
	local found = {}
	for _, root in ipairs(ROOTS) do
		for _, l in ipairs(preprocess(root, defs)) do
			local code = l.text:gsub("//.*$", "")
			-- global constants start at column 0; locals inside functions are indented
			local name = code:match("^uniform%s+uint%d?x?%d?%s+([%w_]+)") or code:match("^uint%d?x?%d?%s+([%w_]+)%s*[%[;]")
			if name then found[#found + 1] = l.file .. ": " .. name end
		end
	end
	return found
end

local failures = 0
local function check(ok, msg)
	print((ok and "PASS " or "FAIL ") .. msg)
	if not ok then failures = failures + 1 end
end

local old = uint_constants({})
check(#old == 0, "no uint constants without SHADER_BUS (old exes): " .. (#old == 0 and "none" or table.concat(old, ", ")))

local v6 = uint_constants({ SHADER_BUS = "6" })
check(#v6 == 0, "no uint constants with SHADER_BUS 6: " .. (#v6 == 0 and "none" or table.concat(v6, ", ")))

local v7 = uint_constants({ SHADER_BUS = "7" })
check(#v7 > 0, "overlay uint constants present with SHADER_BUS 7: " .. #v7 .. " found")

os.exit(failures == 0 and 0 or 1)
