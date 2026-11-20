// Zone Bodycam - VHS-style battery gauge shape (camcorder viewfinder icon): outline, terminal nub, 4 bars.
// Shared by the in-lens overlay (zbc_osd.h) and the HUD static (zbc_batt.ps) so both draw the same thing.
// Units are em (the overlay text height); p = (0,0) at the icon's top-left, y down.
// Geometry in em: keep in step with BATT_* in scripts\zbc_bodycam.script.
#ifndef ZBC_BATT_INCLUDED
#define ZBC_BATT_INCLUDED

#define ZBC_BATT_BODY_W 1.75
#define ZBC_BATT_H      0.90
#define ZBC_BATT_NUB_W  0.15
#define ZBC_BATT_NUB_H  0.42
#define ZBC_BATT_W      (ZBC_BATT_BODY_W + ZBC_BATT_NUB_W)
#define ZBC_BATT_T      0.11    // outline
#define ZBC_BATT_PAD    0.07    // outline to bars
#define ZBC_BATT_GAP    0.07    // between bars
#define ZBC_BATT_ABOVE  0.22    // gap between the icon's bottom and the top of the red dot's square

// anti-aliased coverage of the axis-aligned box [a, b] at p (fw = one pixel in em)
float zbc_batt_box(float2 p, float2 a, float2 b, float fw)
{
	float2 d = min(p - a, b - p);
	return saturate((min(d.x, d.y) + 0.5 * fw) / fw);
}

// coverage 0..1 of the icon with `bars` (0..4) lit; last_on < 0.5 hides the last of them (it flashes)
float zbc_batt_cov(float2 p, float bars, float last_on, float fw)
{
	float outer = zbc_batt_box(p, float2(0.0, 0.0), float2(ZBC_BATT_BODY_W, ZBC_BATT_H), fw);
	float inner = zbc_batt_box(p, float2(ZBC_BATT_T, ZBC_BATT_T), float2(ZBC_BATT_BODY_W - ZBC_BATT_T, ZBC_BATT_H - ZBC_BATT_T), fw);
	float c = outer * (1.0 - inner);
	c = max(c, zbc_batt_box(p, float2(ZBC_BATT_BODY_W - 0.5 * fw, 0.5 * (ZBC_BATT_H - ZBC_BATT_NUB_H)),
	                           float2(ZBC_BATT_W, 0.5 * (ZBC_BATT_H + ZBC_BATT_NUB_H)), fw));
	float x0 = ZBC_BATT_T + ZBC_BATT_PAD;
	float x1 = ZBC_BATT_BODY_W - ZBC_BATT_T - ZBC_BATT_PAD;
	float y0 = ZBC_BATT_T + ZBC_BATT_PAD;
	float y1 = ZBC_BATT_H - ZBC_BATT_T - ZBC_BATT_PAD;
	float bw = (x1 - x0 - 3.0 * ZBC_BATT_GAP) * 0.25;
	[unroll] for (int i = 0; i < 4; i++)
	{
		if ((float)i < bars - 0.5 && ((float)i < bars - 1.5 || last_on > 0.5))
		{
			float bx = x0 + (float)i * (bw + ZBC_BATT_GAP);
			c = max(c, zbc_batt_box(p, float2(bx, y0), float2(bx + bw, y1), fw));
		}
	}
	return c;
}

#endif
