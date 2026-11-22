-- Tests the face square maths in gamedata/scripts/zbc_faces.script: the square around a face is a
-- whole, even number of mosaic blocks wide, near faces get BLOCKS blocks, far faces keep blocks at
-- least MIN_BLOCK_PX tall, and bad input is rejected.
--
-- Usage (from the repo root): lua tools/tests/zbc_faces_test.lua

local PATH = "gamedata/scripts/zbc_faces.script"

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
local sq = rawget(env, "face_square")
check(type(sq) == "function", "face_square exists")

local function near(a, b) return math.abs(a - b) < 1e-9 end

if type(sq) == "function" then
	local BLOCKS, MIN_PX, MIN_FACE = env.BLOCKS, env.MIN_BLOCK_PX, env.MIN_FACE_PX
	check(BLOCKS % 2 == 0, "BLOCKS is even")

	-- near face at 1080p: half side 0.1 screen heights (216 px across) -> BLOCKS blocks
	local half, blk = sq(0.5, 0.5, 0.5, 0.4, 16 / 9, 1080)
	check(near(half, 0.1), ("near face keeps its size, got %s"):format(tostring(half)))
	check(near(blk, 0.2 / BLOCKS), ("near face: %d blocks across, got block %s"):format(BLOCKS, tostring(blk)))

	-- the offset may point sideways (camera roll): u distance counts in screen heights via the aspect
	local half_r = sq(0.5, 0.5, 0.5 + 0.1 / (16 / 9), 0.5, 16 / 9, 1080)
	check(near(half_r, 0.1), "sideways offset measured in screen heights")

	-- mid face: 30 px across at 1080p -> blocks floor at MIN_BLOCK_PX
	local half_m, blk_m = sq(0.5, 0.5, 0.5, 0.5 - 15 / 1080, 16 / 9, 1080)
	check(near(blk_m, MIN_PX / 1080), "mid face: block floored to MIN_BLOCK_PX")
	check(half_m >= 2 * blk_m - 1e-12, "mid face: square at least 4 blocks wide")

	-- small face: 8 px across -> 4 blocks, and the square doesn't grow past the face
	local half_s, blk_s = sq(0.5, 0.5, 0.5, 0.5 - 4 / 1080, 16 / 9, 1080)
	check(half_s and half_s <= 4 / 1080 + 1e-12 and near(2 * half_s / blk_s, 4), "small face: 4 blocks, no bigger than the face")

	-- tiny face (a far NPC without a scope): left alone
	check(sq(0.5, 0.5, 0.5, 0.5 - 2 / 1080, 16 / 9, 1080) == nil, "face under MIN_FACE_PX is not pixelated")
	-- the same NPC through a scope fills a big part of the screen: pixelated with BLOCKS blocks
	local half_z, blk_z = sq(0.5, 0.5, 0.5, 0.25, 16 / 9, 1080)
	check(near(half_z, 0.25) and near(2 * half_z / blk_z, BLOCKS), "scoped face: BLOCKS blocks across")

	-- always a whole, even number of blocks across
	for i = 1, 200 do
		local d = i * 0.0013
		local h, b = sq(0.3, 0.6, 0.3, 0.6 - d, 1.6, 900)
		check((h == nil) == (d * 900 < MIN_FACE), ("d=%.4f: only faces under MIN_FACE_PX are skipped"):format(d))
		if h then
			local n = 2 * h / b
			check(math.abs(n - math.floor(n + 0.5)) < 1e-6 and math.floor(n + 0.5) % 2 == 0,
				("d=%.4f: %.4f blocks across is not a whole even number"):format(d, n))
			check(h >= d - 1e-9 or n == 4, ("d=%.4f: square covers the face"):format(d))
		end
	end

	-- bad input
	check(sq(0.5, 0.5, 0.5, 0.5, 16 / 9, 1080) == nil, "zero size is rejected")
	check(sq(0 / 0, 0.5, 0.5, 0.4, 16 / 9, 1080) == nil, "NaN is rejected")
