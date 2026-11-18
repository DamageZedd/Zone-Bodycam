// Zone Bodycam - top-right Axon overlay rendered inside postprocess (after lens warp, before sensor compression, grain, and vignette).
#ifndef ZBC_OSD_H
#define ZBC_OSD_H

#include "zbc_lens.h"
#include "zbc_logo.h"

uniform float4 bus_zbc_osd_info;         // x: active (>0.5), y: logo_style (0=official, 1=swirl, 2=plain, 3=none), z: text_opacity, w: logo_opacity
uniform float4 bus_zbc_osd_layout;       // x: logo_x (0.950), y: logo_y (0.026*asp.x), z: logo_w (0.035), w: em_v (em_px / H)
uniform uint4  bus_zbc_osd_chars[31];    // row 0: (len0, len1, len2, 0); row 1+i*10+(c>>2) comp (c&3) = ASCII byte
uniform uint4  bus_zbc_osd_atlas[816];   // rows 0..751: ASCII 33..126 16x32 2-bit (8 uint4s/glyph); rows 752..815: 64x64 2-bit logo
uniform float4 bus_zbc_rec;              // top-left recording timer. x: active (>0.5), y: dot lit (>0.5), z: whole seconds recorded, w: text_opacity

// recording timer geometry in em (keep in step with REC_* in scripts\zbc_bodycam.script)
#define ZBC_REC_DOT_D  1.06
#define ZBC_REC_DOT_CY 0.56
#define ZBC_REC_GAP    0.15

uint zbc_uint4_comp(uint4 v, uint comp)
{
	return (comp < 2u) ? ((comp == 0u) ? v.x : v.y) : ((comp == 2u) ? v.z : v.w);
}

uint zbc_osd_len(uint line_idx)
{
	return min(zbc_uint4_comp(bus_zbc_osd_chars[0], min(line_idx, 2u)), 40u);
}

uint zbc_osd_char_at(uint line_idx, uint c_idx)
{
	uint row = min(1u + min(line_idx, 2u) * 10u + (min(c_idx, 39u) >> 2u), 30u);
	return zbc_uint4_comp(bus_zbc_osd_chars[row], c_idx & 3u);
}

// Decodes one texel from a 16x32 2-bit font glyph as float2(luma, alpha).
float2 zbc_osd_glyph_texel(uint g, int ix, int iy)
{
	if (ix < 0 || ix >= 16 || iy < 0 || iy >= 32)
		return float2(0.0, 0.0);
	uint ux   = (uint)ix;
	uint uy   = (uint)iy;
	uint row  = min(g, 93u) * 8u + (uy >> 2u);
	uint word = zbc_uint4_comp(bus_zbc_osd_atlas[row], uy & 3u);
	uint code = (word >> (ux * 2u)) & 3u;
	if (code == 0u) return float2(0.0,  0.0);
	if (code == 1u) return float2(0.0,  0.82);
	if (code == 2u) return float2(0.68, 0.95);
	return float2(1.0, 1.0);
}

float2 zbc_osd_glyph_sample(uint ch, float2 guv)
{
	if (ch < 33u || ch > 126u)
		return float2(0.0, 0.0);
	uint   g   = ch - 33u;
	float2 fp  = guv * float2(16.0, 32.0) - 0.5;
	int2   p0  = (int2)floor(fp);
	float2 f   = fp - (float2)p0;
	float2 t00 = zbc_osd_glyph_texel(g, p0.x,     p0.y);
	float2 t10 = zbc_osd_glyph_texel(g, p0.x + 1, p0.y);
	float2 t01 = zbc_osd_glyph_texel(g, p0.x,     p0.y + 1);
	float2 t11 = zbc_osd_glyph_texel(g, p0.x + 1, p0.y + 1);
	return lerp(lerp(t00, t10, f.x), lerp(t01, t11, f.x), f.y);
}

// Decodes one texel from the 64x64 2-bit official logo alpha atlas.
float zbc_osd_logo_texel(int ix, int iy)
{
	if (ix < 0 || ix >= 64 || iy < 0 || iy >= 64)
		return 0.0;
	uint ux   = (uint)ix;
	uint uy   = (uint)iy;
	uint row  = 752u + uy;
	uint word = zbc_uint4_comp(bus_zbc_osd_atlas[row], ux >> 4u);
	uint code = (word >> ((ux & 15u) * 2u)) & 3u;
	if (code == 0u) return 0.0;
	if (code == 1u) return 0.33;
	if (code == 2u) return 0.70;
	return 1.0;
}

