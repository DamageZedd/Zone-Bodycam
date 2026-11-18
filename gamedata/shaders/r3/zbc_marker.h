// Zone Bodycam - ally marker shapes (HUD layer, procedural). Vertex colour = marker colour and opacity.
// Strokes are measured in screen pixels with fwidth, so they stay crisp at any marker size.
#ifndef ZBC_MARKER_H
#define ZBC_MARKER_H

// colour core from 0.75 to 2.75 px in from the edge, dark outline around it
float4 zbc_stroke(float d, float3 col)
{
	float outline = saturate(3.5 - d) * saturate(d + 0.5);
	float core    = saturate(d - 0.75) * saturate(2.75 - d);
	float a       = max(outline * 0.55, core);
	float3 rgb    = col * (core / max(a, 0.0001));
	return float4(rgb, a);
}

float4 zbc_marker_out(float4 c, float opacity)
{
	c.a *= opacity;
	if (HDR10_IS_ENABLED)
		c.rgb = HDR10_ToDisplay_UI(c.rgb, HDR10_UI_NITS_SCALAR, c.a);
	return c;
}

#endif