end

-- packing for the shader: mirrors zbc_face_unpack in shaders/r3/zbc_lens.h
local pack_face, pack_rows = rawget(env, "pack_face"), rawget(env, "pack_rows")
check(type(pack_face) == "function" and type(pack_rows) == "function", "packing functions exist")
if type(pack_face) == "function" and type(pack_rows) == "function" then
	local function unpack16(p)
		return math.floor(p / 65536) / 65535, (p % 65536) / 65535
	end
	local function unpack(a, b)
		local qu, qv = unpack16(a)
		local qh, qb = unpack16(b)
		return qu * env.POS_SPAN + env.POS_MIN, qv * env.POS_SPAN + env.POS_MIN, qh * env.SIZE_SPAN, qb * env.SIZE_SPAN
	end
	local step = 1 / 2160 / 4   -- a quarter pixel at 4K
	for _, f in ipairs({ { 0.5, 0.5, 0.1, 0.025 }, { -0.2, 1.2, 0.003, 0.0023 }, { 0.013, 0.987, 0.74, 0.18 } }) do
		local a, b = pack_face(f[1], f[2], f[3], f[4])
		check(a >= 0 and a < 4294967296 and b >= 0 and b < 4294967296 and a % 1 == 0 and b % 1 == 0, "packed values are uint32")
		local u, v, h, k = unpack(a, b)
		check(math.abs(u - f[1]) < step and math.abs(v - f[2]) < step and math.abs(h - f[3]) < step and math.abs(k - f[4]) < step,
			("round trip within a quarter pixel at 4K: %s"):format(table.concat(f, ", ")))
	end
	local a = pack_face(9, -9, 0 / 0, 2)
	check(a == 65535 * 65536 + 0, "out-of-range centre clamps, NaN packs as 0")

	-- 2 faces per row; an odd count leaves the last half empty; rows past the count are dropped
	local list = {}
	for i = 1, 64 do list[i] = { i / 100, 0.5, 0.05, 0.01 } end
	local out = { {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {} }
	check(pack_rows(list, 64, out) == 32 and #out == 32, "64 faces fill 32 rows")
	check(pack_rows(list, 5, out) == 3 and #out == 3, "5 faces: 3 rows, the rest dropped")
	check(out[3][3] == 0 and out[3][4] == 0, "odd count: last half of the last row is empty")
	local u = unpack(out[3][1], out[3][2])
	check(math.abs(u - 0.05) < step, "face 5 sits in the first half of row 3")
end

-- 12-bit AABB packing for bus_zbc_faces.yzw (matches HLSL unpacking in shaders/r3/zbc_lens.h)
local pack_bounds = rawget(env, "pack_bounds")
check(type(pack_bounds) == "function", "pack_bounds exists")
if type(pack_bounds) == "function" then
	local function unpack_hlsl(py, pz)
		local max_u = math.floor(py * (1.0 / 4096.0))
		local min_u = (py - max_u * 4096.0) * (1.0 / 4095.0)
		max_u = max_u * (1.0 / 4095.0)
		local max_v = math.floor(pz * (1.0 / 4096.0))
		local min_v = (pz - max_v * 4096.0) * (1.0 / 4095.0)
		max_v = max_v * (1.0 / 4095.0)
		return min_u, min_v, max_u, max_v
	end

	local c0, py0, pz0, pw0 = pack_bounds({}, 0, 16 / 9)
	check(c0 == 0 and py0 == 0 and pz0 == 0 and pw0 == 0, "empty face list packs as (0, 0, 0, 0)")

	for _, asp in ipairs({ 4 / 3, 16 / 9, 21 / 9, 32 / 9 }) do
		local faces = {
			{ 0.25, 0.35, 0.08, 0.02 },
			{ 0.72, 0.61, 0.12, 0.03 },
		}
		local cnt, py, pz, pw = pack_bounds(faces, #faces, asp)
		check(cnt == 2 and pw == 1.0, ("aspect %.2f: count=2, w=1.0"):format(asp))
		check(py >= 0 and py <= 16777215 and pz >= 0 and pz <= 16777215, "packed bounds fit in exact 24-bit float32 integers")
		local min_u, min_v, max_u, max_v = unpack_hlsl(py, pz)
		for _, f in ipairs(faces) do
			local hu = f[3] / asp
			local hv = f[3]
			check(min_u <= math.max(0, f[1] - hu - 0.002) + 1e-6, "unpacked min_u encloses padded face left")
			check(max_u >= math.min(1, f[1] + hu + 0.002) - 1e-6, "unpacked max_u encloses padded face right")
			check(min_v <= math.max(0, f[2] - hv - 0.002) + 1e-6, "unpacked min_v encloses padded face top")
			check(max_v >= math.min(1, f[2] + hv + 0.002) - 1e-6, "unpacked max_v encloses padded face bottom")
		end
	end

	-- clamping at 0.0 and 1.0 edges
	local cnt_e, py_e, pz_e, pw_e = pack_bounds({ { -0.1, 1.1, 0.2, 0.05 }, { 0.9, 0.0, 0.2, 0.05 } }, 2, 16 / 9)
	local eu0, ev0, eu1, ev1 = unpack_hlsl(py_e, pz_e)
	check(cnt_e == 2 and pw_e == 1.0 and eu0 == 0 and ev0 == 0 and eu1 == 1 and ev1 == 1, "edge clamping covers [0, 1]")
end

-- which heads are blurred: configs\zbc_face_models.ltx [skip] / [only]
local fa, mk = rawget(env, "face_allowed"), rawget(env, "model_key")
check(type(fa) == "function" and type(mk) == "function", "model list functions exist")
if type(fa) == "function" and type(mk) == "function" then
	check(mk("Meshes/Actors/Stalker_Neutral/stalker_neutral_1.ogf") == "actors\\stalker_neutral\\stalker_neutral_1", "model names are normalised")
	local none = { skip = {}, only = {} }
	check(fa("actors\\a\\b", none), "empty lists: everyone blurred")
	local skip = { skip = { ["actors\\exo\\exo_1"] = true }, only = {} }
	check(not fa("actors/exo/exo_1.ogf", skip) and fa("actors\\a\\b", skip), "a skipped model is not blurred, others are")
	local only = { skip = {}, only = { ["actors\\a\\b"] = true } }
	check(fa("actors\\a\\b", only) and not fa("actors\\c\\d", only), "an [only] list limits blurring to it")
	local both = { skip = { ["actors\\a\\b"] = true }, only = { ["actors\\a\\b"] = true } }
	check(not fa("actors\\a\\b", both), "skip wins over only")
end

-- update() edge cases: close-up off-center face, -side projection fallback, and lying dead NPC
do
	local npcs = {}
	local function mkvec(x, y, z)
		return { x = x or 0, y = y or 0, z = z or 0, set = function(self, nx, ny, nz) self.x, self.y, self.z = nx, ny, nz; return self end, distance_to_sqr = function(a, b) local dx, dy, dz = a.x - b.x, a.y - b.y, a.z - b.z; return dx*dx + dy*dy + dz*dz end }
	end
	local fenv
	fenv = setmetatable({
		time_global = function() return 1000 end,
		vector = function() return mkvec(0, 0, 0) end,
		device = function()
			return {
				width = 1920, height = 1080, fov = 75,
				cam_pos = { x = 0, y = 1.6, z = 0 },
				cam_dir = { x = 0, y = 0, z = 1 },
			}
		end,
		IsStalker = function() return true end,
		db = { storage = {} },
		level = { object_by_id = function(id) return npcs[id] end },
		utils_obj = { safe_bone_pos = function(obj) return obj._head end },
		zbc_allies = { los_point = function() return true end },
		game = {
			world2ui = function(v)
				-- simulate +side unprojectable near the right frustum edge (x > 0.99)
				if v.x > 0.99 then return { x = -9999, y = -9999 } end
				return { x = v.x * 1024, y = (0.5 - (v.y - 1.6)) * 768 }
			end,
		},
	}, { __index = _G })
	local fchunk = assert(loadfile(PATH))
	setfenv(fchunk, fenv)
	fchunk()

	-- 1) Close-up off-screen-center NPC (cu = -0.15, half = 0.30 -> overlaps [0,1])
	-- 2) Dead NPC lying with origin at z = -0.8 (behind cam) but head at z = 0.9, y = 1.53 (head + HEAD_UP = 1.60)
	-- 3) Edge NPC at x = 0.92: +side (0.92 + 0.17 = 1.09 > 0.99) fails to project, -side (0.75) succeeds
	npcs[10] = {
		alive = function() return true end,
		position = function() return mkvec(-0.15, 0, 1.0) end,
		_head = mkvec(-0.15, 1.53, 1.0),
	}
	npcs[20] = {
		alive = function() return false end,
		position = function() return mkvec(0.5, 0.0, -0.8) end,
		_head = mkvec(0.5, 1.53, 0.9),
	}
	npcs[30] = {
		alive = function() return true end,
		position = function() return mkvec(0.92, 0, 1.2) end,
		_head = mkvec(0.92, 1.53, 1.2),
	}
	fenv.db.storage[10] = { object = npcs[10] }
	fenv.db.storage[20] = { object = npcs[20] }
	fenv.db.storage[30] = { object = npcs[30] }

	local actor = { position = function() return mkvec(0, 0, 0) end, see = function() return true end }
	-- first update seeds los timers; advance time past LOS_INTERVAL (0.1s) so visible() evaluates
	fenv.update(actor, 64)
	fenv.time_global = function() return 1200 end
	local rows, n = fenv.update(actor, 64)
	check(n == 3, "update() includes close-up off-center, lying dead NPC, and -side fallback NPC, got n=" .. tostring(n))
	if n == 3 then
		local found_closeup, found_dead, found_edge = false, false, false
		for i = 1, n do
			if math.abs(rows[i][1] - (-0.15)) < 1e-6 then found_closeup = true end
			if math.abs(rows[i][1] - 0.5) < 1e-6 then found_dead = true end
			if math.abs(rows[i][1] - 0.92) < 1e-6 then found_edge = true end
		end
		check(found_closeup, "close-up face at cu=-0.15 is kept")
		check(found_dead, "dead NPC with origin behind cam and head in front is kept")
		check(found_edge, "edge face with unprojectable +side falls back to -side")
	end
end

-- Dual-view 3DSS PiP projection: magnified inside lens + 1x outside lens + occluded behind lens
do
	local npcs = {}
	local function mkvec(x, y, z)
		return { x = x or 0, y = y or 0, z = z or 0, set = function(self, nx, ny, nz) self.x, self.y, self.z = nx, ny, nz; return self end, distance_to_sqr = function(a, b) local dx, dy, dz = a.x - b.x, a.y - b.y, a.z - b.z; return dx*dx + dy*dy + dz*dz end }
	end
	local P = { m = 4, r = 0.12, a = 16 / 9, au = 0.56, av = 0.5 }
	local fenv
	fenv = setmetatable({
		time_global = function() return 1000 end,
		vector = function() return mkvec(0, 0, 0) end,
		device = function()
			return {
				width = 1920, height = 1080, fov = 75,
				cam_pos = { x = 0, y = 1.6, z = 0 },
				cam_dir = { x = 0, y = 0, z = 1 },
			}
		end,
		IsStalker = function() return true end,
		db = { storage = {} },
		level = { object_by_id = function(id) return npcs[id] end },
		utils_obj = { safe_bone_pos = function(obj) return obj._head end },
		zbc_allies = {
			PIP = P,
			pip_refresh = function() return P end,
			pip_active = function(p) return (p or P).m > 1.01 end,
			pip_map = function(u, v, p)
				p = p or P
				local mu, mv = 0.5 + (u - p.au) * p.m, 0.5 + (v - p.av) * p.m
				local dx, dy = (mu - 0.5) * p.a, mv - 0.5
				return mu, mv, dx * dx + dy * dy <= p.r * p.r
			end,
			los_point = function() return true end,
		},
		game = {
			world2ui = function(v)
				if v.z <= 0.05 then return { x = -9999, y = -9999 } end
				local u = 0.5 + (v.x / v.z) * 0.5
				local vv = 0.5 - (v.y - 1.6) / v.z
				return { x = u * 1024, y = vv * 768 }
			end,
		},
	}, { __index = _G })
	local fchunk = assert(loadfile(PATH))
	setfenv(fchunk, fenv)
	fchunk()

	-- 101: Far face inside PiP lens (ru=0.57 -> mu=0.54, in_lens=true)
	npcs[101] = {
		alive = function() return true end,
		position = function() return mkvec(2.8, 0, 20) end,
		_head = mkvec(2.8, 1.53, 20),
	}
	-- 102: Nearby face outside PiP lens on right side (ru=0.80, 1x unmagnified)
	npcs[102] = {
		alive = function() return true end,
		position = function() return mkvec(1.2, 0, 2.0) end,
		_head = mkvec(1.2, 1.53, 2.0),
	}
	-- 103: Raw 1x face behind the opaque/magnified lens interior (ru=0.50 -> mu=0.26 out of lens, raw 1x inside lens circle)
	npcs[103] = {
		alive = function() return true end,
		position = function() return mkvec(0.0, 0, 2.0) end,
		_head = mkvec(0.0, 1.53, 2.0),
	}
	fenv.db.storage[101] = { object = npcs[101] }
	fenv.db.storage[102] = { object = npcs[102] }
	fenv.db.storage[103] = { object = npcs[103] }

	local actor = { position = function() return mkvec(0, 0, 0) end, see = function() return true end }
	fenv.update(actor, 64)
	fenv.time_global = function() return 1200 end
	local rows, n = fenv.update(actor, 64)
	check(n == 2, "PiP dual-view keeps far in-lens face and nearby 1x face, skips face behind lens, got n=" .. tostring(n))
	if n == 2 then
		local far_row, near_row
		for i = 1, n do
			if math.abs(rows[i][1] - 0.54) < 1e-6 then far_row = rows[i] end
			if math.abs(rows[i][1] - 0.80) < 1e-6 then near_row = rows[i] end
		end
		check(far_row ~= nil, "far face inside PiP lens is placed at magnified cu=0.54")
		check(near_row ~= nil, "nearby face outside PiP lens is placed at 1x cu=0.80")
		if far_row then
			local exp_half = fenv.face_square(0.54, 0.5, 0.54 + 4 * 0.5 * (0.17 / 20), 0.5, 16 / 9, 1080)
			check(near(far_row[3], exp_half), "in-lens face square is magnified")
		end
		if near_row then
			local exp_half = fenv.face_square(0.80, 0.5, 0.80 + 0.5 * (0.17 / 2.0), 0.5, 16 / 9, 1080)
			check(near(near_row[3], exp_half), "outside-lens face square is 1x unmagnified")
		end
	end

	-- predict() must not extrapolate across a 1x <-> magnified mode switch even for small deltas
	local pu, pv = fenv.predict({ 0.50, 0.50, false }, 0.52, 0.50, true)
	check(near(pu, 0.52) and near(pv, 0.50), "predict() does not extrapolate across 1x <-> magnified switch")
end

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_faces_test: all checks passed")
