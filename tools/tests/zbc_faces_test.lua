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

if failures > 0 then
	print(failures .. " check(s) failed")
	os.exit(1)
end
print("zbc_faces_test: all checks passed")