float zbc_osd_logo_sample(float2 luv)
{
	float2 fp  = luv * 64.0 - 0.5;
	int2   p0  = (int2)floor(fp);
	float2 f   = fp - (float2)p0;
	float  a00 = zbc_osd_logo_texel(p0.x,     p0.y);
	float  a10 = zbc_osd_logo_texel(p0.x + 1, p0.y);
	float  a01 = zbc_osd_logo_texel(p0.x,     p0.y + 1);
	float  a11 = zbc_osd_logo_texel(p0.x + 1, p0.y + 1);
	return lerp(lerp(a00, a10, f.x), lerp(a01, a11, f.x), f.y);
}

// Evaluates premultiplied RGBA (rgb = col * a, a = alpha) at unwarped screen-space OSD UV.
float4 zbc_osd_eval(float2 uv_s, float text_op, float logo_op, float logo_style, float2 asp)
{
	float4 acc = float4(0.0, 0.0, 0.0, 0.0);

	// 1. Logo
	float logo_x = bus_zbc_osd_layout.x;
	float logo_y = bus_zbc_osd_layout.y;
	float logo_w = max(bus_zbc_osd_layout.z, 0.0001);
	float logo_h = logo_w * asp.x;
	if (logo_op > 0.001 && logo_style < 2.5
	 && uv_s.x >= logo_x && uv_s.x < logo_x + logo_w
	 && uv_s.y >= logo_y && uv_s.y < logo_y + logo_h)
	{
		float2 luv = float2((uv_s.x - logo_x) / logo_w, (uv_s.y - logo_y) / logo_h);
		float  la  = 0.0;
		if (logo_style < 0.5)
		{
			la = zbc_osd_logo_sample(luv);
		}
		else
		{
			float swirl = (logo_style < 1.5) ? 1.0 : 0.0;
			float d     = zbc_logo_sd(luv, swirl);
			float fw    = max(1.0 / max(logo_w * screen_res.x, 1.0), 0.0005);
			la = saturate(0.5 - d / fw);
		}
		float  src_a = saturate(la * logo_op);
		float3 src_p = float3(1.0, 0.882, 0.0) * src_a;
		acc.rgb = src_p + acc.rgb * (1.0 - src_a);
		acc.a   = src_a + acc.a   * (1.0 - src_a);
	}

	// 2. Three right-aligned text lines (O(1) char lookup across at most 2 overlapping cells)
	float em_v = max(bus_zbc_osd_layout.w, 0.001);
	if (text_op > 0.001)
	{
		float em_u     = em_v / asp.x;
		float right_u  = logo_x - (0.004 / 0.035) * logo_w;
		float top_v    = logo_y * (3.0 / 2.6);
		float adv_u    = (33.0 / 64.0) * em_u;
		float cell_w_u = (43.0 / 64.0) * em_u;
		float cell_h_v = (81.0 / 64.0) * em_v;
		float pad_u    = (5.0 / 64.0) * em_u;
		float pad_v    = (5.0 / 64.0) * em_v;

		[loop] for (uint i = 0u; i < 3u; i++)
		{
			float y0_v = top_v + (float)i * em_v - pad_v;
			if (uv_s.y >= y0_v && uv_s.y < y0_v + cell_h_v)
			{
				uint len_i = zbc_osd_len(i);
				if (len_i > 0u)
				{
					float x0_u  = right_u - (float)len_i * adv_u - pad_u;
					float end_u = x0_u + (float)(len_i - 1u) * adv_u + cell_w_u;
					if (uv_s.x >= x0_u && uv_s.x < end_u)
					{
						float gy  = (uv_s.y - y0_v) / cell_h_v;
						int   c0  = (int)floor((uv_s.x - x0_u) / adv_u);
						[loop] for (int dc = -1; dc <= 0; dc++)
						{
							int ci = c0 + dc;
							if (ci >= 0 && ci < (int)len_i)
							{
								float cx0 = x0_u + (float)ci * adv_u;
								if (uv_s.x >= cx0 && uv_s.x < cx0 + cell_w_u)
								{
									float  gx    = (uv_s.x - cx0) / cell_w_u;
									uint   ch    = zbc_osd_char_at(i, (uint)ci);
									float2 la    = zbc_osd_glyph_sample(ch, float2(gx, gy));
									float  src_a = saturate(la.y * text_op);
									if (src_a > 0.0001)
									{
										float3 src_p = la.xxx * src_a;
										acc.rgb = src_p + acc.rgb * (1.0 - src_a);
										acc.a   = src_a + acc.a   * (1.0 - src_a);
									}
								}
							}
						}
					}
				}
			}
		}
	}

	return acc;
}

