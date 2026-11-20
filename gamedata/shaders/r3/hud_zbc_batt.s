-- Zone Bodycam: HUD layer shader "hud\zbc_batt" (procedural VHS battery gauge). Binds the base texture like the engine's
-- hud_default.s does: the UI code expects every HUD shader to have one.
function normal(shader, t_base, t_second, t_detail)
	shader:begin("stub_notransform_t", "zbc_batt")
		: blend(true, blend.srcalpha, blend.invsrcalpha)
		: zb(false, false)
		: aref(true, 0)
	shader:dx10texture("s_base", t_base)
	shader:dx10sampler("smp_base"):clamp()
end
