// Zone Bodycam - top-right Axon overlay rendered inside postprocess (after lens warp, before sensor compression, grain, and vignette).
#ifndef ZBC_OSD_H
#define ZBC_OSD_H

#include "zbc_lens.h"
#include "zbc_logo.h"

uniform float4 bus_zbc_osd_info;         // x: active (>0.5), y: logo_style (0=official, 1=swirl, 2=plain, 3=none), z: text_opacity, w: logo_opacity
uniform float4 bus_zbc_osd_layout;       // x: logo_x (0.950), y: logo_y (0.026*asp.x), z: logo_w (0.035), w: em_v (em_px / H)
uniform uint4  bus_zbc_osd_chars[31];    // row 0: (len0, len1, len2, 0); row 1+i*10+(c>>2) comp (c&3) = ASCII byte
uniform uint4  bus_zbc_osd_atlas[816];   // rows 0..751: ASCII 33..126 16x32 2-bit (8 uint4s/glyph); rows 752..815: 64x64 2-bit logo

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
		float right_u  = 0.946;
		float top_v    = 0.030 * asp.x;
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

// Composites the top-right Axon overlay directly onto linear scene color before sensor compression/grain/vignette.
void zbc_osd_composite(inout float3 image, float2 uv, inout float osd_mask)
{
	osd_mask = 0.0;
	[branch] if (bus_zbc_osd_info.x > 0.5 && uv.x >= 0.60 && uv.y <= 0.18)
	{
		float  text_op    = saturate(bus_zbc_osd_info.z);
		float  logo_op    = saturate(bus_zbc_osd_info.w);
		float  logo_style = bus_zbc_osd_info.y;
		float2 asp        = zbc_aspect();

		// Tiny rolling-shutter horizontal shear only (NO fisheye barrel warp)
		float2 uv_o = uv;
		uv_o.x += bus_zbc_sensor.z * 0.35 * (uv.y - 0.5) * ZBC_INTENSITY;

		float ca_px = screen_res.z * (0.65 + 0.55 * saturate(bus_zbc_lens.y));
		float dy_px = screen_res.w * 0.70;

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
			float4 sv = zbc_osd_eval(uv_o + off, text_op, logo_op, logo_style, asp);
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
}

#endif