// "REC " + hours (2 digits, 3 from 100 h) + ":MM:SS"; must match rec_text() in scripts\zbc_bodycam.script
uint zbc_rec_hours(uint secs)  { return min(secs / 3600u, 999u); }
uint zbc_rec_hdigits(uint secs) { return (zbc_rec_hours(secs) >= 100u) ? 3u : 2u; }

uint zbc_rec_char(uint i, uint secs, uint nh)
{
	if (i < 4u)
		return (i == 0u) ? 82u : ((i == 1u) ? 69u : ((i == 2u) ? 67u : 32u));   // "REC "
	uint j = i - 4u;
	if (j < nh)
	{
		uint p   = nh - 1u - j;
		uint div = (p == 0u) ? 1u : ((p == 1u) ? 10u : 100u);
		return 48u + (zbc_rec_hours(secs) / div) % 10u;
	}
	j -= nh;
	uint m = (secs / 60u) % 60u;
	uint s = secs % 60u;
	if (j == 0u || j == 3u) return 58u;           // ':'
	if (j == 1u) return 48u + m / 10u;
	if (j == 2u) return 48u + m % 10u;
	if (j == 4u) return 48u + s / 10u;
	return 48u + s % 10u;
}

// Top-left recording timer: red dot (same look as hud\zbc_dot) + "REC HH:MM:SS", premultiplied RGBA.
// Mirrors the top-right layout: same margin as the logo, on the first text line.
float4 zbc_rec_eval(float2 uv_s, float text_op, float2 asp)
{
	float4 acc    = float4(0.0, 0.0, 0.0, 0.0);
	float  em_v   = max(bus_zbc_osd_layout.w, 0.001);
	float  em_u   = em_v / asp.x;
	float  left_u = 1.0 - bus_zbc_osd_layout.x - max(bus_zbc_osd_layout.z, 0.0001);
	float  top_v  = bus_zbc_osd_layout.y * (3.0 / 2.6);
	float  half_v = 0.5 * ZBC_REC_DOT_D * em_v;

	// 1. Dot (blinks at 1 Hz from the script)
	if (bus_zbc_rec.y > 0.5)
	{
		float2 c = float2(left_u + half_v / asp.x, top_v + ZBC_REC_DOT_CY * em_v);
		float  r = length(float2((uv_s.x - c.x) * asp.x, uv_s.y - c.y)) / half_v;   // 0 centre .. 1 edge of its square
		if (r < 1.0)
		{
			float  fw    = max(screen_res.w / half_v, 0.0001);
			float  a     = saturate((0.95 - r) / fw);
			float  core  = saturate((0.66 - r) / fw);
			float  src_a = saturate(max(a * 0.55, core) * text_op);
			float3 src_p = float3(0.92, 0.12, 0.09) * core * text_op;
			acc.rgb = src_p + acc.rgb * (1.0 - src_a);
			acc.a   = src_a + acc.a   * (1.0 - src_a);
		}
	}

	// 2. Text, left-aligned after the dot
	float adv_u    = (33.0 / 64.0) * em_u;
	float cell_w_u = (43.0 / 64.0) * em_u;
	float cell_h_v = (81.0 / 64.0) * em_v;
	float pad_u    = (5.0 / 64.0) * em_u;
	float pad_v    = (5.0 / 64.0) * em_v;
	float y0_v     = top_v - pad_v;
	if (uv_s.y >= y0_v && uv_s.y < y0_v + cell_h_v)
	{
		uint  secs = (uint)max(bus_zbc_rec.z, 0.0);
		uint  nh   = zbc_rec_hdigits(secs);
		uint  len  = 10u + nh;
		float x0_u = left_u + 2.0 * half_v / asp.x + ZBC_REC_GAP * em_u - pad_u;
		float gy   = (uv_s.y - y0_v) / cell_h_v;
		int   c0   = (int)floor((uv_s.x - x0_u) / adv_u);
		[loop] for (int dc = -1; dc <= 0; dc++)
		{
			int ci = c0 + dc;
			if (ci >= 0 && ci < (int)len)
			{
				float cx0 = x0_u + (float)ci * adv_u;
				if (uv_s.x >= cx0 && uv_s.x < cx0 + cell_w_u)
				{
					uint   ch    = zbc_rec_char((uint)ci, secs, nh);
					float2 la    = zbc_osd_glyph_sample(ch, float2((uv_s.x - cx0) / cell_w_u, gy));
					float  src_a = saturate(la.y * text_op);
					if (src_a > 0.0001)
					{
						acc.rgb = la.xxx * src_a + acc.rgb * (1.0 - src_a);
						acc.a   = src_a + acc.a * (1.0 - src_a);
					}
				}
			}
		}
	}
	return acc;
}

