-- Tests the ally name label text in gamedata/scripts/zbc_allies.script: upper case like the overlay,
-- trimmed, cut to the label length, and safe on missing names.
--
-- Usage (from the repo root): lua tools/tests/zbc_allies_label_test.lua

local PATH = "gamedata/scripts/zbc_allies.script"

local failures = 0
local function check(cond, msg)
	if not cond then
		failures = failures + 1
		print("FAIL: " .. msg)
	end
end

local env = setmetatable({}, { __index = _G })
local chunk = assert(loadfile(PATH))
setfenv(chunk, env)
local ok, err = pcall(chunk)
check(ok, "script loads: " .. tostring(err))
local lt = rawget(env, "label_text")
check(type(lt) == "function", "label_text exists")

if type(lt) == "function" then
	check(lt("Vova Tramp") == "VOVA TRAMP", "upper case")
	check(lt("  Artyom Favorite \t") == "ARTYOM FAVORITE", "trimmed")
	check(#lt(string.rep("Ab", 40)) == 24, "cut to 24 characters")
	check(lt(nil) == "" and lt(42) == "", "no name: empty label")
	check(lt("") == "", "empty name: empty label")
end

-- decode effect
local dt = rawget(env, "decode_text")
check(type(dt) == "function", "decode_text exists")
if type(dt) == "function" then
	local name = "VOVA TRAMP"
	local s0, done0 = dt(name, 0, 5)
	check(#s0 == #name and not done0, "starts scrambled, same length")
	check(s0:sub(5, 5) == " ", "spaces stay spaces while scrambled")
	check(s0 ~= name, "the start is not the plain name")
	local full = env.DECODE_DELAY + #name * env.DECODE_STEP
	local s1, done1 = dt(name, full, 5)
	check(s1 == name and done1, "fully decoded after the reveal time")
	-- letters lock one after another from the left
	local mid = env.DECODE_DELAY + 3.5 * env.DECODE_STEP
	local sm = dt(name, mid, 5)
	check(sm:sub(1, 4) == "VOVA", "the first letters have locked")
	local prev_locked = 0
	for k = 0, 40 do
		local t = k * 0.01
		local s = dt(name, t, 5)
		local locked = 0
		for i = 1, #name do
			if s:sub(i, i) == name:sub(i, i) and t >= env.DECODE_DELAY + (i - 1) * env.DECODE_STEP then locked = i else break end
		end
		check(locked >= prev_locked, ("t=%.2f: locked letters never go back"):format(t))
		prev_locked = locked
	end
	check(dt("ABC", -1, 1) ~= nil, "negative time (faction delay) is fine")
	check(dt("", 0, 1) == "", "empty text stays empty")
	-- the scramble changes over time and differs per NPC
	check(dt(name, 0.0, 5) ~= dt(name, 0.06, 5), "scramble flickers")
	check(dt(name, 0.0, 5) ~= dt(name, 0.0, 6), "different NPCs scramble differently")
	-- only drawable characters
	for k = 0, 30 do
		local s = dt("XXXXXXXXXXXXXXXXXXXX", k * 0.013, k)
		check(not s:find("[^%w%+=/<>#%%]"), "scramble uses only glyph-atlas characters: " .. s)
	end
	-- lockstep faction decode: shorter or longer faction finishes at the exact same time as name
	local long_name = "ARTYOM FAVORITE"
	local short_fac = "DUTY"
	local total_t = env.DECODE_DELAY + #long_name * env.DECODE_STEP
	local fn0, fd0 = dt(short_fac, 0, 22, nil, false, total_t)
	check(not fd0 and fn0 ~= short_fac, "short faction starts scrambled at t=0")
	local fn_mid, fd_mid = dt(short_fac, env.DECODE_DELAY + 5 * env.DECODE_STEP, 22, nil, false, total_t)
	local nm_mid, nd_mid = dt(long_name, env.DECODE_DELAY + 5 * env.DECODE_STEP, 5, nil, false, total_t)
	check(not fd_mid and not nd_mid, "short faction is still decoding while long name is still decoding")
	local fn_end, fd_end = dt(short_fac, total_t, 22, nil, false, total_t)
	local nm_end, nd_end = dt(long_name, total_t, 5, nil, false, total_t)
	check(fd_end and nd_end and fn_end == short_fac and nm_end == long_name,
		"faction and name finish decoding at the exact same time")
end

-- faction text
local ft = rawget(env, "faction_text")
check(type(ft) == "function", "faction_text exists")
if type(ft) == "function" then
	env.game = { translate_string = function(id) return ({ csky = "Clear Sky", dolg = "Duty" })[id] or id end }
	local function npc(comm) return { character_community = function() return comm end } end
	check(ft(npc("csky")) == "CLEAR SKY", "translated and upper case")
	check(ft(npc("monolith")) == "MONOLITH", "untranslated id falls back to the id")
	check(ft(npc(nil)) == "" and ft(nil) == "", "no community: empty")
	check(#ft(npc(string.rep("x", 50))) == env.FACTION_CHARS, "cut to FACTION_CHARS")
end

-- box colour reveal: white first, then the relation colour once the name has decoded
local rm = rawget(env, "reveal_mix")
check(type(rm) == "function", "reveal_mix exists")
if type(rm) == "function" then
	check(rm(0, 10) == 0, "white when the box appears")
	local name_done = env.DECODE_DELAY + 20 * env.DECODE_STEP
	check(rm(name_done - 0.01, 20) == 0, "still white while a long name decodes")
	check(rm(name_done + env.COLOR_FADE + 0.01, 20) == 1, "full colour after the fade")
	check(rm(env.REVEAL_MIN - 0.01, 1) == 0, "short names still stay white for REVEAL_MIN")
	local prev = 0
	for k = 0, 200 do
		local v = rm(k * 0.01, 12)
		check(v >= prev and v >= 0 and v <= 1, "reveal only moves towards the colour")
		prev = v
	end
	check(rm(nil, nil) == 0, "no timer yet: white")
end

-- identification by distance (after the Identification UI mod)
local ir, rs = rawget(env, "identify_rate"), rawget(env, "reveal_speed")
check(type(ir) == "function" and type(rs) == "function", "identification functions exist")
if type(ir) == "function" and type(rs) == "function" then
	local function near(a, b) return math.abs(a - b) < 1e-6 end
	-- nobody is identified instantly: never faster than ID_MIN_TIME, even up close
	check(env.ID_MIN_TIME >= 1.5, "a minimum identification time")
	check(near(1 / ir(5, 75), env.ID_MIN_TIME) and near(1 / ir(50, 75), env.ID_MIN_TIME), "close up: the minimum time, not instant")
	check(near(1 / ir(60, 10), env.ID_MIN_TIME), "a strong scope can't beat the minimum either")
	-- beyond that, the mod: 100 / ((d^2 - 2500) * 0.1) / fov * 20 * speed per 0.2 s tick, at GAMMA's speed 0.5
	check(env.ID_SPEED == 0.5, "GAMMA's Identification UI speed")
	local per_tick = 100 / ((80 * 80 - 2500) * 0.1) / 75 * 20 * env.ID_SPEED
	check(near(ir(80, 75), per_tick * 5), "80 m matches the mod's per-tick gain x 5 ticks a second")
	check(ir(100, 75) < ir(80, 75), "further away identifies slower")
	check(ir(100, 18) > ir(100, 75), "through a scope (smaller fov) identifies faster")
	check(ir(100, nil) > 0, "missing fov falls back to 75")
	local t_full = 1.2
	check(rs(t_full, true, 300, false, 75) == 1, "already identified: quick decode wherever they are")
	check(rs(t_full, false, 10, false, 75) == 0, "close stalker you are not looking at: not identified")
	check(rs(t_full, false, 120, false, 75) == 0, "far stalker you are not looking at: paused")
	local s_near = rs(t_full, false, 10, true, 75)
	check(s_near < 1 and near(s_near, t_full / env.ID_MIN_TIME), "close stalker you look at: takes ID_MIN_TIME")
	local s = rs(t_full, false, 120, true, 75)
	check(s > 0 and s < 1 and near(s, ir(120, 75) * t_full), "far stalker you look at: decodes at the mod's rate")
	-- seconds to identify: 2 s up to about 60 m, 11 s at 100 m, 3 s at 100 m through a 4x scope
	local at60, plain, scoped = 1 / ir(60, 75), 1 / ir(100, 75), 1 / ir(100, 75 / 4)
	check(near(at60, env.ID_MIN_TIME), ("60 m: %.2f s"):format(at60))
	check(plain > 10 and plain < 12.5 and scoped > 2.5 and scoped < 3.2, ("100 m: %.1f s plain, %.1f s scoped"):format(plain, scoped))
end

-- skeleton boxes: the joints' bounds get a little room for the body around them
local pj = rawget(env, "pad_joint_bounds")
check(type(pj) == "function", "pad_joint_bounds exists")
if type(pj) == "function" then
	local u0, v0, u1, v1 = pj(0.50, 0.30, 0.52, 0.70, 16 / 9)
	local h = 0.40
	check(math.abs((v1 - v0) - h * (1 + 2 * env.BONE_PAD_H)) < 1e-9, "a little room above and below")
	check(math.abs((u1 - u0) - (0.02 + 2 * h * env.BONE_PAD_W / (16 / 9))) < 1e-9, "room either side, in screen heights")
	check(u1 - u0 < (v1 - v0) / (16 / 9), "a standing body's box stays taller than wide")
	check(#env.BOX_BONES >= env.BONE_MIN, "enough bones to build a box")
end

-- info line: progress while unknown, rank and distance once known, KIA when dead
local it = rawget(env, "info_text")
check(type(it) == "function", "info_text exists")
if type(it) == "function" then
	check(it(false, false, 0.456, "VETERAN", 142.4) == "IDENT 45%  142 M", "unknown: progress and distance")
	check(it(false, true, 1, "VETERAN", 87.6) == "VETERAN  88 M", "known: rank and distance")
	check(it(false, true, 1, "", 30) == "30 M", "known mutant (no rank): distance only")
	check(it(true, true, 1, "VETERAN", 10) == "KIA", "dead: KIA")
	check(it(false, false, nil, nil, nil) == "IDENT 0%", "no progress or distance yet")
	check(#it(false, false, 1, "", 99999) <= env.INFO_CHARS, "fits INFO_CHARS")
	local W = { kia = "\219\225\232\242", ident = "\206\239\238\231\237.", m = "\236" }
	check(it(true, nil, nil, nil, nil, W) == W.kia, "translated words are used")
end

-- label layout: on screen, below the box when there is no room above, stacked without overlaps
local ll = rawget(env, "layout_labels")
check(type(ll) == "function", "layout_labels exists")
if type(ll) == "function" then
	local function q(cx, top, bottom, prio) return { cx = cx, top = top, bottom = bottom, w = 80, h = 30, prio = prio } end
	local function overlap(a, b)
		return math.abs(a.x - b.x) < (a.w + b.w) * 0.5 and a.y < b.y + b.h and a.y + a.h > b.y
	end
	-- plenty of room: sits just above the box
	local L1 = { q(512, 300, 500, 10) }
	ll(L1, 1, 4)
	check(L1[1].y == 300 - 4 - 30 and L1[1].x == 512, "above the box")
	-- someone close: box top off the screen, so the label goes below the box
	local L2 = { q(512, -50, 400, 5) }
	ll(L2, 1, 4)
	check(L2[1].y == 404, "no room above: below the box")
	-- huge box filling the screen: pinned inside the top edge
	local L3 = { q(512, -50, 900, 5) }
	ll(L3, 1, 4)
	check(L3[1].y == env.LABEL_MARGIN, "no room above or below: inside the top edge")
	-- at the screen edge: pulled in so it is fully visible
	local L4 = { q(1020, 300, 500, 5) }
	ll(L4, 1, 4)
	check(L4[1].x + 40 <= 1024 - env.LABEL_MARGIN + 1e-9, "kept inside the right edge")
	-- two people side by side: the nearer keeps its place, the other stacks above it
	local far, near = q(520, 300, 500, 60), q(500, 300, 500, 20)
	local L5 = { far, near }
	ll(L5, 2, 4)
	check(near.y == 300 - 4 - 30, "nearer label stays above its box")
	check(not overlap(near, far), "labels never overlap")
	check(far.y < near.y, "the further one stacks above")
	-- the aimed-at target wins its spot even when further away
	local tgt, close = q(500, 300, 500, -1), q(505, 300, 500, 5)
	local L6 = { close, tgt }
	ll(L6, 2, 4)
	check(tgt.y == 300 - 4 - 30 and not overlap(tgt, close), "aimed target first, others move")
	-- a crowd of six in one spot: none overlap, all on screen
	local L7 = {}
	for i = 1, 6 do L7[i] = q(500 + i, 200, 400, i * 10) end
	ll(L7, 6, 4)
	local ok = true
	for i = 1, 6 do
		if L7[i].y < 0 or L7[i].y + L7[i].h > 768 then ok = false end
		for j = i + 1, 6 do if overlap(L7[i], L7[j]) then ok = false end end
	end
	check(ok, "a crowd stacks with no overlaps, all on screen")
end

-- picture-in-picture scopes: points inside the lens are magnified about the view centre
local pm, pmag = rawget(env, "pip_map"), rawget(env, "pip_magnification")
check(type(pm) == "function" and type(pmag) == "function", "scope view functions exist")
if type(pm) == "function" and type(pmag) == "function" then
	local function near(a, b) return math.abs(a - b) < 1e-6 end
	local P = { m = 4, r = 0.12, a = 16 / 9 }
	local u, v, inside = pm(0.5 + 0.01, 0.5 + 0.02, P)
	check(near(u, 0.54) and near(v, 0.58) and inside, "inside the lens: 4x further from the centre")
	local cu, cv = pm(0.5, 0.5, P)
	check(near(cu, 0.5) and near(cv, 0.5), "the centre stays the centre")
	local fu, fv, fin = pm(0.5, 0.5 + 0.05, P)
	check(fu ~= nil and near(fv, 0.7) and not fin, "magnified past the lens edge: still placed, flagged outside")
	local _, _, oin = pm(0.9, 0.2, P)
	check(not oin, "far from the centre: outside the lens")
	local nu, nv, nin = pm(0.51, 0.52, { m = 1, r = 0.12, a = 16 / 9 })
	check(nu == 0.51 and nv == 0.52 and nin, "no scope view: unchanged")
	-- a box's height grows with the magnification
	local _, top = pm(0.5, 0.49, P)
	local _, bot = pm(0.5, 0.51, P)
	check(near(bot - top, 0.08), "box height x4 inside the lens")

	-- boxes through the scope: only inside the lens, clipped to it, never dropped for being big
	local pc = rawget(env, "pip_clip_box")
	check(type(pc) == "function", "pip_clip_box exists")
	if type(pc) == "function" then
		local ry = 0.12 * 768
		local cx, cy, w, h = pc(512, 400, 60, 120, P)
		check(cx == 512 and cy == 400 and w == 60 and h == 120, "small box inside the lens: unchanged")
		local bx, by, bw, bh = pc(512, 384 + 30, 120, 600, P)
		check(bx and bh <= 2 * ry + 1e-6 and by - bh * 0.5 >= 384 - ry - 1e-6, "body filling the lens: box clipped to it, not dropped")
		check(pc(150, 384, 40, 80, P) == nil, "someone outside the lens: no box")
		check(pc(512, 384 + ry * 1.2, 40, 80, P) == nil, "centre outside the lens: no box")
		local sx, sy, sw, sh = pc(150, 384, 40, 80, { m = 1, r = 0.12, a = 16 / 9 })
		check(sx == 150 and sw == 40, "no scope view: boxes anywhere")
	end

	local pil = rawget(env, "pip_inside_lens")
	check(type(pil) == "function", "pip_inside_lens exists")
	if type(pil) == "function" then
		local ry = 0.12 * 768
		check(pil(512, 384, P) == true, "lens centre is inside lens")
		check(pil(800, 384, P) == false, "right side of screen is outside lens")
		check(pil(512, 384 + ry * 1.2, P) == false, "above/below lens radius is outside lens")
		check(pil(512, 384, { m = 1, r = 0.12, a = 16 / 9 }) == false, "inactive PiP: nothing inside lens")
	end

	-- lens size from the Bodycam exes' measurement (pip.log, [SVP-RATIO] measH = lens height in half screens)
	local pl = rawget(env, "parse_lens_log")
	check(type(pl) == "function", "parse_lens_log exists")
	if type(pl) == "function" then
		local log = table.concat({
			"[SVP-RATIO] scope x measH 0.40 w 0.2 aim 1.00 r 1 frame 90",      -- before this scope came up
			"[SVP-RATIO] scope x measH 0.48 w 0.2 aim 0.50 r 1 frame 120",     -- not aimed: ignored
			"[SVP-RATIO] scope x measH 0.52 w 0.2 aim 1.00 r 1 frame 130",
			"[SVP-RATIO] scope x measH 9.00 w 0.2 aim 1.00 r 1 frame 131",     -- nonsense: ignored
			"some other line",
		}, "\n")
		local r = pl(log, 100, 200)
		check(r and math.abs(r - 0.13) < 1e-9, ("latest good measurement: radius 0.13, got %s"):format(tostring(r)))
		check(pl(log, 140, 200) == nil, "nothing newer than this scope: no measurement")
		check(pl("", 0, 10) == nil and pl(nil, 0, 10) == nil, "empty log: no measurement")
	end

	-- magnification: GAMMA's 3DSS zoom factors work out at 100 / zf (as the Bodycam exes' scope
	-- projection uses them, svp_runtime_factor_to_magnification), at every zoom step
	local m30 = pmag(30, 75, 75)
	check(m30 > 3.3 and m30 < 3.35, ("3DSS zoom factor 30: 100 / 30, got %.2f"):format(m30))
	check(pmag(20, 75, 75) > m30, "zoom factor 20 magnifies more than 30")
	check(pmag(30, 75, 60) < m30, "main view already zoomed a little: less relative magnification")
	check(pmag(nil, 75, 75) == 1 and pmag(0.5, 75, 75) == 1, "no or bad zoom factor: 1")

	-- regression: variable-zoom scopes, every step of the ladder (the exe steps the factor linearly,
	-- zoom_step_count 3). The top of a 3-24x (March F) is factor 4.167 = 24x, it was read as 4.17x.
	local function ladder(f_min, f_top, steps)
		local t, d = {}, (f_min - f_top) / steps
		for i = 0, steps do t[#t + 1] = f_min - d * i end
		return t
	end
	local function mag_ok(f, want, fov)
		local got = pmag(f, fov, fov)
		check(math.abs(got - want) < 0.01, ("zoom factor %.3f at fov %d: %.2fx, got %.2fx"):format(f, fov, want, got))
		return got
	end
	for _, fov in ipairs({ 75, 90 }) do
		local prev = 0
		for i, f in ipairs(ladder(100 / 3, 100 / 24, 3)) do              -- March F 3-24x
			local m = mag_ok(f, 100 / f, fov)
			check(m > prev, ("March F step %d magnifies more than step %d"):format(i, i - 1))
			prev = m
		end
		for _, f in ipairs(ladder(100, 20, 3)) do mag_ok(f, math.max(100 / f, 1), fov) end   -- 1-6x
		for _, f in ipairs({ 5, 6, 6.66 }) do mag_ok(f, 100 / f, fov) end -- 3DSS 20x / 16.7x / 15x tops
	end
	-- mapping at the top step: a point 0.01 right of the aim point lands 0.24 right of the lens centre
	local Ptop = { m = pmag(100 / 24, 90, 90), r = 0.2, a = 16 / 9, au = 0.5, av = 0.5 }
	local tu, tv, tin = pm(0.51, 0.5, Ptop)
	check(math.abs(tu - 0.74) < 1e-6 and tv == 0.5 and not tin, ("24x: 0.01 off the aim point maps 0.24 out, got %.4f"):format(tu))
	local su, _, sin = pm(0.502, 0.5, Ptop)
	check(math.abs(su - 0.548) < 1e-6 and sin, "24x: a point near the aim point stays inside the lens")
end

-- scope zoom
local zf = rawget(env, "zoom_factor")
check(type(zf) == "function", "zoom_factor exists")
if type(zf) == "function" then
	local function near(a, b) return math.abs(a - b) < 1e-6 end
	check(zf(75, 75) == 1, "no scope: 1")
	check(zf(75, 80) == 1, "wider than normal: 1")
	check(near(zf(90, 2 * math.deg(math.atan(0.25))), 4), "4x scope from 90 degrees")
	check(zf(75, 0.1) == 1 and zf(nil, 30) == 1 and zf(75, nil) == 1, "bad input: 1")
	check(zf(170, 0.6) <= 40, "capped at MAX_ZOOM")
end

-- small quadruped height floor
local bty = rawget(env, "box_top_y")
check(type(bty) == "function", "box_top_y exists")
if type(bty) == "function" then
	check(math.abs(bty(0.10, 0.0, true) - 0.27) < 1e-6, "quadruped height floor uses 0.15 + 0.12")
	check(math.abs(bty(0.10, 0.0, false) - 0.72) < 1e-6, "stalker height floor keeps 0.5 + 0.22")
end

-- known / id_progress lifecycle: kept across visible == false, cleared on load / net_destroy
do
	local cbs = {}
	local now_ms = 1000
	local function make_vec(x, y, z)
		local v = { x = x or 0, y = y or 0, z = z or 0 }
		function v:set(nx, ny, nz) self.x, self.y, self.z = nx or 0, ny or 0, nz or 0; return self end
		function v:distance_to(o) local dx, dy, dz = self.x - o.x, self.y - o.y, self.z - o.z; return math.sqrt(dx*dx+dy*dy+dz*dz) end
		function v:distance_to_sqr(o) local dx, dy, dz = self.x - o.x, self.y - o.y, self.z - o.z; return dx*dx+dy*dy+dz*dz end
		return v
	end
	local function make_wnd()
		local w = {}
		return setmetatable(w, { __index = function() return function() return w end end })
	end
	local npc_pos = make_vec(0, 0, 20)
	local npc_head = make_vec(0, 1.6, 20)
	local npc = {
		alive = function() return true end,
		position = function() return npc_pos end,
		relation = function() return 0 end,
		has_info = function() return false end,
		character_name = function() return "Tolik" end,
		character_community = function() return "stalker" end,
	}
	local actor_pos = make_vec(0, 0, 0)
	local actor = {
		position = function() return actor_pos end,
		see = function() return true end,
	}
	local last_rgb = nil          -- colour of the last GetARGB call (the box)
	local ae
	ae = setmetatable({
		db = { actor = actor, storage = { [42] = { object = npc } } },
		level = { object_by_id = function(id) return id == 42 and npc or nil end },
		game_object = { enemy = 2, friend = 0, neutral = 1 },
		IsStalker = function(o) return o == npc end,
		IsMonster = function() return false end,
		utils_obj = { safe_bone_pos = function() return npc_head end },
		game = {
			world2ui = function(v) return { x = 512, y = (v.y > 0.5) and 300 or 450 } end,
			translate_string = function(s) return s end,
		},
		device = function()
			return { width = 1920, height = 1080, fov = 75, cam_pos = make_vec(0, 1.6, 0), cam_dir = make_vec(0, 0, 1) }
		end,
		time_global = function() return now_ms end,
		vector = make_vec,
		vector2 = make_vec,
		Frect = make_vec,
		GetARGB = function(a, r, g, b) last_rgb = { r, g, b }; return 0 end,
		RegisterScriptCallback = function(name, fn) cbs[name] = fn end,
	}, { __index = _G })
	local c = assert(loadfile(PATH))
	setfenv(c, ae)
	c()
	ae.on_game_start()
	check(type(cbs.actor_on_first_update) == "function" and type(cbs.actor_on_net_destroy) == "function",
		"zbc_allies registers load/destroy callbacks")

	local pool = { { box = make_wnd(), brk = make_wnd(), dot = make_wnd() } }
	local cfg = {
		allies = true, allies_range = 100, allies_dot_ratio = 0.7, allies_los = false,
		allies_enemies = true, allies_mutants = true, allies_size = 1, allies_opacity = 1,
		allies_color_companion = 2, allies_color_friend = 1, allies_color_enemy = 5,
		allies_names = false, allies_style = 0,
	}
	local lens = { k = 0, ox = 0, oy = 0, roll = 0, dist = 0, zoom = 1, shutter = 0 }

	ae.update(pool, cfg, lens, true)
	now_ms = 1080
	ae.update(pool, cfg, lens, true)
	check(ae.id_progress_for(42) ~= nil and ae.id_progress_for(42) > 0, "partial identification tracks id_progress")
	check(ae.is_known_id(42) == false, "a nearby NPC is not identified instantly")
	for step = 1, 40 do                     -- 3.2 s of looking at them: past ID_MIN_TIME
		now_ms = now_ms + 80
		ae.update(pool, cfg, lens, true)
	end
	check(ae.is_known_id(42) == true, "nearby NPC becomes known")

	-- Hiding HUD (inventory/PDA) preserves known
	ae.update(pool, cfg, lens, false)
	check(ae.is_known_id(42) == true, "visible == false preserves known")

	-- looking back at someone identified: their colour is there at once, no white decode again
	last_rgb = nil
	ae.update(pool, cfg, lens, true)
	check(last_rgb ~= nil, "the box is drawn again")
	if last_rgb then
		check(not (last_rgb[1] == 255 and last_rgb[2] == 255 and last_rgb[3] == 255),
			"identified NPC keeps their colour when the box comes back")
	end

	-- actor_on_first_update clears known
	cbs.actor_on_first_update()
	check(ae.is_known_id(42) == false and ae.id_progress_for(42) == nil, "actor_on_first_update clears known and id_progress")

	-- Re-identify, then actor_on_net_destroy clears known
	now_ms = now_ms + 80
	ae.update(pool, cfg, lens, true)
	for step = 1, 40 do
		now_ms = now_ms + 80
		ae.update(pool, cfg, lens, true)
	end
	check(ae.is_known_id(42) == true, "re-identified NPC is known")
	-- the save keeps who is identified: save, leave the level, load, still known
	local saved = {}
	ae.save_state(saved)
	check(type(saved.zbc_known) == "table" and saved.zbc_known[#saved.zbc_known] == 42, "identified ids go into the save")
	cbs.actor_on_net_destroy()
	ae.load_state(saved)
	cbs.actor_on_first_update()
	check(ae.is_known_id(42) == true, "still identified after loading the save")

	-- a game started without that data (a new game): nobody known
	cbs.actor_on_net_destroy()
	cbs.actor_on_first_update()
	check(ae.is_known_id(42) == false and ae.id_progress_for(42) == nil, "no saved data: memory cleared")

	-- a save without the data, or with junk in it, loads with nobody known
	ae.load_state({ zbc_known = { "x", -5, 70000, 7 } })
	check(ae.is_known_id(7) == true and ae.is_known_id(70000) == false, "only valid ids are restored")
	ae.load_state({})
	check(ae.is_known_id(7) == false, "a save without the data: nobody known")
end

-- allies_mutants decoupled from allies_enemies & allies_color_enemy=7, label clamping, visible==false preserves states
do
	local now_ms = 1000
	local box_shown, min_gx, min_gy, max_gx, max_gy = 0, 9999, 9999, -9999, -9999
	local function make_vec(x, y, z)
		local v = { x = x or 0, y = y or 0, z = z or 0 }
		function v:set(nx, ny, nz) self.x, self.y, self.z = nx or 0, ny or 0, nz or 0; return self end
		function v:distance_to(o) local dx, dy, dz = self.x - o.x, self.y - o.y, self.z - o.z; return math.sqrt(dx*dx+dy*dy+dz*dz) end
		function v:distance_to_sqr(o) local dx, dy, dz = self.x - o.x, self.y - o.y, self.z - o.z; return dx*dx+dy*dy+dz*dz end
		return v
	end
	local function make_wnd(is_box, is_glyph)
		local w = {}
		return setmetatable(w, { __index = {
			Show = function(_, v) if is_box and v then box_shown = box_shown + 1 end end,
			SetWndPos = function(_, p)
				if is_glyph then
					if p.x < min_gx then min_gx = p.x end
					if p.y < min_gy then min_gy = p.y end
					if p.x > max_gx then max_gx = p.x end
					if p.y > max_gy then max_gy = p.y end
				end
			end,
			SetWndSize = function() end,
			SetTextureColor = function() end,
			SetTextureRect = function() end,
			InitTexture = function() end,
		} })
	end
	local mut_pos = make_vec(0, 0, 15)
	local mut_head = make_vec(0, 0.8, 15)
	local mut = {
		alive = function() return true end,
		position = function() return mut_pos end,
		relation = function() return 2 end,
		has_info = function() return false end,
	}
	local actor = { position = function() return make_vec(0, 0, 0) end, see = function() return true end }
	local see_calls = 0
	actor.see = function() see_calls = see_calls + 1; return true end
	local ae
	ae = setmetatable({
		db = { actor = actor, storage = { [77] = { object = mut } } },
		level = { object_by_id = function(id) return id == 77 and mut or nil end },
		game_object = { enemy = 2, friend = 0, neutral = 1 },
		IsStalker = function() return false end,
		IsMonster = function(o) return o == mut end,
		dynamic_news_helper = { GetMonsterDescription = function() return "dog" end },
		utils_obj = { safe_bone_pos = function() return mut_head end },
		game = {
			world2ui = function(v) return { x = 5, y = (v.y > 0.3) and 5 or 45 } end,
			translate_string = function(s) return s end,
		},
		device = function()
			return { width = 1920, height = 1080, fov = 75, cam_pos = make_vec(0, 1.6, 0), cam_dir = make_vec(0, 0, 1) }
		end,
		zbc_font_metrics = { em = 32, advance = 20, cell_w = 32, cell_h = 40, pad = 4, cols = 16, rows = 16, tex_w = 512, tex_h = 512, first = 33, last = 126 },
		time_global = function() return now_ms end,
		vector = make_vec, vector2 = make_vec, Frect = make_vec,
		GetARGB = function(a, r, g, b) return { a = a, r = r, g = g, b = b } end,
		RegisterScriptCallback = function() end,
	}, { __index = _G })
	local c = assert(loadfile(PATH))
	setfenv(c, ae)
	c()

	local glyphs_n, glyphs_f = {}, {}
	for i = 1, 24 do glyphs_n[i] = make_wnd(false, true) end
	for i = 1, 20 do glyphs_f[i] = make_wnd(false, true) end
	local pool = { {
		box = make_wnd(true), brk = make_wnd(false), dot = make_wnd(false),
		lbl = { name = { glyphs = glyphs_n }, fac = { glyphs = glyphs_f } },
	} }
	local cfg = {
		allies = true, allies_range = 100, allies_dot_ratio = 0.7, allies_los = true,
		allies_enemies = false, allies_mutants = true, allies_size = 1, allies_opacity = 1,
		allies_color_companion = 2, allies_color_friend = 1, allies_color_enemy = 7,
		allies_names = true, allies_style = 1,
	}
	local lens = { k = 0, ox = 0, oy = 0, roll = 0, dist = 0, zoom = 1, shutter = 0 }

	ae.update(pool, cfg, lens, true)
	now_ms = 1050
	ae.update(pool, cfg, lens, true)
	check(box_shown >= 1, "mutant remains visible when allies_enemies=false and allies_color_enemy=7")
	check(min_gx >= -10 and min_gy >= -10 and max_gx <= 1024 and max_gy <= 768,
		("label glyphs clamped on screen (min=%.1f,%.1f max=%.1f,%.1f)"):format(min_gx, min_gy, max_gx, max_gy))

	-- visible == false hides HUD without wiping states (no extra see_calls on next frame)
	local see_before = see_calls
	ae.update(pool, cfg, lens, false)
	now_ms = 1010
	ae.update(pool, cfg, lens, true)
	check(see_calls == see_before, "visible == false preserves states and avoids re-raycasting on reopen")

	-- tame mutant (relation=friend) and nil-relation mutant remain visible even when friend/enemy colours are Off (7)
	cfg.allies_color_friend = 7
	cfg.allies_color_enemy = 7
	mut.relation = function() return 0 end
	local shown_before = box_shown
	now_ms = 1100
	ae.update(pool, cfg, lens, true)
	check(box_shown > shown_before, "tame mutant remains visible even when allies_color_friend=7")
	mut.relation = nil
	shown_before = box_shown
	now_ms = 1150
	ae.update(pool, cfg, lens, true)
	check(box_shown > shown_before, "mutant with nil relation remains visible with enemy colour fallback")
end

-- Zoomed-in partial-body projection, close-up head-tracking switch, smooth morph, hysteresis,
-- spine fallback, quadruped mutants, lens unwarp, and identification while head-tracking.
do
	local now_ms = 1000
	local sw, sh = 1920, 1080
	local ux, uy = 1024 / sw, 768 / sh
	local cur_fov = 75
	local clip_below_y = nil -- when set, world2ui returns -9999 if v.y < clip_below_y or v.y > clip_above_y
	local clip_above_y = nil
	local cam_pos_v = { x = 0, y = 1.6, z = 0 }
	local cam_dir_v = { x = 0, y = 0, z = 1 }

	local function make_vec(x, y, z)
		local v = { x = x or 0, y = y or 0, z = z or 0 }
		function v:set(nx, ny, nz) self.x, self.y, self.z = nx or 0, ny or 0, nz or 0; return self end
		function v:distance_to(o) local dx, dy, dz = self.x - o.x, self.y - o.y, self.z - o.z; return math.sqrt(dx*dx+dy*dy+dz*dz) end
		function v:distance_to_sqr(o) local dx, dy, dz = self.x - o.x, self.y - o.y, self.z - o.z; return dx*dx+dy*dy+dz*dz end
		return v
	end

	local last_draw = {}
	local function make_spy_wnd(kind)
		local w = { shown = false, cx = 0, cy = 0, bw = 0, bh = 0 }
		return setmetatable(w, { __index = {
			Show = function(self, v)
				self.shown = v and true or false
				if kind and v then
					last_draw[kind] = { cx = self.cx, cy = self.cy, w = self.bw, h = self.bh, color = self._col }
				end
			end,
			SetWndPos = function(self, p) self._px, self._py = p.x, p.y end,
			SetWndSize = function(self, s)
				self.bw, self.bh = s.x, s.y
				self.cx = (self._px or 0) + s.x * 0.5
				self.cy = (self._py or 0) + s.y * 0.5
			end,
			SetTextureColor = function(self, c) self._col = c end,
			SetTextureRect = function() end,
			InitTexture = function() end,
			SetStretchTexture = function() end,
		} })
	end

	local npc_pos = make_vec(0, 0, 20)
	local npc_head = make_vec(0, 1.6, 20)
	local npc_spine = make_vec(0, 1.0, 20)
	local npc_kind = "stalker"
	local use_head_bone = true

	local target = {
		alive = function() return true end,
		position = function() return npc_pos end,
		relation = function() return 0 end,
		has_info = function() return false end,
		character_name = function() return "Strelok" end,
		character_community = function() return "stalker" end,
	}
	local actor = { position = function() return make_vec(0, 0, 0) end, see = function() return true end }

	local function persp_world2ui(v)
		if clip_below_y and v.y < clip_below_y then return { x = -9999, y = -9999 } end
		if clip_above_y and v.y > clip_above_y then return { x = -9999, y = -9999 } end
		local dx, dy, dz = v.x - cam_pos_v.x, v.y - cam_pos_v.y, v.z - cam_pos_v.z
		if dz <= 0.1 then return { x = -9999, y = -9999 } end
		local tan_half = math.tan(math.rad(cur_fov) * 0.5)
		local aspect = sw / sh
		local u = 0.5 + 0.5 * (dx / (dz * tan_half * aspect))
		local vv = 0.5 - 0.5 * (dy / (dz * tan_half))
		return { x = u * 1024, y = vv * 768 }
	end

	local ae = setmetatable({
		db = { actor = actor, storage = { [101] = { object = target } } },
		level = { object_by_id = function(id) return id == 101 and target or nil end },
		game_object = { enemy = 2, friend = 0, neutral = 1 },
		IsStalker = function() return npc_kind == "stalker" end,
		IsMonster = function() return npc_kind == "monster" end,
		dynamic_news_helper = { GetMonsterDescription = function() return "dog" end },
		utils_obj = {
			safe_bone_pos = function(_, bone)
				if bone == "bip01_head" then return use_head_bone and npc_head or nil end
				if bone == "bip01_spine" then return npc_spine end
				return nil
			end,
		},
		game = { world2ui = persp_world2ui, translate_string = function(s) return s end },
		device = function()
			return {
				width = sw, height = sh, fov = cur_fov,
				cam_pos = make_vec(cam_pos_v.x, cam_pos_v.y, cam_pos_v.z),
				cam_dir = make_vec(cam_dir_v.x, cam_dir_v.y, cam_dir_v.z),
			}
		end,
		get_console = function() return { get_float = function() return 75 end } end,
		zbc_font_metrics = { em = 32, advance = 20, cell_w = 32, cell_h = 40, pad = 4, cols = 16, rows = 16, tex_w = 512, tex_h = 512, first = 33, last = 126 },
		time_global = function() return now_ms end,
		vector = make_vec, vector2 = make_vec, Frect = make_vec,
		GetARGB = function(a, r, g, b) return { a = a, r = r, g = g, b = b } end,
		RegisterScriptCallback = function() end,
	}, { __index = _G })

	local c = assert(loadfile(PATH))
	setfenv(c, ae)
	c()

	local min_gy, max_gy = 9999, -9999
	local function make_glyph_wnd()
		local w = {}
		return setmetatable(w, { __index = {
			Show = function() end,
			SetWndPos = function(_, p)
				if p.y < min_gy then min_gy = p.y end
				if p.y > max_gy then max_gy = p.y end
			end,
			SetWndSize = function() end,
			SetTextureColor = function() end,
			SetTextureRect = function() end,
		} })
	end
	local glyphs_n, glyphs_f = {}, {}
	for i = 1, 24 do glyphs_n[i] = make_glyph_wnd() end
	for i = 1, 20 do glyphs_f[i] = make_glyph_wnd() end

	local pool = { {
		box = make_spy_wnd("box"), brk = make_spy_wnd("brk"), dot = make_spy_wnd("dot"),
		lbl = { name = { glyphs = glyphs_n }, fac = { glyphs = glyphs_f } },
	} }
	local cfg = {
		allies = true, allies_range = 100, allies_dot_ratio = 0.7, allies_los = false,
		allies_enemies = true, allies_mutants = true, allies_size = 1, allies_opacity = 1,
		allies_color_companion = 2, allies_color_friend = 1, allies_color_enemy = 5,
		allies_names = true, allies_style = 0,
	}
	local lens = { k = 0, ox = 0, oy = 0, roll = 0, dist = 0, zoom = 1, shutter = 0 }

	-- 1. Normal full-body box at 20m, fov=75
	last_draw.brk = nil
	ae.update(pool, cfg, lens, true)
	now_ms = 1050
	ae.update(pool, cfg, lens, true)
	check(last_draw.brk ~= nil, "normal stalker draws bracket box")
	if last_draw.brk then
		local px_w = last_draw.brk.w / ux
		local px_h = last_draw.brk.h / uy
		check(px_h > px_w * 1.5, "normal full-body box is tall (not square head box)")
	end

	-- 2. Zoomed in on upper half (fov=10, feet unprojectable below screen) -> head-tracking square
	cur_fov = 10
	clip_below_y = 0.5
	last_draw.brk = nil
	now_ms = 1100
	ae.update(pool, cfg, lens, true)
	check(last_draw.brk ~= nil, "zoomed-in stalker with unprojectable feet still shows box")
	if last_draw.brk then
		local px_w = last_draw.brk.w / ux
		local px_h = last_draw.brk.h / uy
		check(math.abs(px_w - px_h) < 1.5, ("zoomed-in head box is square in screen px (w=%.1f, h=%.1f)"):format(px_w, px_h))
		check(math.abs(last_draw.brk.cy - 384) < 30, "head box is centered on bip01_head")
		check(px_h > 30 and px_h < 250, ("head box scales naturally with scope zoom (h=%.1f px)"):format(px_h))
	end

	-- 3. Zoomed in with feet projecting below screen (fv > 1, clipped vertically) + label placement
	clip_below_y = nil
	min_gy, max_gy = 9999, -9999
	last_draw.brk = nil
	now_ms = 1150
	ae.update(pool, cfg, lens, true)
	check(last_draw.brk ~= nil, "zoomed-in stalker with feet below bottom edge uses head-tracking")
	if last_draw.brk then
		local px_w = last_draw.brk.w / ux
		local px_h = last_draw.brk.h / uy
		check(math.abs(px_w - px_h) < 1.5, "clipped full-body switches to square head-tracking")
		local box_top = last_draw.brk.cy - last_draw.brk.h * 0.5
		check(max_gy <= box_top and min_gy >= -10, ("label placed above head box and clamped on screen (min_y=%.1f, max_y=%.1f, top=%.1f)"):format(min_gy, max_gy, box_top))
	end

	-- 4. Unscoped close-up (1.2m, fov=75) does NOT switch to head-tracking; scoped (fov=10 or PiP) DOES
	ae.clear_known()
	cur_fov = 75
	npc_pos:set(0, 0, 1.2)
	npc_head:set(0, 1.6, 1.2)
	npc_spine:set(0, 1.0, 1.2)
	last_draw.brk = nil
	now_ms = 1200
	ae.update(pool, cfg, lens, true)
	now_ms = 1250
	ae.update(pool, cfg, lens, true)
	check(last_draw.brk ~= nil, "unscoped close-up stalker at 1.2m draws full-body box")
	if last_draw.brk then
		local px_w = last_draw.brk.w / ux
		local px_h = last_draw.brk.h / uy
		check(px_h > px_w * 1.5, "unscoped close-up does NOT switch to square head-tracking")
	end

	-- Now scope in via FOV zoom (cur_fov=10) -> head-tracking activates and respects cap
	cur_fov = 10
	last_draw.brk = nil
	for _ = 1, 10 do
		now_ms = now_ms + 50
		ae.update(pool, cfg, lens, true)
	end
	if last_draw.brk then
		local px_w = last_draw.brk.w / ux
		local px_h = last_draw.brk.h / uy
		check(math.abs(px_w - px_h) < 1.5, "scoped close-up box switches to square head-tracking")
		check(last_draw.brk.h <= 768 * 0.75 + 0.01, "scoped close-up head box respects max screen size cap")
	end

	-- Also verify 3DSS PiP scope (pip_active() = true, cur_fov = 75) enables head-tracking
	ae.clear_known()
	cur_fov = 75
	local orig_pip_refresh = ae.pip_refresh
	ae.pip_refresh = function() ae.PIP.m = 3.33; ae.PIP.r = 0.25; return ae.PIP end
	npc_pos:set(0, 0, 20)
	npc_head:set(0, 1.6, 20)
	npc_spine:set(0, 1.0, 20)
	clip_below_y = 0.5
	last_draw.brk = nil
	now_ms = 1260
	ae.update(pool, cfg, lens, true)
	now_ms = 1290
	ae.update(pool, cfg, lens, true)
	check(last_draw.brk ~= nil, "PiP scoped stalker with clipped feet shows head-tracking box")
	if last_draw.brk then
		local px_w = last_draw.brk.w / ux
		local px_h = last_draw.brk.h / uy
		check(math.abs(px_w - px_h) < 1.5, "PiP scoped clipped body switches to square head-tracking")
	end
	ae.pip_refresh = orig_pip_refresh
	ae.PIP.m = 1
	clip_below_y = nil

	-- 5. Smooth transition (no instant pop) when scoping in on 1.5m stalker, and smooth return when unscoping
	ae.clear_known()
	cur_fov = 75
	npc_pos:set(0, 0, 1.5)
	npc_head:set(0, 1.6, 1.5)
	npc_spine:set(0, 1.0, 1.5)
	now_ms = 1300
	ae.update(pool, cfg, lens, true)
	now_ms = 1350
	ae.update(pool, cfg, lens, true)
	local start_h = last_draw.brk and last_draw.brk.h or 0
	cur_fov = 15
	local heights = {}
	for i = 1, 6 do
		now_ms = now_ms + 40
		ae.update(pool, cfg, lens, true)
		heights[i] = last_draw.brk and last_draw.brk.h or 0
	end
	check(start_h > 0 and heights[1] > heights[6] and heights[2] > heights[5],
		("smooth morph from full-body to head-tracking when scoping in (h: %.1f -> %.1f -> %.1f)"):format(heights[1], heights[3], heights[6]))
	-- Unscoping smoothly morphs back to full-body
	cur_fov = 75
	local unscope_h = {}
	for i = 1, 6 do
		now_ms = now_ms + 40
		ae.update(pool, cfg, lens, true)
		unscope_h[i] = last_draw.brk and last_draw.brk.h or 0
	end
	check(unscope_h[6] > unscope_h[1],
		("smooth morph back to full-body when unscoping (h: %.1f -> %.1f)"):format(unscope_h[1], unscope_h[6]))

	-- 6. Hysteresis prevents flicker near bottom screen edge (while scoped in, cur_fov=50 -> view_zoom ~ 1.59)
	ae.clear_known()
	cur_fov = 50
	-- At z=4.0, cur_fov=50, cam_y=1.6, tan(25)=0.4663 -> bottom of screen is y = 1.6 - 4.0*0.4663 = -0.265.
	-- Place feet at y = -0.35 (just below bottom of screen -> triggers head-tracking)
	npc_pos:set(0, -0.35, 4.0)
	npc_head:set(0, 1.25, 4.0)
	npc_spine:set(0, 0.65, 4.0)
	now_ms = 1600
	ae.update(pool, cfg, lens, true)
	now_ms = 1650
	ae.update(pool, cfg, lens, true)
	local head_h_px = last_draw.brk and (last_draw.brk.h / uy) or 0
	local head_w_px = last_draw.brk and (last_draw.brk.w / ux) or 0
	check(math.abs(head_w_px - head_h_px) < 1.5, "scoped feet just below screen triggers head-tracking")
	-- Move feet ~8 UI px inside bottom edge (within CLIP_MARGIN_LO=24 -> stays in head-tracking!)
	npc_pos:set(0, -0.22, 4.0)
	npc_head:set(0, 1.38, 4.0)
	npc_spine:set(0, 0.78, 4.0)
	now_ms = 1700
	ae.update(pool, cfg, lens, true)
	local hyst_w_px = last_draw.brk and (last_draw.brk.w / ux) or 0
	local hyst_h_px = last_draw.brk and (last_draw.brk.h / uy) or 0
	check(math.abs(hyst_w_px - hyst_h_px) < 1.5, "hysteresis keeps head-tracking inside bottom margin")
	-- Move feet comfortably inside screen -> returns to full-body
	npc_pos:set(0, 0.2, 4.0)
	npc_head:set(0, 1.8, 4.0)
	npc_spine:set(0, 1.2, 4.0)
	for _ = 1, 8 do
		now_ms = now_ms + 50
		ae.update(pool, cfg, lens, true)
	end
	local back_w_px = last_draw.brk and (last_draw.brk.w / ux) or 0
	local back_h_px = last_draw.brk and (last_draw.brk.h / uy) or 0
	check(back_h_px > back_w_px * 1.5, "returns smoothly to full-body once well inside screen")

	-- 7. Spine fallback when zoomed in on mid-body (both head above screen & feet below screen unprojectable)
	ae.clear_known()
	cur_fov = 10
	cam_pos_v.y = 1.0
	npc_pos:set(0, 0, 20)
	npc_head:set(0, 1.6, 20)
	npc_spine:set(0, 1.0, 20)
	clip_above_y = 1.3
	clip_below_y = 0.5
	last_draw.brk = nil
	now_ms = 2200
	ae.update(pool, cfg, lens, true)
	now_ms = 2250
	ae.update(pool, cfg, lens, true)
	check(last_draw.brk ~= nil, "zoomed in on mid-body (head & feet off-screen) falls back to spine box")
	if last_draw.brk then
		check(math.abs(last_draw.brk.cy - 384) < 30, "spine fallback box is centered on bip01_spine")
	end

	-- 8. Lens warp/unwarp + quadruped mutant head-tracking + nil head bone fallback
	clip_above_y = nil
	clip_below_y = nil
	cam_pos_v.y = 1.6
	ae.clear_known()
	npc_kind = "monster"
	npc_pos:set(0, 0.8, 20)
	npc_head:set(0, 1.56, 20)
	npc_spine:set(0, 1.2, 20)
	cur_fov = 8
	clip_below_y = 1.0
	local warped_lens = { k = 1, ox = 0, oy = 0, roll = 0, dist = -0.3, zoom = 1.1, shutter = 0 }
	last_draw.brk = nil
	now_ms = 2300
	ae.update(pool, cfg, warped_lens, true)
	now_ms = 2350
	ae.update(pool, cfg, warped_lens, true)
	check(last_draw.brk ~= nil, "quadruped mutant zoomed-in head-tracking draws with active lens warp")
	if last_draw.brk then
		local q_w_px = last_draw.brk.w / ux
		local q_h_px = last_draw.brk.h / uy
		check(math.abs(q_w_px - q_h_px) < 4.0, "quadruped head-tracking box is square")
	end
	use_head_bone = false
	last_draw.brk = nil
	now_ms = 2400
	ae.update(pool, cfg, warped_lens, true)
	check(last_draw.brk ~= nil, "missing bip01_head bone falls back safely in head-tracking mode")

	-- 9. Identification works while zoomed-in & head-tracking beyond ID_INSTANT (80m)
	ae.clear_known()
	npc_kind = "stalker"
	use_head_bone = true
	clip_below_y = 1.0
	cur_fov = 10
	cam_pos_v.y = 1.6
	npc_pos:set(0, 0, 80)
	npc_head:set(0, 1.6, 80)
	npc_spine:set(0, 1.0, 80)
	now_ms = 2500
	ae.update(pool, cfg, lens, true)
	now_ms = 2580
	ae.update(pool, cfg, lens, true)
	check(ae.id_progress_for(101) ~= nil and ae.id_progress_for(101) > 0,
		"distant zoomed-in head-tracking target accumulates identification progress")

	-- 10. Unidentified dot stays white; identified dot takes relation colour
	ae.clear_known()
	clip_below_y = nil
	clip_above_y = nil
	cur_fov = 75
	npc_pos:set(0, 0, 80)
	npc_head:set(0, 1.6, 80)
	npc_spine:set(0, 1.0, 80)
	last_draw.dot = nil
	now_ms = 3000
	ae.update(pool, cfg, lens, true)
	now_ms = 3050
	ae.update(pool, cfg, lens, true)
	check(last_draw.dot ~= nil, "distant unidentified stalker (80m > 70m dot_dist) draws dot")
	if last_draw.dot and last_draw.dot.color then
		local c = last_draw.dot.color
		check(c.r == 255 and c.g == 255 and c.b == 255,
			("unidentified dot is white (got %d,%d,%d)"):format(c.r, c.g, c.b))
	end

	-- Identify stalker up close (20m), then move back to dot distance (80m)
	npc_pos:set(0, 0, 20)
	npc_head:set(0, 1.6, 20)
	npc_spine:set(0, 1.0, 20)
	for _ = 1, 30 do
		now_ms = now_ms + 100
		ae.update(pool, cfg, lens, true)
	end
	npc_pos:set(0, 0, 80)
	npc_head:set(0, 1.6, 80)
	npc_spine:set(0, 1.0, 80)
	last_draw.dot = nil
	for _ = 1, 15 do
		now_ms = now_ms + 100
		ae.update(pool, cfg, lens, true)
	end
	check(last_draw.dot ~= nil, "identified distant stalker draws dot")
	if last_draw.dot and last_draw.dot.color then
		local c = last_draw.dot.color
		check(c.r == 80 and c.g == 255 and c.b == 90,
			("identified friendly dot takes relation colour (got %d,%d,%d)"):format(c.r, c.g, c.b))
	end

	-- 11. Dots are hidden while scoped in (both FOV zoom and PiP, newly spotted and already tracked)
	local short_cfg = {
		allies = true, allies_range = 10, allies_dot_ratio = 0.7, allies_los = false,
		allies_enemies = true, allies_mutants = true, allies_size = 1, allies_opacity = 1,
		allies_color_companion = 2, allies_color_friend = 1, allies_color_enemy = 5,
		allies_names = true, allies_style = 0,
	}
	ae.clear_known()
	cur_fov = 50 -- view_zoom ~ 1.59 -> range ~ 15.9, dot_dist ~ 11.1
	npc_pos:set(0, 0, 13) -- between dot_dist (11.1) and range (15.9) -> dot-only target
	npc_head:set(0, 1.6, 13)
	npc_spine:set(0, 1.0, 13)
	last_draw.dot = nil
	now_ms = 8000
	ae.update(pool, short_cfg, lens, true)
	now_ms = 8050
	ae.update(pool, short_cfg, lens, true)
	check(last_draw.dot == nil, "dot-only target is hidden while FOV scoped in")

	-- (a) Already-tracked dot hides when scoping in via FOV zoom, and returns when unscoping
	ae.clear_known()
	cur_fov = 75
	npc_pos:set(0, 0, 8.5) -- unscoped: range=10, dot_dist=7 -> dot
	npc_head:set(0, 1.6, 8.5)
	npc_spine:set(0, 1.0, 8.5)
	last_draw.dot = nil
	now_ms = 8100
	ae.update(pool, short_cfg, lens, true)
	now_ms = 8150
	ae.update(pool, short_cfg, lens, true)
	check(last_draw.dot ~= nil, "already-tracked target draws dot while unscoped")
	-- Scope in with short_cfg2 where 8.5m stays > dot_dist even zoomed (range=8, dot_dist=5.6 -> zoomed 1.59x: range=12.7, dot_dist=8.9 -> use 10.5m? Instead test PiP scope with 13m)
	local tiny_cfg = {
		allies = true, allies_range = 8, allies_dot_ratio = 0.7, allies_los = false,
		allies_enemies = true, allies_mutants = true, allies_size = 1, allies_opacity = 1,
		allies_color_companion = 2, allies_color_friend = 1, allies_color_enemy = 5,
		allies_names = true, allies_style = 0,
	}
	ae.clear_known()
	cur_fov = 75
	npc_pos:set(0, 0, 7.0) -- unscoped: range=8, dot_dist=5.6 -> dot
	npc_head:set(0, 1.6, 7.0)
	npc_spine:set(0, 1.0, 7.0)
	last_draw.dot = nil
	now_ms = 8200
	ae.update(pool, tiny_cfg, lens, true)
	now_ms = 8250
	ae.update(pool, tiny_cfg, lens, true)
	check(last_draw.dot ~= nil, "unscoped dot-only target at 7m draws dot")
	cur_fov = 65 -- view_zoom ~ 1.18 > 1.05 -> dot_dist ~ 6.6m, so 7m stays target_dot == 1
	last_draw.dot = nil
	now_ms = 8300
	ae.update(pool, tiny_cfg, lens, true)
	check(last_draw.dot == nil, "already-tracked dot hides immediately when FOV scoping in")

	-- (b) PiP scope hides dot-only targets
	ae.clear_known()
	cur_fov = 75
	local orig_pip_refresh2 = ae.pip_refresh
	ae.pip_refresh = function() ae.PIP.m = 1.5; ae.PIP.r = 0.25; return ae.PIP end
	npc_pos:set(0, 0, 10.0) -- with m=1.5: range=12, dot_dist=8.4 -> 10m is dot-only
	npc_head:set(0, 1.6, 10.0)
	npc_spine:set(0, 1.0, 10.0)
	last_draw.dot = nil
	now_ms = 8400
	ae.update(pool, tiny_cfg, lens, true)
	now_ms = 8450
	ae.update(pool, tiny_cfg, lens, true)
	check(last_draw.dot == nil, "dot-only target is hidden while PiP scoped in")
	ae.pip_refresh = orig_pip_refresh2
	ae.PIP.m = 1

	-- (c) Unscoped mid-body clip (head & feet unprojectable) does NOT fall back to head or spine box
	ae.clear_known()
	cur_fov = 75
	cam_pos_v.y = 1.0
	npc_pos:set(0, 0, 20)
	npc_head:set(0, 1.6, 20)
	npc_spine:set(0, 1.0, 20)
	clip_above_y = 1.3
	clip_below_y = 0.5
	last_draw.brk = nil
	now_ms = 8500
	ae.update(pool, cfg, lens, true)
	now_ms = 8550
	ae.update(pool, cfg, lens, true)
	check(last_draw.brk == nil, "unscoped mid-body clip (head & feet off-screen) does NOT fall back to head/spine box")
	clip_above_y = nil
	clip_below_y = nil
	cam_pos_v.y = 1.6
end

-- 12. Dual-view 3DSS PiP projection & zero dots while scoped in:
--     - stalker inside PiP lens gets magnified box (with clipped-body head-tracking if needed)
--     - stalker nearby outside PiP lens (right side of screen) STILL gets a 1x main-camera full-body box
--     - stalker behind PiP lens circle (when gun aim is offset) does NOT draw a 1x box inside the lens
--     - distant target outside base cfg.allies_range outside lens does NOT get a 1x box
--     - zero dots (neither distant dots nor companion_edge dots) appear while PiP scoped in
do
	local now_ms = 1000
	local sw, sh = 1920, 1080
	local ux, uy = 1024 / sw, 768 / sh
	local cur_fov = 75
	local pip_on = false
	local pip_m, pip_r, pip_au, pip_av = 4.0, 0.18, 0.5, 0.5
	local cam_pos_v = { x = 0, y = 1.6, z = 0 }
	local cam_dir_v = { x = 0, y = 0, z = 1 }

	local function make_vec(x, y, z)
		local v = { x = x or 0, y = y or 0, z = z or 0 }
		function v:set(nx, ny, nz) self.x, self.y, self.z = nx or 0, ny or 0, nz or 0; return self end
		function v:distance_to(o) local dx, dy, dz = self.x - o.x, self.y - o.y, self.z - o.z; return math.sqrt(dx*dx+dy*dy+dz*dz) end
		function v:distance_to_sqr(o) local dx, dy, dz = self.x - o.x, self.y - o.y, self.z - o.z; return dx*dx+dy*dy+dz*dz end
		return v
	end

	local function make_slot_wnd()
		local w = { shown = false, cx = 0, cy = 0, w = 0, h = 0 }
		return setmetatable(w, { __index = {
			Show = function(self, v) self.shown = v and true or false end,
			SetWndPos = function(self, p) self._px, self._py = p.x, p.y end,
			SetWndSize = function(self, s)
				self.w, self.h = s.x, s.y
				self.cx = (self._px or 0) + s.x * 0.5
				self.cy = (self._py or 0) + s.y * 0.5
			end,
			SetTextureColor = function(self, c) self._col = c end,
			SetTextureRect = function() end,
			InitTexture = function() end,
			SetStretchTexture = function() end,
		} })
	end

	local function make_npc(name, x, y, z, is_companion)
		local pos = make_vec(x, y, z)
		local head = make_vec(x, y + 1.6, z)
		local spine = make_vec(x, y + 1.0, z)
		return {
			_pos = pos, _head = head, _spine = spine,
			alive = function() return true end,
			position = function() return pos end,
			relation = function() return 0 end,
			has_info = function(_, info) return is_companion and info == "npcx_is_companion" or false end,
			character_name = function() return name end,
			character_community = function() return "stalker" end,
		}
	end

	-- IDs:
	-- 201: inside PiP lens (center, 30m)
	-- 202: nearby outside PiP lens on right side of screen (x=8, z=15 -> ~17m, u ~ 0.89 -> cx ~ 910)
	-- 203: distant outside lens (x=45, z=65 -> ~79m > allies_range=50, u ~ 0.96 -> must NOT get 1x box)
	-- 204: distant dot-range inside lens (x=0, z=150 -> between dot_dist=140 and range=200 when pip_m=4)
	-- 205: off-screen companion behind/right (x=12, z=-5 -> triggers edge dot unscoped, hidden when scoped)
	local npcs = {
		[201] = make_npc("InsideLens", 0, 0, 30, false),
		[202] = make_npc("OutsideRight", 8, 0, 15, false),
		[203] = make_npc("TooFarRight", 45, 0, 65, false),
		[204] = make_npc("FarDotLens", 0, 0, 150, false),
		[205] = make_npc("EdgeComp", 12, 0, -5, true),
	}
	local active_ids = { [201] = true, [202] = true, [203] = true, [204] = true, [205] = true }

	local storage = {}
	for id, obj in pairs(npcs) do
		if active_ids[id] then storage[id] = { object = obj } end
	end

	local actor = { position = function() return make_vec(0, 0, 0) end, see = function() return true end }

	local function persp_world2ui(v)
		local dx, dy, dz = v.x - cam_pos_v.x, v.y - cam_pos_v.y, v.z - cam_pos_v.z
		if dz <= 0.1 then return { x = -9999, y = -9999 } end
		local tan_half = math.tan(math.rad(cur_fov) * 0.5)
		local aspect = sw / sh
		local u = 0.5 + 0.5 * (dx / (dz * tan_half * aspect))
		local vv = 0.5 - 0.5 * (dy / (dz * tan_half))
		return { x = u * 1024, y = vv * 768 }
	end

	local ae = setmetatable({
		db = { actor = actor, storage = storage },
		level = { object_by_id = function(id) return active_ids[id] and npcs[id] or nil end },
		game_object = { enemy = 2, friend = 0, neutral = 1 },
		IsStalker = function() return true end,
		IsMonster = function() return false end,
		utils_obj = {
			safe_bone_pos = function(obj, bone)
				if bone == "bip01_head" then return obj._head end
				if bone == "bip01_spine" then return obj._spine end
				return nil
			end,
		},
		game = { world2ui = persp_world2ui, translate_string = function(s) return s end },
		device = function()
			return {
				width = sw, height = sh, fov = cur_fov,
				cam_pos = make_vec(cam_pos_v.x, cam_pos_v.y, cam_pos_v.z),
				cam_dir = make_vec(cam_dir_v.x, cam_dir_v.y, cam_dir_v.z),
			}
		end,
		get_console = function() return { get_float = function() return 75 end } end,
		time_global = function() return now_ms end,
		vector = make_vec, vector2 = make_vec, Frect = make_vec,
		GetARGB = function(a, r, g, b) return { a = a, r = r, g = g, b = b } end,
		RegisterScriptCallback = function() end,
	}, { __index = _G })

	local c = assert(loadfile(PATH))
	setfenv(c, ae)
	c()

	ae.pip_refresh = function()
		if pip_on then
			ae.PIP.m = pip_m
			ae.PIP.r = pip_r
			ae.PIP.au = pip_au
			ae.PIP.av = pip_av
		else
			ae.PIP.m = 1
			ae.PIP.au = 0.5
			ae.PIP.av = 0.5
		end
		ae.PIP.a = sw / sh
		return ae.PIP
	end

	local pool = { edges = {} }
	for i = 1, 8 do
		pool[i] = { box = make_slot_wnd(), brk = make_slot_wnd(), dot = make_slot_wnd() }
	end
	for i = 1, 4 do
		pool.edges[i] = make_slot_wnd()
	end

	local cfg = {
		allies = true, allies_range = 50, allies_dot_ratio = 0.7, allies_los = false,
		allies_enemies = true, allies_mutants = true, allies_size = 1, allies_opacity = 1,
		allies_color_companion = 2, allies_color_friend = 1, allies_color_enemy = 5,
		allies_names = false, allies_style = 0, allies_companion_edge = true,
	}
	local lens = { k = 0, ox = 0, oy = 0, roll = 0, dist = 0, zoom = 1, shutter = 0 }

	local function collect_shown()
		local brks, dots, edges = {}, {}, {}
		for i = 1, #pool do
			if pool[i].brk.shown then brks[#brks + 1] = pool[i].brk end
			if pool[i].dot.shown then dots[#dots + 1] = pool[i].dot end
		end
		for i = 1, #pool.edges do
			if pool.edges[i].shown then edges[#edges + 1] = pool.edges[i] end
		end
		return brks, dots, edges
	end

	-- Step A: Unscoped baseline -> 201 (center), 202 (right) get 1x boxes; 205 gets edge dot
	pip_on = false
	for _ = 1, 8 do
		ae.update(pool, cfg, lens, true)
		now_ms = now_ms + 80
	end
	ae.update(pool, cfg, lens, true)
	local u_brks, u_dots, u_edges = collect_shown()
	check(#u_brks == 2, ("unscoped: 2 boxes shown (got %d)"):format(#u_brks))
	check(#u_edges == 1, ("unscoped: off-screen companion edge dot shown (got %d)"):format(#u_edges))
	local unscoped_center_h, unscoped_right_cx, unscoped_right_h
	for _, b in ipairs(u_brks) do
		if math.abs(b.cx - 512) < 5 then
			unscoped_center_h = b.h
		elseif b.cx > 700 then
			unscoped_right_cx = b.cx
			unscoped_right_h = b.h
		end
	end
	check(unscoped_center_h and unscoped_right_cx and unscoped_right_h, "unscoped: found both center and right boxes")

	-- Step B: PiP scope active (4x) ->
	--   201 (inside lens) gets 4x magnified box at center
	--   202 (nearby outside lens on right) STILL gets 1x full-body box at same cx/height
	--   203 (79m > allies_range=50, outside lens) does NOT get a 1x box
	--   204 (150m > dot_dist=140, inside lens) does NOT draw a dot
	--   205 (off-screen companion) does NOT draw an edge dot
	pip_on = true
	now_ms = now_ms + 300 -- force rescan at range = 200m
	ae.update(pool, cfg, lens, true)
	now_ms = now_ms + 80
	ae.update(pool, cfg, lens, true)
	local p_brks, p_dots, p_edges = collect_shown()
	check(#p_dots == 0, ("PiP scoped: zero regular dots shown (got %d)"):format(#p_dots))
	check(#p_edges == 0, ("PiP scoped: zero companion edge dots shown (got %d)"):format(#p_edges))
	check(#p_brks == 2, ("PiP scoped: exactly 2 boxes shown (inside lens + nearby outside lens, not >base_range; got %d)"):format(#p_brks))

	local pip_center_b, pip_right_b
	for _, b in ipairs(p_brks) do
		if math.abs(b.cx - 512) < 5 then
			pip_center_b = b
		elseif b.cx > 700 then
			pip_right_b = b
		end
	end
	check(pip_center_b ~= nil, "PiP scoped: stalker inside lens keeps box")
	if pip_center_b and unscoped_center_h then
		check(pip_center_b.h > unscoped_center_h * 3.0,
			("PiP scoped: in-lens box is magnified (unscoped=%.1f, pip=%.1f)"):format(unscoped_center_h, pip_center_b.h))
	end
	check(pip_right_b ~= nil, "PiP scoped: stalker standing nearby outside lens STILL gets 1x box on right side")
	if pip_right_b and unscoped_right_cx and unscoped_right_h then
		check(math.abs(pip_right_b.cx - unscoped_right_cx) < 1.0 and math.abs(pip_right_b.h - unscoped_right_h) < 1.0,
			("PiP scoped: outside-lens box stays unmagnified 1x (cx=%.1f vs %.1f, h=%.1f vs %.1f)"):format(
				pip_right_b.cx, unscoped_right_cx, pip_right_b.h, unscoped_right_h))
		local px_w = pip_right_b.w / ux
		local px_h = pip_right_b.h / uy
		check(px_h > px_w * 1.5, "PiP scoped: outside-lens 1x box stays tall full-body (not head-tracking)")
	end

	-- Step C: Decoupled gun aim offset (PIP.au = 0.65) while stalker 201 is at screen centre (u=0.50):
	--   In-lens magnified projection misses 201 (0.5 + (0.5 - 0.65)*4 = -0.10, outside lens),
	--   AND outside-lens 1x fallback MUST reject 201 because its 1x center (512, 384) is inside the lens circle!
	pip_au = 0.65
	now_ms = now_ms + 80
	ae.update(pool, cfg, lens, true)
	for _ = 1, 10 do
		now_ms = now_ms + 80
		ae.update(pool, cfg, lens, true)
	end
	local o_brks, o_dots, o_edges = collect_shown()
	local ghost_center = false
	for _, b in ipairs(o_brks) do
		if math.abs(b.cx - 512) < 5 then ghost_center = true end
	end
	check(not ghost_center, "PiP scoped: target behind scope lens circle does NOT draw a ghost 1x box inside the lens")
	check(#o_dots == 0 and #o_edges == 0, "PiP scoped: still zero dots with offset aim")

	-- Step D: Unscoping brings back companion edge dot
	pip_on = false
	pip_au = 0.5
	now_ms = now_ms + 80
	ae.update(pool, cfg, lens, true)
	local _, _, r_edges = collect_shown()
	check(#r_edges == 1, ("unscoping restores companion edge dot (got %d)"):format(#r_edges))

	-- Step E: Outside-lens 1x fade-out past base_range never flashes alpha upward
	pip_on = true
	pip_au = 0.5
	-- Move 202 to 48.9m (just inside base_range=50, on right side of screen)
	npcs[202]._pos:set(25, 0, 42)
	npcs[202]._head:set(25, 1.6, 42)
	npcs[202]._spine:set(25, 1.0, 42)
	for _ = 1, 8 do
		now_ms = now_ms + 80
		ae.update(pool, cfg, lens, true)
	end
	local near_alpha = nil
	for i = 1, #pool do
		if pool[i].brk.shown and pool[i].brk.cx > 700 then
			near_alpha = pool[i].brk._col and pool[i].brk._col.a
		end
	end
	check(near_alpha ~= nil and near_alpha > 0 and near_alpha < 30,
		("outside-lens stalker near base_range (48.9m) has faded alpha (got %s)"):format(tostring(near_alpha)))
	-- Step past base_range to 51.1m -> alpha must not flash upward toward 255
	npcs[202]._pos:set(26, 0, 44)
	npcs[202]._head:set(26, 1.6, 44)
	npcs[202]._spine:set(26, 1.0, 44)
	now_ms = now_ms + 80
	ae.update(pool, cfg, lens, true)
	local past_alpha = 0
	for i = 1, #pool do
		if pool[i].brk.shown and pool[i].brk.cx > 700 then
			past_alpha = pool[i].brk._col and pool[i].brk._col.a or 0
		end
	end
	check(near_alpha and past_alpha <= near_alpha,
		("stepping past base_range does NOT flash alpha upward (%s -> %s)"):format(tostring(near_alpha), tostring(past_alpha)))
end

-- 13. Aim-gated labels: non-companion shows box only when not aimed, box+label when aimed;
--     companion shows box+label at all times while on screen & in LOS, hidden when LOS fails.
do
	local now_ms = 1000
	local sw, sh = 1920, 1080
	local cur_fov = 75
	local cam_pos_v = { x = 0, y = 1.6, z = 0 }
	local cam_dir_v = { x = 0, y = 0, z = 1 }

	local function make_vec(x, y, z)
		local v = { x = x or 0, y = y or 0, z = z or 0 }
		function v:set(nx, ny, nz) self.x, self.y, self.z = nx or 0, ny or 0, nz or 0; return self end
		function v:distance_to(o) local dx, dy, dz = self.x - o.x, self.y - o.y, self.z - o.z; return math.sqrt(dx*dx+dy*dy+dz*dz) end
		function v:distance_to_sqr(o) local dx, dy, dz = self.x - o.x, self.y - o.y, self.z - o.z; return dx*dx+dy*dy+dz*dz end
		return v
	end

	local function make_wnd()
		local w = { shown = false, cx = 0, cy = 0, w = 0, h = 0 }
		return setmetatable(w, { __index = {
			Show = function(self, v) self.shown = v and true or false end,
			SetWndPos = function(self, p) self._px, self._py = p.x, p.y end,
			SetWndSize = function(self, s)
				self.w, self.h = s.x, s.y
				self.cx = (self._px or 0) + s.x * 0.5
				self.cy = (self._py or 0) + s.y * 0.5
			end,
			SetTextureColor = function(self, c) self._col = c end,
			SetTextureRect = function() end,
			InitTexture = function() end,
			SetStretchTexture = function() end,
		} })
	end

	local function make_glyphs(n)
		local g = {}
		for i = 1, n do g[i] = make_wnd() end
		return g
	end

	local function make_slot()
		return {
			box = make_wnd(), brk = make_wnd(), dot = make_wnd(),
			lbl = {
				name = { glyphs = make_glyphs(24) },
				fac  = { glyphs = make_glyphs(20) },
				info = { glyphs = make_glyphs(24) },
			},
		}
	end

	local function any_glyph_shown(line)
		if not line then return false end
		for i = 1, #line.glyphs do
			if line.glyphs[i].shown then return true end
		end
		return false
	end

	local function label_shown(lbl)
		return any_glyph_shown(lbl.name) or any_glyph_shown(lbl.fac) or any_glyph_shown(lbl.info)
	end

	local function make_npc(name, x, y, z, is_companion)
		local pos = make_vec(x, y, z)
		local head = make_vec(x, y + 1.6, z)
		local spine = make_vec(x, y + 1.0, z)
		return {
			_pos = pos, _head = head, _spine = spine,
			_los = true,
			alive = function() return true end,
			position = function() return pos end,
			relation = function() return 0 end,
			has_info = function(_, info) return is_companion and info == "npcx_is_companion" or false end,
			character_name = function() return name end,
			character_community = function() return "stalker" end,
			rank = function() return 500 end,
		}
	end

	-- 301: non-companion off-center (x=8, z=15 -> ~28 deg off camera centre, cos ~ 0.88 < 0.984)
	-- 302: companion off-center (x=-8, z=15 -> ~28 deg off camera centre, cos ~ 0.88 < 0.984)
	local npcs = {
		[301] = make_npc("StalkerBob", 8, 0, 15, false),
		[302] = make_npc("CompanionMax", -8, 0, 15, true),
	}
	local storage = { [301] = { object = npcs[301] }, [302] = { object = npcs[302] } }
	local actor = {
		position = function() return make_vec(0, 0, 0) end,
		see = function(_, obj) return obj._los == true end,
	}

	local function persp_world2ui(v)
		local dx, dy, dz = v.x - cam_pos_v.x, v.y - cam_pos_v.y, v.z - cam_pos_v.z
		-- project relative to cam_dir_v (yaw in XZ plane)
		local fwd_x, fwd_z = cam_dir_v.x, cam_dir_v.z
		local fl = math.sqrt(fwd_x * fwd_x + fwd_z * fwd_z)
		fwd_x, fwd_z = fwd_x / fl, fwd_z / fl
		local right_x, right_z = fwd_z, -fwd_x
		local cz = dx * fwd_x + dz * fwd_z
		local cx = dx * right_x + dz * right_z
		if cz <= 0.1 then return { x = -9999, y = -9999 } end
		local tan_half = math.tan(math.rad(cur_fov) * 0.5)
		local aspect = sw / sh
		local u = 0.5 + 0.5 * (cx / (cz * tan_half * aspect))
		local vv = 0.5 - 0.5 * (dy / (cz * tan_half))
		return { x = u * 1024, y = vv * 768 }
	end

	local ae = setmetatable({
		db = { actor = actor, storage = storage },
		level = { object_by_id = function(id) return npcs[id] end },
		game_object = { enemy = 2, friend = 0, neutral = 1 },
		IsStalker = function() return true end,
		IsMonster = function() return false end,
		utils_obj = {
			safe_bone_pos = function(obj, bone)
				if bone == "bip01_head" then return obj._head end
				if bone == "bip01_spine" then return obj._spine end
				return nil
			end,
		},
		game = { world2ui = persp_world2ui, translate_string = function(s) return s end },
		device = function()
			return {
				width = sw, height = sh, fov = cur_fov,
				cam_pos = make_vec(cam_pos_v.x, cam_pos_v.y, cam_pos_v.z),
				cam_dir = make_vec(cam_dir_v.x, cam_dir_v.y, cam_dir_v.z),
			}
		end,
		zbc_font_metrics = { em = 32, advance = 20, cell_w = 32, cell_h = 40, pad = 4, cols = 16, rows = 16, tex_w = 512, tex_h = 512, first = 33, last = 126 },
		get_console = function() return { get_float = function() return 75 end } end,
		time_global = function() return now_ms end,
		vector = make_vec, vector2 = make_vec, Frect = make_vec,
		GetARGB = function(a, r, g, b) return { a = a, r = r, g = g, b = b } end,
		RegisterScriptCallback = function() end,
	}, { __index = _G })

	local c = assert(loadfile(PATH))
	setfenv(c, ae)
	c()

	local pool = { make_slot(), make_slot(), make_slot(), make_slot() }
	local cfg = {
		allies = true, allies_range = 100, allies_dot_ratio = 0.7, allies_los = true,
		allies_enemies = true, allies_mutants = true, allies_size = 1, allies_opacity = 1,
		allies_color_companion = 2, allies_color_friend = 1, allies_color_enemy = 5,
		allies_names = true, allies_style = 0, allies_companion_edge = false,
	}
	local lens = { k = 0, ox = 0, oy = 0, roll = 0, dist = 0, zoom = 1, shutter = 0 }

	local function find_slot_near(target_cx)
		local best, best_d = nil, 40
		for i = 1, #pool do
			if pool[i].brk.shown then
				local d = math.abs(pool[i].brk.cx - target_cx)
				if d < best_d then best, best_d = pool[i], d end
			end
		end
		return best
	end

	-- Seed last_t with empty storage so dt > 0 on the very first entity-creation frame
	storage[301], storage[302] = nil, nil
	ae.update(pool, cfg, lens, true)
	storage[301] = { object = npcs[301] }
	storage[302] = { object = npcs[302] }
	now_ms = now_ms + 600

	-- Frame 1 (first drawn frame): camera looking straight (0, 0, 1). Neither 301 nor 302 is aimed at.
	ae.update(pool, cfg, lens, true)
	local p_stk = persp_world2ui(npcs[301]._head)
	local p_cmp = persp_world2ui(npcs[302]._head)
	local s_stk = find_slot_near(p_stk.x)
	local s_cmp = find_slot_near(p_cmp.x)
	check(s_stk ~= nil and s_stk.brk.shown, "non-companion not aimed at: bounding box IS shown on frame 1")
	check(s_stk ~= nil and not label_shown(s_stk.lbl), "non-companion not aimed at: label text is HIDDEN")
	check(s_cmp ~= nil and s_cmp.brk.shown, "companion not aimed at: bounding box IS shown on frame 1")
	check(s_cmp ~= nil and label_shown(s_cmp.lbl), "companion not aimed at: label text IS shown on frame 1")

	-- Aim directly at non-companion 301 (x=8, z=15)
	local l301 = math.sqrt(8 * 8 + 15 * 15)
	cam_dir_v.x, cam_dir_v.z = 8 / l301, 15 / l301
	now_ms = now_ms + 80
	ae.update(pool, cfg, lens, true)
	p_stk = persp_world2ui(npcs[301]._head)
	s_stk = find_slot_near(p_stk.x)
	check(s_stk ~= nil and s_stk.brk.shown, "non-companion aimed at: bounding box IS shown")
	check(s_stk ~= nil and label_shown(s_stk.lbl), "non-companion aimed at: label text IS shown")
	check(s_stk ~= nil and any_glyph_shown(s_stk.lbl.name) and any_glyph_shown(s_stk.lbl.fac) and any_glyph_shown(s_stk.lbl.info),
		"non-companion aimed at: name, faction, and info glyphs are all shown")

	-- Look away again -> label fades out smoothly over ~0.25s while box stays
	cam_dir_v.x, cam_dir_v.z = 0, 1
	now_ms = now_ms + 80
	ae.update(pool, cfg, lens, true)
	p_stk = persp_world2ui(npcs[301]._head)
	s_stk = find_slot_near(p_stk.x)
	check(s_stk ~= nil and s_stk.brk.shown and label_shown(s_stk.lbl),
		"looking away from non-companion fades label out smoothly (still visible at 80ms)")
	for _ = 1, 5 do
		now_ms = now_ms + 80
		ae.update(pool, cfg, lens, true)
	end
	s_stk = find_slot_near(p_stk.x)
	check(s_stk ~= nil and s_stk.brk.shown and not label_shown(s_stk.lbl),
		"looking away from non-companion hides label after fade while keeping box visible")

	-- Remembered stalker popping back in: quick ~0.30s re-decode sweep (scrambled at 80ms, decoded by 400ms)
	ae.load_state({ zbc_known = { 301 } })
	storage[301] = { object = npcs[301] }
	storage[302] = { object = npcs[302] }
	now_ms = now_ms + 300
	cam_dir_v.x, cam_dir_v.z = 0, 1
	ae.update(pool, cfg, lens, true)
	-- Look at remembered stalker 301
	cam_dir_v.x, cam_dir_v.z = 8 / l301, 15 / l301
	now_ms = now_ms + 80
	ae.update(pool, cfg, lens, true)
	p_stk = persp_world2ui(npcs[301]._head)
	s_stk = find_slot_near(p_stk.x)
	local mid_text = s_stk and s_stk.lbl.name.text
	check(mid_text ~= nil and mid_text ~= "STALKERBOB",
		("remembered stalker popping back in plays quick re-decode (got %s at 80ms)"):format(tostring(mid_text)))
	for _ = 1, 5 do
		now_ms = now_ms + 80
		ae.update(pool, cfg, lens, true)
	end
	s_stk = find_slot_near(p_stk.x)
	check(s_stk ~= nil and s_stk.lbl.name.text == "STALKERBOB",
		("remembered stalker finishes quick re-decode cleanly (got %s)"):format(tostring(s_stk and s_stk.lbl.name.text)))
	-- Look away again before companion LOS test
	cam_dir_v.x, cam_dir_v.z = 0, 1

	-- Companion failing LOS: loses both box and label after LOS grace expires
	npcs[302]._los = false
	for _ = 1, 25 do
		now_ms = now_ms + 100
		ae.update(pool, cfg, lens, true)
	end
	p_cmp = persp_world2ui(npcs[302]._head)
	s_cmp = find_slot_near(p_cmp.x)
	check(s_cmp == nil, "companion failing LOS: box is hidden")
	local any_cmp_lbl = false
	for i = 1, #pool do
		if not pool[i].brk.shown and label_shown(pool[i].lbl) then any_cmp_lbl = true end
	end
	check(not any_cmp_lbl, "companion failing LOS: label is hidden when box is hidden")
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_allies_label_test: all checks passed")
