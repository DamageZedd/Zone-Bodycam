// Zone Bodycam - Modern-Gritty Axon lens, CMOS sensor, and motion-reactive vignette model.
// Included by postprocess.ps / postprocess_cm.ps, i.e. the display-resolution post chain that the
// Slop-Ray engine runs AFTER DLSS/FSR reconstruction, so the warp is never fed to the upscaler.
// Values come from scripts\zbc_bodycam.script through private Shader Bus lanes. All-zero
// bus_zbc_motion means "off" and the post chain is untouched (main menu, no actor, mod disabled).
#ifndef ZBC_LENS_H
#define ZBC_LENS_H

uniform float4 bus_zbc_motion;   // x: intensity 0..1  y/z: world shift (screen heights)  w: world roll (rad)
uniform float4 bus_zbc_lens;     // x: barrel k1  y: radial CA  z: zoom  w: peripheral edge softness (0..1)
uniform float4 bus_zbc_edge;     // x: edge radius (0.4..1.35, negative: housing off)  y: edge softness (>0)  z: optical vignette (0..1)  w: edge shape (0=circle .. 1=screen)
uniform float4 bus_zbc_extra;    // x: vignette follow scale  y: sharpen (0..1)  z: CMOS grain (0..1)  w: >=0.5 image, <0.5 HUD ring
uniform float4 bus_zbc_vig;      // x/y: independent vignette & housing center offset (screen heights)  z: dynamic tightening (0..1)  w: housing/vignette roll (rad)
uniform float4 bus_zbc_vig_occ;  // x: horizontal chest/shoulder occlusion (-1 left .. +1 right)  y: vertical rig/chin occlusion (-1 top .. +1 bottom)  z: occlusion strength (0..1+)  w: superellipse power (2.0..6.0)
uniform float4 bus_zbc_sensor;   // x: highlight blowout & auto-exposure punch (0..1)  y: digital compression crispness (0..1)  z: signed rolling-shutter horizontal shear  w: CMOS color grade (0..1)

// Face pixelation (scripts\zbc_faces.script). Squares in rendered-image uv, independent of the lens.
uniform float4 bus_zbc_faces;    // x: number of faces in use (0..64), y/z: packed 12-bit union AABB (u, v), w: >0.5 if valid

// Camera effects (scripts\zbc_fx.script), independent of the lens.
uniform float4 bus_zbc_glitch;   // x: interference 0..1 (with its swells)  y: spikes and hit bursts 0..1  z: time of death (timers.x clock, 0 alive)  w: seconds since death on the real clock
uniform float4 bus_zbc_ir;       // x: low-light (infrared) mix 0..1  y: auto-exposure gain (0 = off, 1 = neutral)  z: unused
uniform float4 bus_zbc_dirt;     // x..w: hit times of up to 4 blood splatters on the lens (timers.x clock, 0 empty)
uniform float4 bus_zbc_blood;    // x..w: how far each splatter's drips have run (1 at ~14 s, up to 3)

#define ZBC_INTENSITY (saturate(bus_zbc_motion.x))
#define ZBC_ACTIVE    (bus_zbc_motion.x > 0.0005)
#define ZBC_FACES     (bus_zbc_faces.x > 0.5)
#define ZBC_FX        (bus_zbc_glitch.x + bus_zbc_glitch.y + bus_zbc_glitch.z + dot(bus_zbc_dirt, 1.0) > 0.0005)

// width / height of the display
float2 zbc_aspect() { return float2(max(screen_res.x * screen_res.w, 0.1), 1.0); }

// Clock for animated effects. timers.x counts seconds since the game started and float32 loses the
// fraction once it is large, so a hash of floor(timers.x * 24) stops changing after about 15 minutes
// and the "per-frame" noise freezes. Everything animated runs on this clock, wrapped every 10 minutes
// (one frame jumps there), and every hash takes small inputs.
// After death the clock also runs on real time (glitch.w), since a death screen mod can stop game time
// (time_factor 0) and timers.x with it; while game time runs the extra is ~0.
#define ZBC_TWRAP 600.0
float zbc_death_lag() { return (bus_zbc_glitch.z > 0.0) ? max(bus_zbc_glitch.w - (timers.x - bus_zbc_glitch.z), 0.0) : 0.0; }
float zbc_time() { return fmod(max(timers.x, 0.0) + zbc_death_lag(), ZBC_TWRAP); }
float zbc_tstep(float rate) { return floor(zbc_time() * rate); }   // frame counter at rate Hz