float4 zbc_osd_layer(bool rec, float2 uv_s, float text_op, float logo_op, float logo_style, float2 asp)
{
	if (rec) return zbc_rec_eval(uv_s, text_op, asp);
	return zbc_osd_eval(uv_s, text_op, logo_op, logo_style, asp);
}

// 5-tap CMOS look (RGB split + vertical bleed + noise) for one overlay layer, composited onto the image.
void zbc_osd_filter(inout float3 image, float2 uv, float2 uv_o, bool rec, float text_op, float logo_op, float logo_style,
	float2 asp, float ca_px, float dy_px, inout float osd_mask)
{
	float4 c_r  = float4(0.0, 0.0, 0.0, 0.0);
	float4 c_g  = float4(0.0, 0.0, 0.0, 0.0);
	float4 c_b  = float4(0.0, 0.0, 0.0, 0.0);
	float4 v_up = float4(0.0, 0.0, 0.0, 0.0);
	float4 v_dn = float4(0.0, 0.0, 0.0, 0.0);

	[loop] for (int t_i = 0; t_i < 5; t_i++)
	{
		float2 off = float2(0.0, 0.0);
		if      (t_i == 0) off = float2( ca_px,  0.0);
		else if (t_i == 2) off = float2(-ca_px,  0.0);
		else if (t_i == 3) off = float2( 0.0,   -dy_px);
		else if (t_i == 4) off = float2( 0.0,    dy_px);
		float4 sv = zbc_osd_layer(rec, uv_o + off, text_op, logo_op, logo_style, asp);
		if      (t_i == 0) c_r  = sv;
		else if (t_i == 1) c_g  = sv;
		else if (t_i == 2) c_b  = sv;
		else if (t_i == 3) v_up = sv;
		else               v_dn = sv;
	}

	if (max(max(c_g.a, max(c_r.a, c_b.a)), max(v_up.a, v_dn.a)) > 0.0001)
	{
		float4 v_avg = 0.5 * (v_up + v_dn);
		c_r = lerp(c_r, v_avg, 0.20);
		c_g = lerp(c_g, v_avg, 0.20);
		c_b = lerp(c_b, v_avg, 0.20);

		float2 px    = floor(uv * screen_res.xy);
		float2 t_off = floor(timers.x * 30.0) * float2(37.0, 17.0);
		float  osd_n = (zbc_hash(px + t_off) - 0.5) * 0.05 * (0.4 + 0.6 * saturate(bus_zbc_extra.z));

		c_r.r = clamp(c_r.r + osd_n * c_r.a, 0.0, c_r.a);
		c_g.g = clamp(c_g.g + osd_n * c_g.a, 0.0, c_g.a);
		c_b.b = clamp(c_b.b + osd_n * c_b.a, 0.0, c_b.a);

		image.r = image.r * (1.0 - c_r.a) + c_r.r;
		image.g = image.g * (1.0 - c_g.a) + c_g.g;
		image.b = image.b * (1.0 - c_b.a) + c_b.b;

		osd_mask = saturate((c_r.a + c_g.a + c_b.a) * (1.0 / 3.0));
	}
}

// Top-left recording timer.
void zbc_rec_composite(inout float3 image, float2 uv, float2 uv_o, float2 asp, float ca_px, float dy_px, inout float osd_mask)
{
	float text_op = saturate(bus_zbc_rec.w);
	if (text_op <= 0.001)
		return;
	float  em_v    = max(bus_zbc_osd_layout.w, 0.001);
	float  em_u    = em_v / asp.x;
	float  left_u  = 1.0 - bus_zbc_osd_layout.x - max(bus_zbc_osd_layout.z, 0.0001);
	float  top_v   = bus_zbc_osd_layout.y * (3.0 / 2.6);
	uint   len     = 10u + zbc_rec_hdigits((uint)max(bus_zbc_rec.z, 0.0));
	float2 r_min   = float2(left_u, top_v - (5.0 / 64.0) * em_v);
	float2 r_max   = float2(left_u + (ZBC_REC_DOT_D + ZBC_REC_GAP) * em_u + (float)len * (33.0 / 64.0) * em_u + (10.0 / 64.0) * em_u,
	                        r_min.y + (81.0 / 64.0) * em_v);
	float2 pad_roi = float2(ca_px + screen_res.z, dy_px + screen_res.w);
	if (uv_o.x < r_min.x - pad_roi.x || uv_o.x > r_max.x + pad_roi.x
	 || uv_o.y < r_min.y - pad_roi.y || uv_o.y > r_max.y + pad_roi.y)
		return;
	zbc_osd_filter(image, uv, uv_o, true, text_op, 0.0, 3.0, asp, ca_px, dy_px, osd_mask);
}

