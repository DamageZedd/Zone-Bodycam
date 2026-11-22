-- Tests the pure logic of the event log, footage review, companion edge markers, random decode order,
-- face prediction and auto-exposure.
--
-- Usage (from the repo root): lua tools/tests/zbc_round3_test.lua

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end
local function load(path)
	local env = setmetatable({}, { __index = _G })
	local c = assert(loadfile(path))
	setfenv(c, env)
	check(pcall(c), path .. " loads")
	return env
end

-- random decode order: a full shuffle, the same for the same NPC, every letter still locks
local al = load("gamedata/scripts/zbc_allies.script")
local r = al.lock_ranks(10, 4211)
local seen = {}
for i = 1, 10 do seen[r[i]] = true end
local all = true
for k = 0, 9 do all = all and seen[k] end
check(all, "random order: each letter gets its own turn")
check(al.lock_ranks(10, 4211) == r, "same NPC, same order")
local t_end = al.DECODE_DELAY + 10 * al.DECODE_STEP
check(al.decode_text("ABCDEFGHIJ", t_end, 4211, 0, true) == "ABCDEFGHIJ", "random order still finishes on time")

-- companion edge markers: on the screen border, toward the companion
local ex, ey = al.edge_ui(1, 0, 1)
check(ex > 900 and math.abs(ey - 384) < 1, "to the right: right edge")
ex, ey = al.edge_ui(0, 1, 1)
check(ey < 100 and math.abs(ex - 512) < 1, "above: top edge")
ex, ey = al.edge_ui(0.2, 0, -1)
check(ey > 600, "behind you: slides to the bottom edge")

-- face prediction: one step ahead, but not across a jump
local fa = load("gamedata/scripts/zbc_faces.script")
local pu, pv = fa.predict({ 0.50, 0.40 }, 0.52, 0.41)
check(math.abs(pu - 0.54) < 1e-9 and math.abs(pv - 0.42) < 1e-9, "carries the last step forward")
pu, pv = fa.predict({ 0.10, 0.40 }, 0.60, 0.41)
check(pu == 0.60 and pv == 0.41, "a jump is not extrapolated")
pu = fa.predict(nil, 0.3, 0.3)
check(pu == 0.3, "no history: unchanged")

-- auto-exposure: brighter where it is dark, settles on the target with a small overshoot
local fx = load("gamedata/scripts/zbc_fx.script")
check(fx.exposure_target(0.05) > fx.exposure_target(0.9), "dark spots get more gain")
check(fx.exposure_target(0) <= fx.EXP_MAX and fx.exposure_target(1) >= fx.EXP_MIN, "gain stays in range")
local g, v, peak = 0.75, 0, 0
local target = fx.exposure_target(0.05)
for _ = 1, 300 do
	g, v = fx.exposure_step(g, v, target, 1 / 60)
	peak = math.max(peak, g)
end
check(math.abs(g - target) < 0.02, "settles on the target")
check(peak > target, "overshoots a little on the way (hunting)")

