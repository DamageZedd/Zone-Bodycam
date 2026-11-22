// Zone Bodycam - Modern-Gritty Axon lens, CMOS sensor, and motion-reactive vignette model.
// Included by postprocess.ps / postprocess_cm.ps, i.e. the display-resolution post chain that the
// Slop-Ray engine runs AFTER DLSS/FSR reconstruction, so the warp is never fed to the upscaler.
// Values come from scripts\zbc_bodycam.script through private Shader Bus lanes. All-zero
// bus_zbc_motion means "off" and the post chain is untouched (main menu, no actor, mod disabled).
#ifndef ZBC_LENS_H
#define ZBC_LENS_H

uniform float4 bus_zbc_motion;   // x: intensity 0..1  y/z: world shift (screen heights)  w: world roll (rad)
uniform float4 bus_zbc_lens;     // x: barrel k1  y: radial CA  z: zoom  w: peripheral edge softness (0..1)
uniform float4 bus_zbc_edge;     // x: edge radius (0.4..1.35)  y: edge softness (>0)  z: optical vignette (0..1)  w: edge shape (0=circle .. 1=screen)
uniform float4 bus_zbc_extra;    // x: vignette follow scale  y: sharpen (0..1)  z: CMOS grain (0..1)  w: >=0.5 image, <0.5 HUD ring
uniform float4 bus_zbc_vig;      // x/y: independent vignette & housing center offset (screen heights)  z: dynamic tightening (0..1)  w: housing/vignette roll (rad)
uniform float4 bus_zbc_vig_occ;  // x: horizontal chest/shoulder occlusion (-1 left .. +1 right)  y: vertical rig/chin occlusion (-1 top .. +1 bottom)  z: occlusion strength (0..1+)  w: superellipse power (2.0..6.0)
uniform float4 bus_zbc_sensor;   // x: highlight blowout & auto-exposure punch (0..1)  y: digital compression crispness (0..1)  z: signed rolling-shutter horizontal shear  w: CMOS color grade (0..1)

// Face pixelation (scripts\zbc_faces.script). Squares in rendered-image uv, independent of the lens.
uniform float4 bus_zbc_faces;    // x: number of faces in use (0..64), y/z: packed 12-bit union AABB (u, v), w: >0.5 if valid

// Camera effects (scripts\zbc_fx.script), independent of the lens.
uniform float4 bus_zbc_glitch;   // x: interference 0..1  y: hit burst 0..1  z: time of death (timers.x clock, 0 alive)
uniform float4 bus_zbc_ir;       // x: low-light (infrared) mix 0..1  y: auto-exposure gain (0 = off, 1 = neutral)
uniform float4 bus_zbc_dirt;     // x: rain on the lens 0..1  y: blood seed  z: time the blood hit (0 none)

#define ZBC_INTENSITY (saturate(bus_zbc_motion.x))
#define ZBC_ACTIVE    (bus_zbc_motion.x > 0.0005)
#define ZBC_FACES     (bus_zbc_faces.x > 0.5)
#define ZBC_FX        (bus_zbc_glitch.x + bus_zbc_glitch.y + bus_zbc_glitch.z + bus_zbc_dirt.x + bus_zbc_dirt.z > 0.0005)

// width / height of the display
float2 zbc_aspect() { return float2(max(screen_res.x * screen_res.w, 0.1), 1.0); }