// Top-right Axon overlay.
void zbc_osd_right(inout float3 image, float2 uv, float2 uv_o, float2 asp, float ca_px, float dy_px, inout float osd_mask)
{
	float  text_op    = saturate(bus_zbc_osd_info.z);
	float  logo_op    = saturate(bus_zbc_osd_info.w);
	float  logo_style = bus_zbc_osd_info.y;

	// Tight active OSD bounding rect (logo + max active lines + filter pad) to skip empty quadrant pixels
	float  logo_x   = bus_zbc_osd_layout.x;
	float  logo_y   = bus_zbc_osd_layout.y;
	float  logo_w   = max(bus_zbc_osd_layout.z, 0.0001);
	float2 osd_min  = float2(10.0, 10.0);
	float2 osd_max  = float2(-10.0, -10.0);
	if (logo_op > 0.001 && logo_style < 2.5)
	{
		osd_min = float2(logo_x, logo_y);
		osd_max = float2(logo_x + logo_w, logo_y + logo_w * asp.x);
	}
	if (text_op > 0.001)
	{
		uint len0    = zbc_osd_len(0u);
		uint len1    = zbc_osd_len(1u);
		uint len2    = zbc_osd_len(2u);
		uint max_len = max(len0, max(len1, len2));
		if (max_len > 0u)
		{
			float em_v     = max(bus_zbc_osd_layout.w, 0.001);
			float em_u     = em_v / asp.x;
			float right_u  = logo_x - (0.004 / 0.035) * logo_w;
			float top_v    = logo_y * (3.0 / 2.6);
			float adv_u    = (33.0 / 64.0) * em_u;
			float cell_w_u = (43.0 / 64.0) * em_u;
			float cell_h_v = (81.0 / 64.0) * em_v;
			float pad_u    = (5.0 / 64.0) * em_u;
			float pad_v    = (5.0 / 64.0) * em_v;
			uint  first_i  = (len0 > 0u) ? 0u : ((len1 > 0u) ? 1u : 2u);
			uint  last_i   = (len2 > 0u) ? 2u : ((len1 > 0u) ? 1u : 0u);
			float tx0      = right_u - (float)max_len * adv_u - pad_u;
			float tx1      = right_u - adv_u - pad_u + cell_w_u;
			float ty0      = top_v + (float)first_i * em_v - pad_v;
			float ty1      = top_v + (float)last_i  * em_v - pad_v + cell_h_v;
			osd_min = min(osd_min, float2(tx0, ty0));
			osd_max = max(osd_max, float2(tx1, ty1));
		}
	}
	float2 pad_roi = float2(ca_px + screen_res.z, dy_px + screen_res.w);
	if (uv_o.x < osd_min.x - pad_roi.x || uv_o.x > osd_max.x + pad_roi.x
	 || uv_o.y < osd_min.y - pad_roi.y || uv_o.y > osd_max.y + pad_roi.y)
		return;

	zbc_osd_filter(image, uv, uv_o, false, text_op, logo_op, logo_style, asp, ca_px, dy_px, osd_mask);
}

// Composites the top-right Axon overlay and the top-left recording timer directly onto linear scene color
// before sensor compression/grain/vignette.
void zbc_osd_composite(inout float3 image, float2 uv, inout float osd_mask)
{
	osd_mask = 0.0;
	bool rec_on   = bus_zbc_rec.x > 0.5 && uv.x <= 0.45 && uv.y <= 0.22;
	bool right_on = bus_zbc_osd_info.x > 0.5 && uv.x >= 0.55 && uv.y <= 0.22;
	[branch] if (rec_on || right_on)
	{
		float2 asp = zbc_aspect();

		// Tiny rolling-shutter horizontal shear only (NO fisheye barrel warp)
		float2 uv_o = uv;
		uv_o.x += bus_zbc_sensor.z * 0.35 * (uv.y - 0.5) * ZBC_INTENSITY;

		float ca_px = screen_res.z * (0.65 + 0.55 * saturate(bus_zbc_lens.y));
		float dy_px = screen_res.w * 0.70;

		[branch] if (rec_on)
			zbc_rec_composite(image, uv, uv_o, asp, ca_px, dy_px, osd_mask);
		else
			zbc_osd_right(image, uv, uv_o, asp, ca_px, dy_px, osd_mask);
	}
}

#endif