// 2D -> 1D hash in [0, 1), safe for inputs up to ~1e5
float zbc_hash(float2 p)
{
	float3 p3 = frac(float3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return frac((p3.x + p3.y) * p3.z);
}

// 3D -> 1D hash, for noise that changes per pixel AND per frame (x, y, frame)
float zbc_hash13(float3 p3)
{
	p3  = frac(p3 * 0.1031);
	p3 += dot(p3, p3.zyx + 31.32);
	return frac((p3.x + p3.y) * p3.z);
}

// 3D -> 3D hash
float3 zbc_hash33(float3 p3)
{
	p3  = frac(p3 * float3(0.1031, 0.1030, 0.0973));
	p3 += dot(p3, p3.yxz + 33.33);
	return frac((p3.xxy + p3.yxx) * p3.zyx);
}

// Vectorized 2D -> 3D hash in [0, 1) for decorrelated luma + chroma sensor grain
float3 zbc_hash3(float2 p)
{
	float3 p3 = frac(float3(p.xyx) * float3(0.1031, 0.1030, 0.0973));
	p3 += dot(p3, p3.yxz + 33.33);
	return frac((p3.xxy + p3.yzz) * p3.zyx);
}

// Snaps src to the centre of its mosaic block when it falls inside face f. rcp_ax: 1 / aspect.
bool zbc_face_snap_one(float4 f, inout float2 src, float rcp_ax)
{
	float2 blk     = float2(f.w * rcp_ax, f.w);
	float2 half_sz = float2(f.z * rcp_ax, f.z);
	float2 d       = src - f.xy;
	if (f.w <= 0.0 || abs(d.x) >= half_sz.x || abs(d.y) >= half_sz.y)
		return false;
	src = f.xy + (floor(d / blk) + 0.5) * blk;
	return true;
}

// The faces arrive as a uint4 array, which exes older than Shader Bus 7 can't read (see zbc_osd.h),
// so on those the faces are simply not pixelated.
#if defined(SHADER_BUS) && SHADER_BUS >= 7
#define ZBC_FACE_ROWS 32
// two faces per row; per face two uints of 16-bit halves: (centre u | centre v), (half side | block),
// centres -0.25..1.25 uv, sizes 0..0.75 screen heights (pack_face in scripts\zbc_faces.script)
uniform uint4 bus_zbc_face_rows[ZBC_FACE_ROWS];

float4 zbc_face_unpack(uint2 p)
{
	float4 q = float4(p.x >> 16u, p.x & 0xFFFFu, p.y >> 16u, p.y & 0xFFFFu) / 65535.0;
	return float4(q.xy * 1.5 - 0.25, q.zw * 0.75);
}

// Pixelates faces: true when src was snapped to a mosaic block.
bool zbc_face_snap(inout float2 src)
{
	bool hit = false;
	[branch] if (ZBC_FACES)
	{
		bool in_aabb = true;
		if (bus_zbc_faces.w > 0.5)
		{
			float py    = bus_zbc_faces.y, pz = bus_zbc_faces.z;
			float max_u = floor(py * (1.0 / 4096.0));
			float min_u = (py - max_u * 4096.0) * (1.0 / 4095.0);
			max_u      *= (1.0 / 4095.0);
			float max_v = floor(pz * (1.0 / 4096.0));
			float min_v = (pz - max_v * 4096.0) * (1.0 / 4095.0);
			max_v      *= (1.0 / 4095.0);
			in_aabb     = !(src.x < min_u || src.x > max_u || src.y < min_v || src.y > max_v);
		}
		[branch] if (in_aabb)
		{
			float rcp_ax = 1.0 / zbc_aspect().x;
			uint  n      = min((uint)bus_zbc_faces.x, ZBC_FACE_ROWS * 2u);
			[loop] for (uint i = 0u; i < n; i++)
			{
				uint4 row = bus_zbc_face_rows[i >> 1u];
				uint2 p   = (i & 1u) ? row.zw : row.xy;
				if (zbc_face_snap_one(zbc_face_unpack(p), src, rcp_ax))
				{
					hit = true;
					break;
				}
			}
		}
	}
	return hit;
}
#else
bool zbc_face_snap(inout float2 src) { return false; }
#endif

// Lens off: plain sample with the faces pixelated.
float3 zbc_plain_sample(Texture2D tex, float2 uv)
{
	zbc_face_snap(uv);
	return tex.SampleLevel(smp_rtlinear, uv, 0).rgb;
}

//------------------------------------------------------------------------------------------------
// Interference (emissions, psy, radiation, anomalies, hits) and the death glitch
//------------------------------------------------------------------------------------------------

// seconds since death, or -1 while alive: the game clock, or the real clock if game time stopped
float zbc_death_age() { return (bus_zbc_glitch.z > 0.0) ? max(max(timers.x - bus_zbc_glitch.z, 0.0), bus_zbc_glitch.w) : -1.0; }

// death: breaks up within 0.25 s, with the signal stuttering back for moments until it collapses
float zbc_death_glitch(float e)
{
	float dip = step(zbc_hash(float2(floor(e * 9.0), 41.0)), 0.3) * (1.0 - smoothstep(0.55, 0.75, e));
	return saturate(e / 0.25) * (1.0 - 0.65 * dip);
}

// How broken the picture is now, 0..1. While alive the script sends the level from its sources with
// their swells and random spikes (zbc_fx.script); after death the shader times it all itself.
float zbc_glitch_amount()
{
	float e = zbc_death_age();
	if (e >= 0.0)
		return zbc_death_glitch(e);
	return saturate(max(bus_zbc_glitch.x, bus_zbc_glitch.y));
}

//------------------------------------------------------------------------------------------------
// Digital codec breakdown: what a body camera's H.264 stream does when the signal fails. This pass
// has no previous frame, so damaged blocks show other parts of the current picture.
//   - slice errors: from a random macroblock to the end of its row the blocks are wrong
//   - single bad blocks: shuffled, smeared sideways, flat with a stuck DCT pattern, or off-colour
//   - broken frame (strong interference): below a random row the last good line smears down, or
//     the picture is the flat green of an empty YUV frame
//   - starved bitrate (strongest spikes): the whole picture drops to big blocks
// The grid is in screen pixels (16 at 1080p), the same in the uv and colour stages.
//------------------------------------------------------------------------------------------------

float zbc_mb_px() { return max(floor(16.0 * screen_res.y / 1080.0 + 0.5), 8.0); }

struct zbc_cell
{
	float2 blk;    // macroblock coordinates
	float  bad;    // 1: this block is damaged
	float  kind;   // 0..1: how (one way along a whole slice)
	float  seed;   // random per damage event
	float  cut;    // >0: in a broken frame, 1 + the last good block row
	float  fill;   // 1: the broken frame is green, 0: smeared
	float  starve; // >0: block size of a starved frame, in pixels
};

zbc_cell zbc_codec_cell(float2 uv, float g)
{
	zbc_cell o;
	float  mb   = zbc_mb_px();
	o.blk       = floor(uv * screen_res.xy / mb);
	float  cols = ceil(screen_res.x / mb);
	float  tf   = zbc_time() * 15.0;
	// a slice error holds for ~3 frames; rows are staggered so they don't all change together
	float  tr    = floor((tf + zbc_hash(float2(o.blk.y, 7.0)) * 3.0) / 3.0);
	float  tb    = floor(tf * 0.5);
	float  start = floor(zbc_hash(float2(o.blk.y + 0.5, tr + 0.5)) * cols);
	float  ps    = 0.3 * pow(saturate((g - 0.25) / 0.75), 2.0);   // no slices in a light psy flicker
	float  slice = (zbc_hash(float2(o.blk.y, tr)) < ps && o.blk.x >= start) ? 1.0 : 0.0;
	float  one   = (zbc_hash13(float3(o.blk, tb)) < 0.02 * pow(g, 2.5)) ? 1.0 : 0.0;
	o.bad  = max(slice, one);
	o.seed = (slice > 0.5) ? zbc_hash(float2(o.blk.y + 0.25, tr + 2.3)) : zbc_hash13(float3(o.blk, tb + 0.37));
	o.kind = (slice > 0.5) ? zbc_hash(float2(o.blk.y + 0.75, tr + 1.7)) : zbc_hash13(float3(o.blk + 0.5, tb));
	// broken frame, ~2 frames at a time, only once the interference is strong
	float  tc  = floor(tf * 0.5);
	float  pc  = 0.22 * pow(saturate((g - 0.35) / 0.65), 2.0);
	float  row = floor(lerp(0.2, 0.9, zbc_hash(float2(tc, 93.0))) * screen_res.y / mb);
	o.cut  = (zbc_hash(float2(tc, 91.0)) < pc && o.blk.y > row) ? 1.0 + row : 0.0;
	o.fill = step(zbc_hash(float2(tc, 95.0)), 0.4);
	float  pst = 0.30 * saturate((g - 0.7) / 0.3);
	o.starve = (zbc_hash(float2(tc, 97.0)) < pst) ? mb * lerp(0.5, 1.5, zbc_hash(float2(tc, 98.0))) : 0.0;
	return o;
}

// A stuck DCT coefficient: the cosine stripes of one 8x8 basis pattern (-1..1). p: screen pixels.
float zbc_dct(float2 p, float seed)
{
	float  hb = max(zbc_mb_px() * 0.5, 4.0);
	float2 x  = floor(frac(p / hb) * 8.0);
	float2 f  = 1.0 + floor(float2(zbc_hash(float2(seed * 37.0, 5.0)), zbc_hash(float2(seed * 41.0, 9.0))) * 7.0);
	return cos(3.14159 * (2.0 * x.x + 1.0) * f.x / 16.0) * cos(3.14159 * (2.0 * x.y + 1.0) * f.y / 16.0);
}

// where the damaged picture samples
float2 zbc_glitch_uv(float2 uv, float g)
{
	if (g < 0.002)
		return uv;
	zbc_cell z  = zbc_codec_cell(uv, g);
	float    mb = zbc_mb_px();
	float2   bs = mb * screen_res.zw;                       // block size in uv
	float2   b0 = z.blk * bs;                               // block origin
	if (z.starve > 0.0)
	{
		float2 sb = z.starve * screen_res.zw;
		uv = (floor(uv / sb) + 0.5) * sb;
	}
	if (z.cut > 0.0)
	{
		if (z.fill < 0.5)
			uv.y = z.cut * bs.y - 0.5 * screen_res.w;           // the last good line smears down
		return uv;
	}
	if (z.bad > 0.5)
	{
		if (z.kind < 0.4)                                     // shuffled: another part of the picture
		{
			float2 mv = floor((float2(zbc_hash(float2(z.seed * 59.0, 1.0)), zbc_hash(float2(z.seed * 61.0, 2.0))) - 0.5)
			                  * (3.0 + 12.0 * g) + 0.5);
			uv += mv * bs;
		}
		else if (z.kind < 0.65)                               // smeared: its left pixel column drawn across
			uv.x = b0.x + 0.5 * screen_res.z;
		else if (z.kind < 0.82)                               // flat: one colour (the stuck pattern comes later)
			uv = b0 + 0.5 * bs;
	}
	return uv;
}

// colour damage of the same blocks: stuck DCT patterns, wrong chroma, posterized luma, green frames
float3 zbc_glitch_color(float3 c, float2 uv, float g)
{
	if (g < 0.002)
		return c;
	zbc_cell z  = zbc_codec_cell(uv, g);
	float2   p  = uv * screen_res.xy;
	float    y  = dot(c, float3(0.299, 0.587, 0.114));
	float3   ch = c - y;
	if (z.cut > 0.0)
	{
		if (z.fill > 0.5)                                     // an empty YUV frame decodes to flat green
			return float3(0.0, 0.53, 0.0) * (1.0 + 0.12 * zbc_dct(p, z.cut));
		return c * 0.9;
	}
	if (z.starve > 0.0)
		y = floor(y * 10.0 + 0.5) / 10.0;                     // starved: few levels left
	if (z.bad > 0.5)
	{
		float d = zbc_dct(p, z.seed);
		if (z.kind >= 0.65 && z.kind < 0.82)
			y += d * 0.22;                                    // flat block with its stuck pattern
		else if (z.kind >= 0.82)                              // chroma lost: green or magenta
			ch = (zbc_hash(float2(z.seed, 7.0)) < 0.5) ? float3(-0.18, 0.14, -0.18) : float3(0.2, -0.15, 0.2);
		else
			y += d * 0.06;
		y = floor(y * 24.0 + 0.5) / 24.0;
	}
	return max(y + ch, 0.0);
}

// Signal lost, block by block. From 0.35 s after death the picture dies from the bottom up with a
// ragged edge (all gone by ~1.2 s). A dying block first shows the picture smeared down from the edge
// above it, or decoder green, for a few frames, then goes black. After that the camera tries to
// reconnect every ~3 s: for a moment a few blocks come back, green or the live picture.
float zbc_death_td(float2 blk, float col)                           // when a block dies
{
	float v = (blk.y + 0.5) * zbc_mb_px() * screen_res.w;
	return 0.35 + 0.75 * saturate(0.62 * (1.0 - v) + 0.22 * col + 0.16 * zbc_hash(blk + 0.31));
}

// Returns x: black (0..1), y: decoder green (0..1).
float2 zbc_death_block(float2 uv, float e)
{
	if (e < 0.0)
		return float2(0.0, 0.0);
	float2 blk  = floor(uv * screen_res.xy / zbc_mb_px());
	float  td   = zbc_death_td(blk, zbc_hash(float2(blk.x, 0.77)));
	float  dead = step(td, e);
	float  garb = dead * (1.0 - step(td + 0.18, e));
	if (e > 1.6)
	{
		float n  = floor((e - 1.6) / 3.0);
		float ph = (e - 1.6) - n * 3.0 - zbc_hash(float2(n, 3.3)) * 1.5;
		if (ph > 0.0 && ph < 0.16 && zbc_hash13(float3(blk, n)) < 0.06)
			return float2(0.0, step(0.5, zbc_hash13(float3(blk, n + 0.5))));
	}
	return float2(dead * (1.0 - garb), garb * step(zbc_hash(floor(blk * 0.5) + 0.13), 0.15));   // green in 2x2 clumps
}

// a dying block samples the picture at the dying edge above it: streaks smeared down
float2 zbc_death_uv(float2 uv)
{
	float e = zbc_death_age();
	if (e < 0.35 || e > 1.35)
		return uv;
	float2 blk = floor(uv * screen_res.xy / zbc_mb_px());
	float  col = zbc_hash(float2(blk.x, 0.77));
	float  td  = zbc_death_td(blk, col);
	if (e < td || e >= td + 0.18)
		return uv;
	float  front = 1.0 - ((e - 0.35) / 0.75 - 0.22 * col - 0.08) / 0.62;   // where this column still lives
	uv.y = clamp(front, 0.0, uv.y);
	return uv;
}

// decoder green with a stuck pattern
float3 zbc_death_garbage(float2 uv)
{
	float2 p = uv * screen_res.xy;
	float  h = zbc_hash(floor(p / zbc_mb_px()) + 0.13);
	return float3(0.0, 0.53, 0.0) * (1.0 + 0.3 * zbc_dct(p, h));
}

// how much of the picture is gone (0 shows .. 1 black); the garbage is drawn by zbc_signal_lost
float zbc_death_black(float2 uv) { return zbc_death_block(uv, zbc_death_age()).x; }

// dying blocks with their garbage, the rest black
float3 zbc_death_picture(float3 image, float2 uv, float e)
{
	float2 db = zbc_death_block(uv, e);
	image = lerp(image, zbc_death_garbage(uv), db.y);
	return image * (1.0 - db.x);
}

//------------------------------------------------------------------------------------------------
// Low-light (infrared) mode
//------------------------------------------------------------------------------------------------

// Shadow blocking: the encoder spends few bits on dark, flat areas, so they quantize into 8 px blocks
// whose levels jump a few times a second ("boiling"). amt 0..1.
float zbc_shadow_blocks(float y, float2 uv, float amt)
{
	if (amt <= 0.001)
		return y;
	float2 blk   = floor(uv * screen_res.xy / max(zbc_mb_px() * 0.5, 4.0));
	float  off   = zbc_hash13(float3(blk, zbc_tstep(5.0))) - 0.5;
	float  steps = lerp(96.0, 22.0, amt);
	float  yq    = floor(y * steps + 0.5 + off * 0.9) / steps;
	return lerp(y, max(yq, 0.0), amt * (1.0 - smoothstep(0.04, 0.32, y)));
}

// Strong gain with soft highlight roll-off, nearly black-and-white with a faint green cast. The
// camera's IR lamp lights the middle of the picture and falls off to the edges, the gain hunts a
// little, and the starved shadows boil in blocks; own_noise adds the sensor's per-frame noise when
// the lens grain (which already runs noisier in this mode) is not drawn.
float3 zbc_ir_pass(float3 c, float2 uv, float k, bool own_noise)
{
	float  tt   = zbc_time();
	float  agc  = 1.0 + 0.045 * sin(tt * 1.7) + 0.025 * sin(tt * 4.3 + 1.3);
	float2 d    = (uv - 0.5) * zbc_aspect();
	float  lamp = 0.5 + 0.85 * exp(-dot(d, d) * 3.0);
	float  l    = dot(c, float3(0.299, 0.587, 0.114)) * agc * lerp(1.0, lamp, saturate(k));
	float  ir   = zbc_shadow_blocks(1.0 - exp(-l * 4.5), uv, 0.75 * saturate(k));
	if (own_noise)
	{
		float n = zbc_hash13(float3(floor(uv * screen_res.xy), zbc_tstep(30.0))) - 0.5;
		ir = max(ir + n * 0.07 * (1.0 - 0.6 * ir), 0.0);
	}
	return lerp(c, ir.xxx * float3(0.93, 1.0, 0.95), saturate(k));
}

//------------------------------------------------------------------------------------------------
// Lens dirt: glossy dripping blood (rain on the lens is the game's own visor drops, see zbc_fx.script)
//------------------------------------------------------------------------------------------------

// Smooth radial droplet height + analytic gradient in (value, d/dx, d/dy)
float3 zbc_drop_profile(float2 d, float r)
{
	float len = length(d);
	if (len >= r)
		return float3(0.0, 0.0, 0.0);
	float t = 1.0 - len / r;
	float h = t * t * (3.0 - 2.0 * t);
	float dh_dr = -6.0 * t * (1.0 - t) / max(r, 1e-4);
	float2 grad = (len > 1e-5) ? (d / len) * dh_dr : float2(0.0, 0.0);
	return float3(h, grad);
}

// One splatter: organic glossy dripping blood height + surface gradient (value, d/du, d/dv). p: centred
// screen position (screen heights); age: seconds since it hit; drip_t: how far its drips have run.
// halo: the soft glow around each splat (0..1); blood this close to the lens is out of focus.
float3 zbc_splatter(float2 p, float2 asp, float age, float seed, float drip_t, float fade, out float halo)
{
	halo = 0.0;
	// the splatter spreads out over its first ~0.12 s
	float  grow = lerp(0.35, 1.0, smoothstep(0.0, 0.12, age));
	float3 acc  = float3(0.0, 0.0, 0.0);

	// 1. Primary organic splatter blobs + gravity drips sliding down from each impact
	[loop] for (int k = 0; k < 9; k++)
	{
		float2 hk  = float2(seed * 1.13, (float)k * 17.31);
		float3 h3  = zbc_hash3(hk);
		float  ang = h3.x * 6.2832;
		float  rc  = lerp(0.14, 0.52, h3.y);
		float2 c   = float2(cos(ang) * rc * min(asp.x, 16.0 / 9.0) * 0.78, sin(ang) * rc * 0.85);
		float  rb  = lerp(0.018, 0.058, h3.z) * ((k < 2) ? 1.45 : 1.0);
		float  r   = rb * grow;

		// Drips run out of the middle of the splat; how many and how far depends on its size. A small
		// splat holds too little blood to drip, a mid-sized one runs a short way and stops, a large one
		// runs all the way down off the bottom of the lens. Blood is viscous and sticks to the glass: a
		// drip's head is pinned while blood gathers in it, then breaks free and slips down to the next
		// pinning point (stick-slip), the heavier the faster. Only the head moves. It is a teardrop bulb,
		// widest at the bottom, tapering up into a thin rivulet of even width that stays where it was laid.
		float  sz     = saturate((rb - 0.032) / 0.04);                    // 0 small .. 1 large
		int    n_drip = (rb < 0.032) ? 0 : ((sz < 0.3) ? 1 : ((sz < 0.65) ? 2 : 3));
		float  cap    = lerp(0.06, 1.6, sz * sz);                         // how far its blood can run

		// The splat: an irregular blob (uneven, non-repeating edge) with two smaller lobes merged into
		// it, so it reads as a splash, not a star. It drains a little as its drips run.
		float2 d   = p - c;
		float  len = length(d);
		float  an  = atan2(d.y, d.x);
		float  wob = (len > 1e-5) ? (1.0 + 0.10 * sin(an * 3.0 + seed * 1.7 + (float)k)
		                                + 0.07 * sin(an * 5.0 - seed + (float)k * 2.3)
		                                + 0.04 * sin(an * 9.0 + (float)k * 4.1)) : 1.0;
		float  drain = (n_drip > 0) ? 1.0 - 0.2 * saturate(drip_t * 1.5) : 1.0;
		float3 splat = zbc_drop_profile(d, r * wob * drain);
		[unroll] for (int q = 0; q < 2; q++)
		{
			float3 hq  = zbc_hash3(float2(seed * 0.71 + (float)k * 3.3, (float)q * 7.9 + 1.3));
			float  aq  = hq.x * 6.2832;
			float2 oq  = float2(cos(aq), sin(aq)) * r * lerp(0.3, 0.55, hq.y);
			float3 lb  = zbc_drop_profile(d - oq, r * lerp(0.55, 0.75, hq.z) * drain);
			splat += lb * 0.6;                                      // smooth join, no seam
		}
		float  hl    = saturate(1.0 - len / (r * 1.7));
		halo         = max(halo, hl * hl);

		float3 dhead  = float3(0.0, 0.0, 0.0);
		float3 streak = float3(0.0, 0.0, 0.0);
		[unroll] for (int j = 0; j < 3; j++)
		{
			[branch] if (j < n_drip && drip_t > 0.06 * (float)j)
			{
				float3 hj     = zbc_hash3(float2(seed * 2.3 + (float)k * 5.1, (float)j * 13.7 + 0.5));
				float  t_run  = drip_t - 0.06 * (float)j;
				float  sp     = lerp(0.8, 1.2, hj.y) * lerp(0.8, 1.3, sz);       // the heavier the faster
				float  steps  = 4.0 + 4.0 * hj.z;
				float  s_run  = t_run * steps * sp + hj.x;
				float  fs     = frac(s_run);
				float  slide  = smoothstep(0.62, 1.0, fs);
				float  travel = max(floor(s_run) + slide - smoothstep(0.62, 1.0, hj.x), 0.0) / steps * 0.9;
				float  runs   = (travel < cap) ? 1.0 : 0.0;                    // 0 once its blood has run out
				float  moving = saturate(slide * (1.0 - slide) * 4.0) * runs;  // 0 pinned .. 1 mid-slip
				float  start  = smoothstep(0.0, 0.03, t_run);

				float2 c0   = c + float2((hj.x - 0.5) * r * 0.7, 0.0);          // runs out of the middle
				float  mph  = (float)(k * 3 + j) * 2.1 + seed;
				float  tl   = min(travel, cap);                                 // rivulet length
				float  mh   = 0.003 * sin(tl * 17.0 + mph);                     // a slight, fixed wander
				// teardrop bulb: swells while pinned, stretches while slipping
				float  fsw  = (runs > 0.0) ? saturate(fs / 0.62) : 1.0;
				float  rh   = r * lerp(0.30, 0.48, fsw) * (1.0 - 0.25 * moving) * start * lerp(0.8, 1.2, hj.y);
				float  st   = 1.25 + 0.6 * moving;
				float2 head = c0 + float2(mh, tl);
				float2 dd   = p - head;
				float  tq   = saturate(-dd.y / (rh * st * 2.0));                // narrower toward its top
				float3 hq   = zbc_drop_profile(float2(dd.x / lerp(1.0, 0.55, tq), dd.y / st), rh);
				if (hq.x > dhead.x)
					dhead = float3(hq.x, hq.y / lerp(1.0, 0.55, tq), hq.z / st);

				// the rivulet: even width, flaring into the bulb over its last stretch
				float dist = p.y - c0.y;
				if (dist > 0.0 && dist < tl)
				{
					float ax = p.x - c0.x - 0.003 * sin(dist * 17.0 + mph);
					float wt = r * lerp(0.09, 0.15, hj.z) * start;
					float fl = saturate(1.0 - (tl - dist) / max(rh * 3.5, 1e-4));
					float w  = wt + (rh * 0.8 - wt) * fl * fl;
					if (abs(ax) < w)
					{
						float t1 = 1.0 - abs(ax) / w;
						float sh = t1 * t1 * (3.0 - 2.0 * t1) * 0.6;
						if (sh > streak.x)
							streak = float3(sh, -sign(ax) * 6.0 * t1 * (1.0 - t1) / max(w, 1e-4) * 0.6, 0.0);
					}
				}
			}
		}

		// Smooth blend per splat so overlaps build realistic thickness
		float3 s = splat + dhead + streak;
		s.yz *= asp;
		acc = (s.x > acc.x) ? lerp(acc, s, 0.85) : (acc + s * 0.25);
	}

	// 2. Satellite droplets thrown out by the impact: small, and stretched outward along the way
	// they flew. They are there from the first frame (no grow-in).
	[unroll] for (int m = 0; m < 8; m++)
	{
		float3 hm  = zbc_hash3(float2(seed * 3.7 + (float)m * 23.1, (float)m * 9.3));
		float  ang = hm.x * 6.2832;
		float  rc  = lerp(0.10, 0.58, hm.y);
		float2 dir = float2(cos(ang), sin(ang));
		float2 c   = float2(dir.x * rc * min(asp.x, 16.0 / 9.0) * 0.82, dir.y * rc * 0.90);
		float  r   = lerp(0.005, 0.013, hm.z);
		float2 dm  = p - c;
		float  el  = lerp(1.4, 2.2, frac(hm.z * 7.3));                   // stretch along the flight
		float  ra  = dot(dm, dir);
		float  ta  = dm.x * -dir.y + dm.y * dir.x;
		float3 sp  = zbc_drop_profile(float2(ra / el, ta), r);
		sp.yz      = float2(sp.y * dir.x / el - sp.z * dir.y, sp.y * dir.y / el + sp.z * dir.x);
		sp.yz     *= asp;
		acc       += sp * 0.75;
	}

	halo *= fade;
	return acc * fade;
}

// All the blood on the lens: up to four splatters, each staying until it has faded, so every new hit
// adds to what is already there. Worked out once per pixel in the uv stage (zbc_fx_uv) and kept here
// for the shading: x height, yz gradient, w halo; zbc_blood_dry: how dry it is where it is thickest.
static float4 zbc_blood_px  = float4(0.0, 0.0, 0.0, 0.0);
static float  zbc_blood_dry = 0.0;

float4 zbc_blood_field(float2 uv, out float dry)
{
	float4 acc = float4(0.0, 0.0, 0.0, 0.0);
	dry        = 0.0;
	float  wsum = 0.0;
	float2 asp  = zbc_aspect();
	float2 p    = (uv - 0.5) * asp;
	[loop] for (int i = 0; i < 4; i++)
	{
		float t0  = bus_zbc_dirt[i];
		float age = timers.x - t0;
		[branch] if (t0 > 0.0 && age >= 0.0 && age < 26.0)
		{
			float  fade   = 1.0 - smoothstep(14.0, 26.0, age);
			float  seed   = 1.0 + floor(zbc_hash(float2(frac(t0 * 0.137) * 997.0, 3.7 + (float)i)) * 997.0);
			float  drip_t = (bus_zbc_blood[i] > 0.0) ? min(bus_zbc_blood[i], 3.0) : min(age / 14.0, 3.0);
			float  halo;
			float3 f = zbc_splatter(p, asp, age, seed, drip_t, fade, halo);
			// where splatters overlap the blood piles up, thickest on top
			acc.xyz  = (f.x > acc.x) ? lerp(acc.xyz, f, 0.8) + acc.xyz * 0.2 : acc.xyz + f * 0.3;
			acc.w    = max(acc.w, halo);
			float wt = f.x + 0.001;
			dry     += saturate((age - 4.0) / 18.0) * wt;
			wsum    += wt;
		}
	}
	dry = (wsum > 0.0) ? dry / wsum : 0.0;
	return acc;
}

// uv offset of blood refraction (and the blood worked out for zbc_blood_shade); spec: unused, always 0
float2 zbc_drop_offset(float2 uv, out float spec)
{
	spec = 0.0;
	float2 offset = float2(0.0, 0.0);

	[branch] if (dot(bus_zbc_dirt, 1.0) > 0.0)
	{
		zbc_blood_px = zbc_blood_field(uv, zbc_blood_dry);
		// Thick wet blood refracts the scene slightly behind it
		offset += clamp(-zbc_blood_px.yz * 0.0014, -0.014, 0.014);
	}

	return offset;
}

// Physical glossy blood shading: Beer-Lambert dark crimson absorption, soft out-of-focus edges, a red
// glow where light shines through the haze around it, wet specular highlight, and gradual drying.
float3 zbc_blood_shade(float3 c, float2 uv, float scene_vis)
{
	if (dot(bus_zbc_dirt, 1.0) <= 0.0 || scene_vis <= 0.001)
		return c;
	float4 bf   = zbc_blood_px;
	float  h    = saturate(bf.x) * scene_vis;
	float  halo = bf.w * scene_vis;
	if (h <= 0.005 && halo <= 0.005)
		return c;
	float  dry  = zbc_blood_dry;

	// Fresh arterial crimson darkens toward brownish-crimson as it dries
	float3 fresh_tint = float3(0.42, 0.018, 0.018);
	float3 dry_tint   = float3(0.24, 0.028, 0.018);
	float3 tint       = lerp(fresh_tint, dry_tint, dry);

	// Beer-Lambert transmission: thin edges stay translucent, thick core is deep dark crimson
	float  cov    = smoothstep(0.0, 0.45, h);                 // soft: out of focus this close
	float  thick  = smoothstep(0.15, 0.85, h);
	float3 absorb = lerp(float3(1.0, 1.0, 1.0), tint, cov * lerp(0.75, 0.96, thick));
	float3 shaded = c * absorb + float3(0.035, 0.002, 0.002) * cov * (1.0 - thick * 0.65) * (1.0 - dry * 0.5);

	// the haze around it: a little contrast lost, and a red glow where the scene behind is bright
	float  wet_g  = (1.0 - cov) * halo * (1.0 - dry * 0.6);
	float  lum    = dot(c, float3(0.2126, 0.7152, 0.0722));
	shaded        = lerp(shaded, shaded * 0.88 + lum * 0.06, wet_g);
	shaded       += float3(0.55, 0.05, 0.03) * wet_g * (0.08 + lum) * 0.45;

	// Wet glossy specular highlight along the blood droplet meniscus (fades as blood dries)
	float3 N    = normalize(float3(-bf.y * 0.06, -bf.z * 0.06, 1.0));
	float  spec = pow(saturate(dot(N, normalize(float3(-0.35, -0.55, 0.76)))), 18.0);   // soft, out of focus
	shaded     += float3(0.85, 0.55, 0.55) * spec * cov * (1.0 - dry * 0.75) * 0.30;

	return shaded;
}

// screen uv -> uv to sample (interference tearing + blood refraction); g: zbc_glitch_amount()
float2 zbc_fx_uv(float2 uv, float g, out float spec)
{
	float2 u = zbc_glitch_uv(zbc_death_uv(uv), g);
	return u + zbc_drop_offset(uv, spec);
}

// colour effects on the picture (before the overlay): auto-exposure, glossy blood, interference, infrared
float3 zbc_fx_color(float3 c, float2 uv, float g, float spec, float scene_vis)
{
	c *= (bus_zbc_ir.y > 0.01) ? bus_zbc_ir.y : 1.0;   // auto-exposure gain
	c = zbc_blood_shade(c, uv, scene_vis);
	c = zbc_glitch_color(c, uv, g);
	[branch] if (bus_zbc_ir.x > 0.001)
	{
		bool lens_grain = ZBC_ACTIVE && bus_zbc_extra.z > 0.001;   // drawn here or by the HUD layer (zbc_ring.ps)
		c = zbc_ir_pass(c, uv, bus_zbc_ir.x, !lens_grain);
	}
	return c;
}
float3 zbc_fx_color(float3 c, float2 uv, float g, float spec) { return zbc_fx_color(c, uv, g, spec, 1.0); }

// body motion: roll about the centre, then shift (p centred, in screen heights)
float2 zbc_motion(float2 p, float amount)
{
	float k = ZBC_INTENSITY * amount;
	float s, c;
	sincos(bus_zbc_motion.w * k, s, c);
	p = float2(c * p.x - s * p.y, s * p.x + c * p.y);
	return p + bus_zbc_motion.yz * k;
}

// screen uv -> uv in the rendered image: rolling-shutter shear, barrel distortion, zoom, then world motion.
float2 zbc_warp(float2 uv)
{
	float  k      = ZBC_INTENSITY;
	float2 asp    = zbc_aspect();
	float2 p      = (uv - 0.5) * asp;
	p.x          += bus_zbc_sensor.z * k * (uv.y - 0.5);
	float  r2     = dot(p, p);
	float  k1     = bus_zbc_lens.x * k;
	float  zoom   = max(lerp(1.0, bus_zbc_lens.z, k), 0.25);
	float  uw     = min(1.0, (16.0 / 9.0) / asp.x);
	float  r2_eff = r2 * uw * uw;
	p *= (1.0 + k1 * r2_eff + 0.5 * k1 * k1 * r2_eff * r2_eff) / zoom;
	p  = zbc_motion(p, 1.0);
	return p / asp + 0.5;
}

// 1 inside the rendered image, feathering smoothly to 0 over ~10 px where the lens would sample past its edge.
float zbc_valid_src(float2 src)
{
	float2 d = min(src, 1.0 - src) * screen_res.xy;
	return smoothstep(0.0, 10.0, min(d.x, d.y));
}

float zbc_valid(float2 uv) { return zbc_valid_src(zbc_warp(uv)); }

// Lens tap: warp, 5-tap center unsharp + wide-angle peripheral softness + 2-tap (.r/.b) radial CA (7 taps max).
float3 zbc_lens_sample(Texture2D tex, float2 uv, out float2 out_src)
{
	float  k   = ZBC_INTENSITY;
	float2 asp = zbc_aspect();
	float2 src = zbc_warp(uv);
	out_src    = src;
	float3 col = float3(0.0, 0.0, 0.0);
	bool   hit = zbc_face_snap(src);
	[branch] if (hit)   // a face: one flat tap per mosaic block, no sharpening or fringing
	{
		col = tex.SampleLevel(smp_rtlinear, src, 0).rgb;
	}
	else
	{
		float  ca  = bus_zbc_lens.y * k;
		float  sh  = saturate(bus_zbc_extra.y) * k;

		float2 p_rad     = (uv - 0.5) * asp;
		float  r2_norm   = saturate(dot(p_rad, p_rad) / max(0.25 * (asp.x * asp.x + 1.0), 0.25));
		float  edge_soft = saturate(bus_zbc_lens.w) * k * r2_norm * 0.60;
		float2 px_step   = screen_res.zw * (1.0 + 1.4 * edge_soft);

		float3 c_g   = tex.SampleLevel(smp_rtlinear, src, 0).rgb;
		float3 avg   = c_g;
		float  d_lum = 0.0;
		[branch] if (sh > 0.0001 || edge_soft > 0.0001)
		{
			float3 n = tex.SampleLevel(smp_rtlinear, src + float2(px_step.x, 0.0), 0).rgb
			         + tex.SampleLevel(smp_rtlinear, src - float2(px_step.x, 0.0), 0).rgb
			         + tex.SampleLevel(smp_rtlinear, src + float2(0.0, px_step.y), 0).rgb
			         + tex.SampleLevel(smp_rtlinear, src - float2(0.0, px_step.y), 0).rgb;
			avg   = n * 0.25;
			d_lum = dot(c_g - avg, float3(0.2126, 0.7152, 0.0722));
		}

		col = c_g;
		[branch] if (ca > 0.0001)
		{
			float2 o = (src - 0.5) * (0.012 * ca);
			col.r = tex.SampleLevel(smp_rtlinear, src + o, 0).r;
			col.b = tex.SampleLevel(smp_rtlinear, src - o, 0).b;
		}

		float sh_eff = sh * (1.0 - 0.65 * edge_soft);
		col += clamp(d_lum, -0.08, 0.08) * (sh_eff * 1.6);
		col  = lerp(col, avg, edge_soft);
	}
	return max(col, 0.0);
}

float3 zbc_lens_sample(Texture2D tex, float2 uv)
{
	float2 src;
	return zbc_lens_sample(tex, uv, src);
}

// Modern-gritty Axon CMOS sensor pass (before engine colormap/gamma):
// digital compression crispness, highlight blowout/auto-exposure punch, and CMOS color grade.
// Screen derivatives ddx_c / ddy_c are passed in from unconditional flow control for quad safety.
float3 zbc_sensor_pass(float3 c, float2 uv, float3 ddx_c, float3 ddy_c)
{
	float k  = ZBC_INTENSITY;
	float hb = saturate(bus_zbc_sensor.x) * k;
	float dc = saturate(bus_zbc_sensor.y) * k;
	float sg = saturate(bus_zbc_sensor.w) * k;

	// 1. Subtle 4:2:0 chroma subsampling + 8x8 macroblock luma micro-quantization (never blurry)
	[branch] if (dc > 0.001)
	{
		float2 px    = floor(uv * screen_res.xy);
		float2 odd   = step(0.5, frac(px * 0.5));
		float3 c_2x2 = c + (0.5 - odd.x) * ddx_c + (0.5 - odd.y) * ddy_c;
		float  y0    = dot(c,     float3(0.2126, 0.7152, 0.0722));
		float  y2    = dot(c_2x2, float3(0.2126, 0.7152, 0.0722));
		float3 ch    = lerp(c - y0.xxx, c_2x2 - y2.xxx, 0.55 * dc);

		float2 blk   = floor(px / 8.0);
		float  bn    = (zbc_hash13(float3(blk, zbc_tstep(12.0))) - 0.5) * 0.014 * dc
		             * smoothstep(0.01, 0.08, y0) * (1.0 - saturate(y0 * 1.1));
		float  steps = lerp(255.0, 72.0, dc);
		float  yq    = floor(y0 * steps + 0.5) / steps;
		float  y_out = lerp(y0, yq, 0.22 * dc) + bn;
		// keyframe pumping: crisp on each keyframe (every 1.6 s), the shadows blocking up until the next
		float  gop   = frac(zbc_time() / 1.6);
		y_out        = zbc_shadow_blocks(y_out, uv, dc * (0.35 + 0.65 * gop));
		c = max(y_out.xxx + ch, 0.0);
	}

	// 2. Highlight blowout & small-sensor auto-exposure contrast punch
	[branch] if (hb > 0.001)
	{
		float luma     = dot(c, float3(0.2126, 0.7152, 0.0722));
		float peak     = max(luma, max(c.r, max(c.g, c.b)) * 0.88);
		float hi       = smoothstep(0.50, 1.02, peak);
		float auto_exp = lerp(0.96, 1.14, smoothstep(0.16, 0.78, luma));
		c *= lerp(1.0, auto_exp, hb * 0.65);

		float3 boosted = c * (1.0 + 0.40 * hi * hb);
		float3 clipped = max(boosted, peak.xxx * (1.0 + 0.45 * hb));
		c = lerp(boosted, clipped, saturate(hi * hi * hb * 0.80));
	}

	// 3. Axon CMOS grade: controlled ~18% desaturation, cool-neutral white balance, crisp S-curve
	[branch] if (sg > 0.001)
	{
		float l   = dot(c, float3(0.2126, 0.7152, 0.0722));
		c         = lerp(c, l.xxx, 0.18 * sg);
		c        *= lerp(float3(1.0, 1.0, 1.0), float3(0.97, 1.00, 1.04), sg);
		float3 cs = saturate(c);
		float3 sc = cs * cs * (3.0 - 2.0 * cs);
		c        += (sc - cs) * (0.24 * sg);
	}

	return max(c, 0.0);
}

// Shadow-weighted 30 Hz CMOS sensor grain (luma + subtle RGGB chroma), keeping bright sky clean
// and pure-black bezel (scene_vis == 0 && osd_mask == 0) noiseless while letting OSD carry grain.
// Only used in postprocess pass; HUD-layer mode uses zbc_ring.ps.
float3 zbc_grain(float3 c, float2 uv, float osd_mask, float scene_vis)
{
	float lift_w = saturate(scene_vis + osd_mask);
	if (lift_w <= 0.0001)
		return c;

	float g = saturate(saturate(bus_zbc_extra.z) * (1.0 + 1.5 * saturate(bus_zbc_ir.x))) * ZBC_INTENSITY;   // infrared: noisier
	[branch] if (g >= 0.001)
	{
		float2 px    = floor(uv * screen_res.xy);
		float3 h3    = zbc_hash33(float3(px, zbc_tstep(30.0))) - 0.5;   // new noise every frame, not a shifted copy
		float  nl    = h3.x;
		float  nc_r  = h3.y;
		float  nc_b  = h3.z;
		float3 grain = nl.xxx + float3(nc_r, -0.5 * (nc_r + nc_b), nc_b) * 0.35;

		float  luma     = dot(c, float3(0.2126, 0.7152, 0.0722));
		float  inv_l    = 1.0 - saturate(luma);
		// inv_l * sqrt(inv_l) = inv_l^1.5 without pow(0, 1.5) NaN risk
		float  shadow_w = max(0.08 + 0.92 * inv_l * sqrt(max(inv_l, 0.0)), 0.42 * saturate(osd_mask));
		float  amp      = g * shadow_w;

		c = max(c * (1.0 + grain * (amp * 0.22)) + grain * (amp * 0.022 * inv_l * lift_w), 0.0);
	}
	return c;
}

float3 zbc_grain(float3 c, float2 uv, float osd_mask) { return zbc_grain(c, uv, osd_mask, 1.0); }
float3 zbc_grain(float3 c, float2 uv) { return zbc_grain(c, uv, 0.0, 1.0); }

// Decoupled motion-reactive lens housing, optical vignette, and asymmetric chest-rig occlusion.
// Returns how much of the picture shows: 1 = clear, 0 = pure black.
float zbc_render(float2 uv)
{
	float  k      = ZBC_INTENSITY;
	float2 asp    = zbc_aspect();
	float  follow = max(bus_zbc_extra.x, 0.0);

	// 1. Aspect-corrected offset & independent housing roll
	float2 d = (uv - 0.5) * asp - bus_zbc_vig.xy * (k * follow);
	float  s, c;
	sincos(bus_zbc_vig.w * k, s, c);
	d = float2(c * d.x - s * d.y, s * d.x + c * d.y);

	// 2. Clean circle (0) -> screen aspect (1) shape interpolation, matching 16:9 framing on ultrawides
	float s_w    = saturate(bus_zbc_edge.w);
	float w_div  = lerp(1.0, asp.x, s_w);
	float asp_16 = 16.0 / 9.0;
	if (asp.x > asp_16)
	{
		float w_match = (asp.x / asp_16) * lerp(1.0, asp_16, s_w);
		w_div = lerp(1.0, w_match, smoothstep(0.0, 0.25, s_w));
	}
	d.x /= max(w_div, 0.1);

	// 3. Overflow/NaN-safe superellipse distance (p in 2..6; fast L2 when circular, single pow when rounded)
	float  n  = clamp(bus_zbc_vig_occ.w, 2.0, 6.0);
	float2 ad = abs(d);
	float  m  = max(ad.x, ad.y);
	float  r  = 0.0;
	if (m > 1e-5)
	{
		if (n <= 2.001)
		{
			r = sqrt(dot(ad, ad));
		}
		else
		{
			float q_min = max(min(ad.x, ad.y) / m, 1e-4);
			r = m * pow(1.0 + pow(q_min, n), 1.0 / n);
		}
	}

	// 4. Rounded housing bezel first: early out on dead-black corners before optical cos() / occlusion
	float tighten = saturate(bus_zbc_vig.z) * k;
	float R_base  = max(abs(bus_zbc_edge.x), 0.05);
	float R_eff   = max(R_base * (1.0 - 0.05 * tighten), 0.10);
	float b       = max(bus_zbc_edge.y, 0.001);
	float housing = (bus_zbc_edge.x < 0.0) ? 1.0 : 1.0 - smoothstep(R_eff - b, R_eff, r);   // < 0: housing off
	if (housing <= 0.0001)
		return 0.0;

	// 5. Smooth optical vignette + dynamic tightening
	float vig_str  = saturate(bus_zbc_edge.z + 0.14 * tighten);
	float t        = saturate(r / max(R_eff, 0.25));
	float c_opt    = cos(t * 1.12);
	float cos_fall = c_opt * c_opt;
	float optical  = lerp(1.0, cos_fall, vig_str * 0.85);

	// 5. Asymmetric chest-rig / shoulder / chin occlusion in rolled screen space
	float2 occ_dir = bus_zbc_vig_occ.xy * k;
	float  occ_str = clamp(bus_zbc_vig_occ.z, 0.0, 1.5) * k;
	float  occ_vis = 1.0;
	[branch] if (occ_str > 0.001)
	{
		float2 po = (uv - 0.5) * asp;
		po = float2(c * po.x - s * po.y, s * po.x + c * po.y);
		float2 pn = po / max(float2(asp.x * 0.5, 0.5), float2(0.1, 0.1));
		float  edge_wrap = 0.15 * dot(pn, pn);
		float  sx = saturate(pn.x * occ_dir.x + 0.25 * abs(occ_dir.x) + edge_wrap * abs(occ_dir.x));
		float  sy = saturate(pn.y * occ_dir.y + 0.25 * abs(occ_dir.y) + edge_wrap * abs(occ_dir.y));
		float  occ_f   = max(sx, sy);
		float  soft_sh = smoothstep(0.18, 0.96, occ_f);
		float  hard_sh = smoothstep(0.68, 1.08, occ_f);
		occ_vis = 1.0 - saturate(occ_str * (0.58 * soft_sh + 0.38 * hard_sh));
	}

	return saturate(housing * optical * occ_vis);
}

// Neutral black vignette / housing edge (no blue tint artifact)
float3 zbc_vignette(float3 image, float2 uv)
{
	float rp = lerp(1.0, zbc_render(uv), saturate(bus_zbc_motion.x * 4.0));
	return image * rp;
}

// HUD-layer version (zbc_ring.ps): 1 = fully black
float zbc_edge(float2 uv) { return 1.0 - zbc_render(uv); }

#endif