-- event log: overlay lines are the newest shown events, oldest first; gaps throttle repeats
local ev = load("gamedata/scripts/zbc_eventlog.script")
ev.add("shots", "SHOTS FIRED", true, 100, "12:00", 10)
ev.add("ident", "IDENTIFIED X", false, 101, "12:00", 11)
ev.add("contact", "CONTACT 2", true, 102, "12:01", 12)
local lines = ev.recent(103, 3)
check(#lines == 2 and lines[1] == "12:00 SHOTS FIRED" and lines[2] == "12:01 CONTACT 2", "shown events, oldest first; review-only ones hidden")
check(#ev.recent(100 + ev.SHOW_SECONDS + 5, 3) == 0, "old lines leave the overlay")
check(not ev.due("shots", ev.SHOTS_GAP, 102) and ev.due("shots", ev.SHOTS_GAP, 105), "a burst is one SHOTS FIRED")
check(#ev.history == 3, "everything kept for the review screen")

-- footage review layout (the window class needs the game's luabind "class"; stand-ins here)
local rv = setmetatable({}, { __index = _G })
rv.CUIScriptWnd = {}
rv.class = function(name)
	return function() rv[name] = setmetatable({}, { __call = function(t) return setmetatable({}, { __index = t }) end }) end
end
do
	local c = assert(loadfile("gamedata/scripts/zbc_review.script"))
	setfenv(c, rv)
	check(pcall(c), "zbc_review.script loads")
end
check(rv.rec_clock(3725) == "01:02:05", "recorded time as hh:mm:ss")
check(rv.timeline_x(50, 0, 100, 100, 300) == 200 and rv.timeline_x(500, 0, 100, 100, 300) == 300, "timeline position, clamped")
check(rv.list_start(1, 30, 9) == 1 and rv.list_start(30, 30, 9) == 22 and rv.list_start(15, 30, 9) == 11, "the list keeps the selection in view")

-- footage review toggle & same-keypress debounce + Delete (211) default keybind
do
	local bc
	bc = setmetatable({
		CUIScriptWnd = {},
		class = function(name) return function() bc[name] = {} end end,
	}, { __index = _G })
	local bc_chunk = assert(loadfile("gamedata/scripts/zbc_bodycam.script"))
	setfenv(bc_chunk, bc)
	check(pcall(bc_chunk), "zbc_bodycam.script loads for review_key check")
	check(bc.defaults and bc.defaults.review_key == 211, "default footage review key is Delete (211)")

	local now_ms, shown, reg_n, unreg_n = 1000, false, 0, 0
	local function mk_ctrl()
		local c = {}
		local tc = { SetText = function() end, SetTextColor = function() end }
		return setmetatable(c, { __index = {
			SetWndPos = function() end, SetWndSize = function() end, SetTextureColor = function() end,
			Show = function() end, TextControl = function() return tc end,
		} })
	end
	local env = setmetatable({
		time_global = function() return now_ms end,
		Frect = function() return { set = function(s) return s end } end,
		vector2 = function() return { set = function(s) return s end } end,
		GetARGB = function() return 0 end,
		CScriptXmlInit = function()
			return { ParseFile = function() end, InitStatic = function() return mk_ctrl() end }
		end,
		DIK_keys = { DIK_ESCAPE = 1, DIK_LEFT = 203, DIK_RIGHT = 205, DIK_UP = 200, DIK_DOWN = 208, DIK_A = 30, DIK_D = 32, DIK_W = 17, DIK_S = 31, DIK_HOME = 199, DIK_END = 207 },
		ui_events = { WINDOW_KEY_PRESSED = 1 },
		zbc_bodycam = { review_key_now = function() return 211 end, rec_seconds = function() return 42 end },
		zbc_eventlog = { HISTORY_MAX = 8, history = {} },
		Register_UI = function() reg_n = reg_n + 1 end,
		Unregister_UI = function() unreg_n = unreg_n + 1 end,
		CUIScriptWnd = { OnKeyboard = function() return false end },
		super = function() end,
	}, { __index = _G })
	env.class = function(name)
		return function()
			local cls = {}
			cls.__index = cls
			function cls:SetWndRect() end
			function cls:SetAutoDelete() end
			function cls:ShowDialog() shown = true end
			function cls:HideDialog() shown = false end
			function cls:Show(v) if not v then shown = false end end
			function cls:IsShown() return shown end
			env[name] = setmetatable(cls, {
				__call = function(t)
					local o = setmetatable({}, t)
					o:__init()
					return o
				end,
			})
		end
	end
	local rc = assert(loadfile("gamedata/scripts/zbc_review.script"))
	setfenv(rc, env)
	rc()

	env.toggle()
	check(env.is_open() and reg_n == 1, "toggle() opens review dialog and calls Register_UI")
	-- same-keypress OnKeyboard(211) right after opening must NOT self-close
	local inst = env.ZbcReview()
	inst.opened_at = 1000
	inst:OnKeyboard(211, 1)
	check(env.is_open(), "same-keypress OnKeyboard(review_key) does not immediately self-close")
	-- pressing review_key after debounce closes it cleanly
	now_ms = 1200
	env.toggle()
	check(not env.is_open() and unreg_n == 1, "toggle() after debounce closes review dialog and calls Unregister_UI")
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_round3_test: all checks passed")
