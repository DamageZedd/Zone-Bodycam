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
	check(ir(30, 75) == math.huge and ir(50, 75) == math.huge, "within 50 m: identified at once")
	-- the mod: 100 / ((d^2 - 2500) * 0.1) / fov * 20 * 0.2 per 0.2 s tick
	local per_tick = 100 / ((60 * 60 - 2500) * 0.1) / 75 * 20 * 0.2
	check(near(ir(60, 75), per_tick * 5), "60 m matches the mod's per-tick gain x 5 ticks a second")
	check(ir(100, 75) < ir(60, 75), "further away identifies slower")
	check(ir(100, 18) > ir(100, 75), "through a scope (smaller fov) identifies faster")
	check(ir(100, nil) > 0, "missing fov falls back to 75")
	local t_full = 0.5
	check(rs(t_full, true, 300, false, 75) == 1, "known stalker: quick decode wherever they are")
	check(rs(t_full, false, 40, false, 75) == 1, "near stalker: quick decode even when not looked at")
	check(rs(t_full, false, 120, false, 75) == 0, "far stalker you are not looking at: paused")
	local s = rs(t_full, false, 120, true, 75)
	check(s > 0 and s < 1 and near(s, ir(120, 75) * t_full), "far stalker you look at: decodes at the mod's rate")
	check(rs(t_full, false, 51, true, 1) == 1, "never faster than the quick decode")
	-- seconds to identify at 100 m: about 28 s plain, about 7 s through a 4x scope
	local plain, scoped = 1 / ir(100, 75), 1 / ir(100, 75 / 4)
	check(plain > 25 and plain < 31 and scoped > 6 and scoped < 8, ("100 m: %.1f s plain, %.1f s scoped"):format(plain, scoped))
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
		GetARGB = function() return 0 end,
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
	for step = 1, 5 do
		now_ms = now_ms + 80
		ae.update(pool, cfg, lens, true)
	end
	check(ae.is_known_id(42) == true, "nearby NPC becomes known")

	-- Hiding HUD (inventory/PDA) preserves known
	ae.update(pool, cfg, lens, false)
	check(ae.is_known_id(42) == true, "visible == false preserves known")

	-- actor_on_first_update clears known
	cbs.actor_on_first_update()
	check(ae.is_known_id(42) == false and ae.id_progress_for(42) == nil, "actor_on_first_update clears known and id_progress")

	-- Re-identify, then actor_on_net_destroy clears known
	now_ms = now_ms + 80
	ae.update(pool, cfg, lens, true)
	for step = 1, 5 do
		now_ms = now_ms + 80
		ae.update(pool, cfg, lens, true)
	end
	check(ae.is_known_id(42) == true, "re-identified NPC is known")
	cbs.actor_on_net_destroy()
	check(ae.is_known_id(42) == false and ae.id_progress_for(42) == nil, "actor_on_net_destroy clears known and id_progress")
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
		GetARGB = function() return 0 end,
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
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_allies_label_test: all checks passed")
