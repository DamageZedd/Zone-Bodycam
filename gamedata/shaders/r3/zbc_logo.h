// Zone Bodycam - procedural camera logo (signed distance fields, resolution independent, no texture).
// The HUD static is a square; I.Tex0 runs 0..1 across it, y down.
#ifndef ZBC_LOGO_H
#define ZBC_LOGO_H

// Equilateral triangle pointing up, centred on its centroid, y up. r = half the side. (after I. Quilez)
float zbc_sd_tri(float2 p, float r)
{
	const float k = 1.7320508;
	p.x = abs(p.x) - r;
	p.y = p.y + r / k;
	if (p.x + k * p.y > 0.0)
		p = float2(p.x - k * p.y, -k * p.x - p.y) * 0.5;
	p.x -= clamp(p.x, -2.0 * r, 0.0);
	return -length(p) * sign(p.y);
}

// swirl: 0 = plain rounded triangle, 1 = triangle split into three blades by a swirl, as on bodycam overlays
float zbc_logo_sd(float2 uv, float swirl)
{
	const float side = 0.94;
	const float h    = side * 0.8660254;
	const float top  = (1.0 - h) * 0.5;
	float2 c = float2(0.5, top + h * (2.0 / 3.0));     // centroid in the square
	float2 p = float2(uv.x - c.x, c.y - uv.y);         // centroid origin, y up

	const float rr = 0.035;                            // corner rounding
	float d = zbc_sd_tri(p, side * 0.5 - rr * 1.7320508) - rr;

	[branch] if (swirl > 0.5)
	{
		const float R = side / 1.7320508;              // circumradius
		float2 q   = p / R;
		float  rho = length(q);
		float  t   = saturate(rho);
		float  gap = 1000.0;
		[unroll] for (int i = 0; i < 3; i++)
		{
			// the three cuts leave the edges at 104, -16 and 224 degrees and curl into the centre
			// (tuned against the reference logo with an offline render of this exact function)
			float e = radians(104.0 - 120.0 * i);
			float a = e + 1.8 * (1.0 - t) * (1.0 - t);
			float2 on_curve = float2(cos(a), sin(a)) * rho;
			gap = min(gap, length(q - on_curve) - 0.10);
		}
		d = max(d, -gap * R);
	}
	return d;
}

// anti-aliased coverage
float zbc_logo_cover(float2 uv, float swirl)
{
	float d  = zbc_logo_sd(uv, swirl);
	float fw = max(fwidth(d), 0.0005);
	return saturate(0.5 - d / fw);
}

#endif