// 2D -> 1D hash in [0, 1)
float zbc_hash(float2 p)
{
	p  = frac(p * float2(443.897, 441.423));
	p += dot(p, p.yx + 19.19);
	return frac((p.x + p.y) * p.x);
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

// seconds since death, or -1 while alive
float zbc_death_age() { return (bus_zbc_glitch.z > 0.0) ? max(timers.x - bus_zbc_glitch.z, 0.0) : -1.0; }

// how broken the picture is now, 0..1
float zbc_glitch_amount()
{
	float g = saturate(max(bus_zbc_glitch.x, bus_zbc_glitch.y));
	float e = zbc_death_age();
	if (e >= 0.0)
		g = max(g, saturate(e / 0.3));             // death: full breakup within 0.3 s
	return g;
}

// tearing: sideways-shifted bands, line jitter, an occasional vertical roll (24 updates a second)
float2 zbc_glitch_uv(float2 uv, float g)
{
	if (g < 0.002)
		return uv;
	float t    = floor(timers.x * 24.0);
	float rows = lerp(6.0, 36.0, zbc_hash(float2(t, 3.1)));
	float band = floor(uv.y * rows);
	float on   = step(zbc_hash(float2(band, t)), g * 0.55);
	uv.x += on * (zbc_hash(float2(band, t + 7.0)) - 0.5) * 0.14 * g;
	uv.x += (zbc_hash(float2(floor(uv.y * screen_res.y * 0.5), t)) - 0.5) * 0.004 * g * g;
	float roll = step(zbc_hash(float2(t, 11.0)), g * g * 0.15) * (zbc_hash(float2(t, 13.0)) - 0.5) * 0.25;
	uv.y = frac(uv.y + roll);
	return uv;
}

// colour damage: noise bars, corrupted macroblocks, whole-frame dropouts
float3 zbc_glitch_color(float3 c, float2 uv, float g)
{
	if (g < 0.002)
		return c;
	float  t   = floor(timers.x * 24.0);
	float  bar = floor(uv.y * 90.0);
	float  nb  = step(zbc_hash(float2(bar, t + 1.0)), g * 0.12);
	float  n   = zbc_hash(floor(uv * screen_res.xy * 0.5) + t);
	c = lerp(c, n.xxx * 0.8, nb * 0.85);
	float2 blk = floor(uv * float2(24.0, 14.0));
	float  bc  = step(zbc_hash(blk + t * 1.7), g * g * 0.10);
	c = lerp(c, c.gbr * 1.4, bc);
	float drop = step(zbc_hash(float2(t, 5.0)), g * g * 0.06);
	return c * (1.0 - drop * 0.85);
}

// signal lost: the picture is gone (black) from 0.9 to 1.4 s after death
float zbc_death_black()
{
	float e = zbc_death_age();
	return (e < 0.0) ? 0.0 : smoothstep(0.9, 1.4, e);
}

//------------------------------------------------------------------------------------------------
// Low-light (infrared) mode
//------------------------------------------------------------------------------------------------

// strong gain with soft highlight roll-off, nearly black-and-white with a faint green cast
float3 zbc_ir_pass(float3 c, float k)
{
	float l  = dot(c, float3(0.299, 0.587, 0.114));
	float ir = 1.0 - exp(-l * 4.5);
	return lerp(c, ir.xxx * float3(0.93, 1.0, 0.95), saturate(k));
}

//------------------------------------------------------------------------------------------------
// Lens dirt: dynamic sliding rain drops (with trails & micro-beads) and glossy dripping blood
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

// Stick-slip gravity descent: drops pause, slide, pause, slide
float zbc_slide_progress(float phase, float seed)
{
	float s = (seed - 0.5) * 0.06;
	return 0.22 * smoothstep(0.04, 0.26 + s, phase)
	     + 0.36 * smoothstep(0.34 + s, 0.56 + s, phase)
	     + 0.42 * smoothstep(0.62 + s, 0.86, phase);
}

// One layer of sliding raindrop streams (head + tapered wet trail + wake micro-beads),
// evaluated across horizontal neighbor columns so wandering drops never clip at cell edges.
float3 zbc_rain_streams(float2 uv, float2 asp, float wet, float scale, float t_clock)
{
	float2 grid = float2(14.0 * asp.x, 3.2) * scale;
	float2 p    = uv * grid;
	float2 base = floor(p);
	float3 acc  = float3(0.0, 0.0, 0.0);

	[unroll] for (int ox = -1; ox <= 1; ox++)
	{
		float col = base.x + (float)ox;
		float col_seed = zbc_hash(float2(col * 17.3, scale * 31.7));
		float y_shift  = p.y + col_seed * 6.0;
		float row      = floor(y_shift);
		float3 h3      = zbc_hash3(float2(col * 37.1 + scale * 11.3, row * 91.7));

		// Population gate: denser as wet increases
		float pop = smoothstep(lerp(0.05, 0.92, h3.z) - 0.04, lerp(0.05, 0.92, h3.z) + 0.04, wet);
		if (pop <= 0.001)
			continue;

		float life  = 4.2 + h3.y * 2.4;
		float phase = frac(t_clock / life + h3.z);
		float slide = zbc_slide_progress(phase, h3.y);
		float fade  = smoothstep(0.0, 0.04, phase) * (1.0 - smoothstep(0.88, 1.0, phase));

		float2 local = float2(p.x - col - 0.5, frac(y_shift));
		// Gentle organic horizontal wander as the drop descends
		float wander = sin(local.y * 6.2832 + h3.x * 6.2832) * 0.14 * (0.4 + 0.6 * h3.y);
		float hx     = (h3.x - 0.5) * 0.45 + wander;
		float hy     = lerp(0.08, 0.92, slide);

		// 1. Main teardrop head (slightly elongated vertically)
		float2 hd = local - float2(hx, hy);
		hd.y *= 1.35;
		float3 head = zbc_drop_profile(hd, lerp(0.14, 0.22, h3.y));
		head.z *= 1.35;

		// 2. Tapered wet trail behind the descending head
		float behind = hy - local.y;
		float3 trail = float3(0.0, 0.0, 0.0);
		if (behind > 0.0 && behind < 0.55)
		{
			float tfade = smoothstep(0.55, 0.02, behind) * smoothstep(0.0, 0.05, behind);
			float tr    = lerp(0.045, 0.095, tfade);
			float tx    = local.x - hx;
			if (abs(tx) < tr)
			{
				float tt = 1.0 - abs(tx) / tr;
				float th = tt * tt * (3.0 - 2.0 * tt) * tfade * 0.26;
				float tg = -sign(tx) * 6.0 * tt * (1.0 - tt) / max(tr, 1e-4) * tfade * 0.26;
				trail = float3(th, tg, 0.0);
			}
			// Tiny micro-beads left along the trail wake
			float bead_y = frac(local.y * 7.0 + h3.y * 5.0) - 0.5;
			float2 bd    = float2(tx, bead_y / 7.0);
			float3 bead  = zbc_drop_profile(bd, 0.055) * tfade * 0.45;
			trail += bead;
		}

		float w = pop * fade;
		float3 combined = (head + trail) * w;
		combined.yz *= grid;
		acc += combined;
	}
	return acc;
}

// Stationary fine micro-beads across 2x2 neighbor cells (zero cell-edge clipping)
float3 zbc_rain_static(float2 uv, float2 asp, float wet, float t_clock)
{
	float2 grid = float2(26.0 * asp.x, 26.0);
	float2 p    = uv * grid;
	float2 base = floor(p);
	float2 side = float2((frac(p.x) < 0.5) ? -1.0 : 1.0, (frac(p.y) < 0.5) ? -1.0 : 1.0);
	float3 acc  = float3(0.0, 0.0, 0.0);

	[unroll] for (int ix = 0; ix <= 1; ix++)
	{
		[unroll] for (int iy = 0; iy <= 1; iy++)
		{
			float2 cell  = base + float2((float)ix, (float)iy) * side;
			float3 h3    = zbc_hash3(cell + 13.7);
			float  pop   = smoothstep(lerp(0.08, 0.96, h3.z) - 0.05, lerp(0.08, 0.96, h3.z) + 0.05, wet);
			if (pop <= 0.001)
				continue;
			float life  = frac(t_clock * (0.025 + 0.04 * h3.x) + h3.z);
			float fade  = smoothstep(0.0, 0.12, life) * (1.0 - smoothstep(0.80, 1.0, life));
			float2 ctr  = cell + 0.5 + (h3.xy - 0.5) * 0.65;
			float  r    = lerp(0.14, 0.32, frac(h3.z * 9.7));
			float3 drop = zbc_drop_profile(p - ctr, r) * (pop * fade * 0.55);
			drop.yz    *= grid;
			acc        += drop;
		}
	}
	return acc;
}

// Organic glossy dripping blood height + surface gradient (value, d/du, d/dv)
float3 zbc_blood_field(float2 uv)
{
	if (bus_zbc_dirt.z <= 0.0)
		return float3(0.0, 0.0, 0.0);
	float age  = timers.x - bus_zbc_dirt.z;
	float fade = 1.0 - smoothstep(14.0, 26.0, age);
	if (age < 0.0 || fade <= 0.0)
		return float3(0.0, 0.0, 0.0);

	float  seed = bus_zbc_dirt.y;
	float2 asp  = zbc_aspect();
	float2 p    = (uv - 0.5) * asp;
	float  drip_t = saturate(age / 14.0);
	float3 acc  = float3(0.0, 0.0, 0.0);

	// 1. Primary organic splatter blobs + gravity drips sliding down from each impact
	[unroll] for (int k = 0; k < 9; k++)
	{
		float2 hk  = float2(seed * 1.13, (float)k * 17.31);
		float3 h3  = zbc_hash3(hk);
		float  ang = h3.x * 6.2832;
		float  rc  = lerp(0.14, 0.52, h3.y);
		float2 c   = float2(cos(ang) * rc * min(asp.x, 16.0 / 9.0) * 0.78, sin(ang) * rc * 0.85);
		float  r   = lerp(0.018, 0.058, h3.z) * ((k < 2) ? 1.45 : 1.0);

		// Slight organic wobble on the splat silhouette
		float2 d   = p - c;
		float  len = length(d);
		float  wob = (len > 1e-5) ? (1.0 + 0.22 * sin(atan2(d.y, d.x) * 4.0 + seed + (float)k)
		                                + 0.12 * cos(atan2(d.y, d.x) * 7.0 - seed * 2.0)) : 1.0;
		float3 splat = zbc_drop_profile(d, r * wob);

		// Gravity drip running down from the splat as time passes
		float drip_len = lerp(0.04, 0.22, h3.y) * smoothstep(0.0, 0.85, drip_t);
		float hy       = c.y + drip_len;
		float wx       = c.x + sin((p.y - c.y) * 28.0 + h3.x * 6.2832) * 0.005;
		float2 hd      = p - float2(wx, hy);
		hd.y          *= 0.75;
		float3 dhead   = zbc_drop_profile(hd, r * 0.52) * smoothstep(0.0, 0.15, drip_t);
		dhead.z       *= 0.75;

		// Thin connecting drip streak between splat and drip head
		float3 streak = float3(0.0, 0.0, 0.0);
		if (p.y > c.y && p.y < hy && drip_len > 0.005)
		{
			float frac_y = saturate((p.y - c.y) / drip_len);
			float sr     = r * lerp(0.32, 0.16, frac_y);
			float sx     = p.x - wx;
			if (abs(sx) < sr)
			{
				float st = 1.0 - abs(sx) / sr;
				float sh = st * st * (3.0 - 2.0 * st) * 0.65;
				float sg = -sign(sx) * 6.0 * st * (1.0 - st) / max(sr, 1e-4) * 0.65;
				streak = float3(sh, sg, 0.0);
			}
		}

		// Smooth blend per splat so overlaps build realistic thickness
		float3 s = splat + dhead + streak;
		s.yz *= asp;
		acc = (s.x > acc.x) ? lerp(acc, s, 0.85) : (acc + s * 0.25);
	}

	// 2. Fine secondary mist/micro-droplets around the main impact
	[unroll] for (int m = 0; m < 8; m++)
	{
		float3 hm = zbc_hash3(float2(seed * 3.7 + (float)m * 23.1, (float)m * 9.3));
		float  ang = hm.x * 6.2832;
		float  rc  = lerp(0.10, 0.58, hm.y);
		float2 c   = float2(cos(ang) * rc * min(asp.x, 16.0 / 9.0) * 0.82, sin(ang) * rc * 0.90);
		float  r   = lerp(0.006, 0.016, hm.z);
		float3 sp  = zbc_drop_profile(p - c, r);
		sp.yz     *= asp;
		acc       += sp * 0.75;
	}

	return acc * fade;
}

// uv offset of rain drops + blood refraction; spec: subtle wet meniscus glint for zbc_fx_color
float2 zbc_drop_offset(float2 uv, out float spec)
{
	spec = 0.0;
	float2 offset = float2(0.0, 0.0);
	float2 asp    = zbc_aspect();

	float wet = saturate(bus_zbc_dirt.x);
	[branch] if (wet > 0.01)
	{
		float3 d1 = zbc_rain_streams(uv, asp, wet, 1.0, timers.x);
		float3 d2 = zbc_rain_streams(uv + float2(0.37, 0.19), asp, wet * 0.85, 1.45, timers.x * 0.82 + 11.3);
		float3 ds = zbc_rain_static(uv, asp, wet, timers.x);
		float3 rain = d1 + d2 * 0.65 + ds;
		// Clamp refraction smoothly so droplets bend light crisply without tearing
		float2 n_rain = clamp(-rain.yz * 0.0022, -0.022, 0.022);
		offset += n_rain;
		// Subtle glossy water meniscus highlight (top-left light direction)
		float3 N = normalize(float3(-rain.y * 0.08, -rain.z * 0.08, 1.0));
		float  hl = pow(saturate(dot(N, normalize(float3(-0.35, -0.55, 0.76)))), 28.0);
		spec = hl * saturate(rain.x * 2.5) * 0.28;
	}

	[branch] if (bus_zbc_dirt.z > 0.0)
	{
		float3 bf = zbc_blood_field(uv);
		// Thick wet blood refracts the scene slightly behind it
		offset += clamp(-bf.yz * 0.0014, -0.014, 0.014);
	}

	return offset;
}

// Physical glossy blood shading: Beer-Lambert dark crimson absorption, wet specular highlight,
// and gradual drying over time.
float3 zbc_blood_shade(float3 c, float2 uv, float scene_vis)
{
	if (bus_zbc_dirt.z <= 0.0 || scene_vis <= 0.001)
		return c;
	float3 bf = zbc_blood_field(uv);
	float  h  = saturate(bf.x) * scene_vis;
	if (h <= 0.005)
		return c;

	float age = max(timers.x - bus_zbc_dirt.z, 0.0);
	float dry = saturate((age - 4.0) / 18.0);

	// Fresh arterial crimson darkens toward brownish-crimson as it dries
	float3 fresh_tint = float3(0.42, 0.018, 0.018);
	float3 dry_tint   = float3(0.24, 0.028, 0.018);
	float3 tint       = lerp(fresh_tint, dry_tint, dry);

	// Beer-Lambert transmission: thin edges stay translucent, thick core is deep dark crimson
	float  cov    = smoothstep(0.04, 0.35, h);
	float  thick  = smoothstep(0.15, 0.85, h);
	float3 absorb = lerp(float3(1.0, 1.0, 1.0), tint, cov * lerp(0.75, 0.96, thick));
	float3 shaded = c * absorb + float3(0.035, 0.002, 0.002) * cov * (1.0 - thick * 0.65) * (1.0 - dry * 0.5);

	// Wet glossy specular highlight along the blood droplet meniscus (fades as blood dries)
	float3 N    = normalize(float3(-bf.y * 0.06, -bf.z * 0.06, 1.0));
	float  spec = pow(saturate(dot(N, normalize(float3(-0.35, -0.55, 0.76)))), 36.0);
	shaded     += float3(0.85, 0.55, 0.55) * spec * cov * (1.0 - dry * 0.75) * 0.38;

	return shaded;
}

// screen uv -> uv to sample (interference tearing + rain drop & blood refraction); g: zbc_glitch_amount()
float2 zbc_fx_uv(float2 uv, float g, out float spec)
{
	float2 u = zbc_glitch_uv(uv, g);
	return u + zbc_drop_offset(uv, spec);
}

// colour effects on the picture (before the overlay): auto-exposure, rain glint, glossy blood, interference, infrared
float3 zbc_fx_color(float3 c, float2 uv, float g, float spec, float scene_vis)
{
	c *= (bus_zbc_ir.y > 0.01) ? bus_zbc_ir.y : 1.0;   // auto-exposure gain
	c += spec * scene_vis;
	c = zbc_blood_shade(c, uv, scene_vis);
	c = zbc_glitch_color(c, uv, g);
	[branch] if (bus_zbc_ir.x > 0.001)
		c = zbc_ir_pass(c, bus_zbc_ir.x);
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
		float  t_blk = floor(timers.x * 12.0);
		float  bn    = (zbc_hash(blk + t_blk * float2(13.0, 29.0)) - 0.5) * 0.014 * dc
		             * smoothstep(0.01, 0.08, y0) * (1.0 - saturate(y0 * 1.1));
		float  steps = lerp(255.0, 72.0, dc);
		float  yq    = floor(y0 * steps + 0.5) / steps;
		float  y_out = lerp(y0, yq, 0.22 * dc) + bn;
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
		float2 t_off = floor(timers.x * 30.0) * float2(37.0, 17.0);
		float3 h3    = zbc_hash3(px + t_off) - 0.5;
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
	float R_base  = max(bus_zbc_edge.x, 0.05);
	float R_eff   = max(R_base * (1.0 - 0.05 * tighten), 0.10);
	float b       = max(bus_zbc_edge.y, 0.001);
	float housing = 1.0 - smoothstep(R_eff - b, R_eff, r);
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
