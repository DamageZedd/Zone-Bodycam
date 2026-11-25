"""Zone Bodycam - builds the Axon Body 5 (2026) 1:1 item model in Blender.

Run inside Blender with __file__ set (export_variant.py does this):
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
Creates the scene "zbc_bodycam_5", every part its own single-material object, ready for export_variant.py.

Photogrammetric & photometric ground truth:
- Calibrated directly to Axon's launch front ortho (ab5_og_crop.png at 10.267 px/mm -> 62.6 W x 99.6 H x 28.0 D mm)
  and 3/4 studio renders (ab5_l.png, ab5_r.png, ab5_bottom_regions.jpg, ab5_leds2.png).
- Entire front housing is ONE continuous stealth-faceted polyhedral surface (explicit bmesh vertex/edge planar
  facet graph with zero boolean-hull stair-stepping and no floating centre plate), finished in deep matte tactical
  charcoal micro-stipple (zbc_5_body, baked 1024x1024).
Units are metres in Blender, millimetres below. Front faces -Y, +Z is up, +X is right as seen from the front.
"""
import math
import os
import bpy
import bmesh
from mathutils import Matrix, Vector

SCENE = "zbc_bodycam_5"
COMMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "axon_common.py")
exec(compile(open(COMMON, encoding="utf-8").read(), COMMON, "exec"), globals())
setup_scene()
std_materials()

# ---- core envelope (mm)
W, H, D = 62.6, 99.6, 28.0
hw, hh = W / 2.0, H / 2.0
Z_TOP, Z_BOT = hh, -hh
Y0 = -D / 2.0                     # -14.0 mm: outer front silhouette plane
YB = D / 2.0                      # +14.0 mm: rear housing plane
BAKED = ("zbc_5_body", "zbc_5_pad")

LENS = (0.0, 25.8)
BTN = (0.0, -11.4)

# ---- Body 5 camera-scoped materials (1 material per object; shared Body 4 DDSs untouched)
def _add_micro_stipple(mat, base_rgb, lo_mul, hi_mul, scale, bump_strength, rough):
    """Link subtle world-space 3D micro-stipple colour + bump so Cycles DIFFUSE bake captures real grain."""
    nt = mat.node_tree
    N, L = nt.nodes, nt.links
    bsdf = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = rough
    for n in list(N):
        if n.type in ("TEX_NOISE", "BUMP"):
            N.remove(n)
    tc = N.new("ShaderNodeTexCoord")
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 3.0
    nz.inputs["Roughness"].default_value = 0.65
    L.new(tc.outputs["Object"], nz.inputs["Vector"])

    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*(max(0.0, c * lo_mul) for c in base_rgb), 1.0)
    mix.inputs["B"].default_value = (*(min(1.0, c * hi_mul) for c in base_rgb), 1.0)
    L.new(nz.outputs["Fac"], mix.inputs["Factor"])
    L.new(mix.outputs["Result"], bsdf.inputs["Base Color"])

    bp = N.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump_strength
    bp.inputs["Distance"].default_value = 0.00005
    L.new(nz.outputs["Fac"], bp.inputs["Height"])
    L.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    mat["baked"] = True
    return mat


# sRGB ~#202226 -> linear ~(0.0146, 0.0160, 0.0196)
M_5_BODY = _add_micro_stipple(
    own_material("zbc_5_body", (0.0146, 0.0160, 0.0196), 0.56, spec=0.45),
    (0.0146, 0.0160, 0.0196), 0.84, 1.18, scale=420.0, bump_strength=0.16, rough=0.56,
)
# Soft-touch elastomer button pad: slightly darker/warmer matte micro-grain
M_5_PAD = _add_micro_stipple(
    own_material("zbc_5_pad", (0.0125, 0.0132, 0.0152), 0.64, spec=0.36),
    (0.0125, 0.0132, 0.0152), 0.88, 1.14, scale=650.0, bump_strength=0.12, rough=0.64,
)
M_5_GREEN = own_material("zbc_5_green", (0.42, 0.88, 0.04), 0.24, emission=(0.30, 0.75, 0.03))
M_5_BEZEL = own_material("zbc_5_bezel", (0.020, 0.022, 0.026), 0.34, metal=0.60, spec=0.65)


# ------------------------------------------------------------------------------------------------
# 1. Unified Stealth-Faceted Polyhedral Front + Clamshell Body (explicit bmesh graph, zero floating plate)
# ------------------------------------------------------------------------------------------------
def _arc_corner(p_prev, p_corner, p_next, r_mm, seg=3):
    """Round 2D corner p_corner between p_prev and p_next with radius r_mm (returns list of (x, z) points)."""
    p = Vector(p_corner)
    da = Vector(p_prev) - p
    db = Vector(p_next) - p
    la, lb = da.length, db.length
    da.normalize()
    db.normalize()
    ang = math.acos(max(-1.0, min(1.0, da.dot(db))))
    d = min(r_mm / math.tan(ang / 2.0), la * 0.45, lb * 0.45)
    rr = d * math.tan(ang / 2.0)
    p1, p2 = p + da * d, p + db * d
    c = p + (da + db).normalized() * (rr / math.sin(ang / 2.0))
    a1 = math.atan2(p1.y - c.y, p1.x - c.x)
    a2 = math.atan2(p2.y - c.y, p2.x - c.x)
    da_ = (a2 - a1 + math.pi) % (2.0 * math.pi) - math.pi
    return [(c.x + rr * math.cos(a1 + da_ * k / seg), c.y + rr * math.sin(a1 + da_ * k / seg)) for k in range(seg + 1)]


def build_stealth_body():
    """Construct the closed manifold Axon Body 5 housing from an explicit symmetric planar-facet vertex graph."""
    bm = bmesh.new()

    # Exact coplanar ear-shield height law: slopes gently down-outward from inner crest (|x|=11.8, h=3.15)
    # to outer crest (|x|=21.2, h=2.65) so +X ear catches top-right light and -X ear stays dark charcoal.
    def h_ear(x_abs):
        return 3.15 - 0.0531915 * (x_abs - 11.8)

    # Rounded outer corners (CORNER_R = 1.6 mm) & matching inner rim corners (r = 1.2 mm)
    ot2_arc = _arc_corner((8.8, 49.8), (17.6, 49.8), (31.3, 40.6), 1.6, seg=3)
    otr_arc = _arc_corner((17.6, 49.8), (31.3, 40.6), (31.3, 33.8), 1.6, seg=3)
    obr_arc = _arc_corner((31.3, -33.8), (31.3, -40.8), (20.6, -49.8), 1.6, seg=3)
    ob2_arc = _arc_corner((31.3, -40.8), (20.6, -49.8), (0.0, -49.8), 1.6, seg=3)

    rt2_arc = _arc_corner((8.8, 48.3), (17.0, 48.3), (29.7, 39.8), 1.2, seg=3)
    rtr_arc = _arc_corner((17.0, 48.3), (29.7, 39.8), (29.7, 33.8), 1.2, seg=3)
    rbr_arc = _arc_corner((29.7, -33.8), (29.7, -40.2), (19.8, -48.4), 1.2, seg=3)
    rb2_arc = _arc_corner((29.7, -40.2), (19.8, -48.4), (0.0, -48.4), 1.2, seg=3)

    # Right-half & centerline vertices: name -> (x_mm, z_mm, h_mm), where front Y = Y0 - h_mm
    V = {
        # Outer silhouette perimeter (h = 0.00, clockwise from top-center to bottom-center)
        "O_tc": (0.0, 49.8, 0.00),
        "O_t1": (8.8, 49.8, 0.00),
        "O_su": (31.3, 33.8, 0.00),
        "O_cu": (31.3, 29.8, 0.00),
        "O_cm1": (31.3, 3.2, 0.00),
        "O_cm2": (31.3, -5.2, 0.00),
        "O_cl": (31.3, -29.8, 0.00),
        "O_sl": (31.3, -33.8, 0.00),
        "O_bc": (0.0, -49.8, 0.00),

        # Inner convex perimeter rim
        "R_tc": (0.0, 48.3, 1.45),
        "R_t1": (8.8, 48.3, 1.55),
        "R_su": (29.7, 33.8, 1.85),
        "R_cu": (29.7, 29.8, 0.90),
        "R_cm1": (29.7, 3.2, 0.90),
        "R_cm2": (29.7, -5.2, 0.90),
        "R_cl": (29.7, -29.8, 0.90),
        "R_sl": (29.7, -33.8, 1.80),
        "R_bc": (0.0, -48.4, 1.10),

        # Upper Crown & IR Trapezoid (around IR window at (0, +39.6))
        "IR_t0": (0.0, 43.4, 3.25),
        "IR_t1": (4.0, 43.4, 3.25),
        "IR_s1": (9.4, 40.4, 3.15),
        "IR_b1": (4.0, 35.4, 3.05),
        "IR_b0": (0.0, 35.4, 3.05),

        # Central & X-Valley floor (h = 1.25 mm around lens & 4 green LED pockets)
        "VX_tc": (0.0, 33.8, 1.25),
        "VX_t1": (5.0, 33.8, 1.25),
        "VX_u1": (15.6, 41.2, 1.45),
        "VX_utip": (18.8, 40.8, 1.50),
        "VX_u2": (18.2, 38.2, 1.25),
        "VX_m1": (8.6, 30.8, 1.25),
        "VX_m2": (8.6, 20.8, 1.25),
        "VX_l2": (18.2, 13.0, 1.25),
        "VX_l1": (15.2, 9.2, 1.25),
        "VX_b1": (4.6, 18.0, 1.25),
        "VX_bc": (0.0, 18.0, 1.25),

        # Coplanar Ear Block (speaker grille shield, X in [11.8, 21.2], Z in [10.2, 43.8])
        "E_top": (21.2, 43.8, h_ear(21.2)),
        "E_pu": (17.8, 36.4, h_ear(17.8)),
        "E_pm1": (11.8, 29.8, h_ear(11.8)),
        "E_pm2": (11.8, 20.8, h_ear(11.8)),
        "E_pl": (17.8, 14.8, h_ear(17.8)),
        "E_bot": (21.2, 10.2, h_ear(21.2)),
        "E_om1": (21.2, 33.8, h_ear(21.2)),
        "E_om2": (21.2, 29.8, h_ear(21.2)),

        # Ambient Sensor Trapezoid (around sensor pill at (0, +13.0)) + micro-groove above button
        "SN_t0": (0.0, 16.4, 2.95),
        "SN_t1": (3.6, 16.4, 2.95),
        "SN_b1": (11.2, 8.8, 2.75),
        "SN_b0": (0.0, 8.8, 2.75),
        "BG_0": (0.0, 8.1, 2.30),
        "BG_1": (10.6, 8.1, 2.30),

        # Event Button Octagonal Ridge Crest & Deep Moat (button centered at (0, -11.4))
        "BC_t0": (0.0, 7.5, 2.75),
        "BC_t1": (10.2, 7.5, 2.75),
        "BC_tr": (19.8, -2.1, 2.70),
        "BC_br": (19.8, -22.2, 2.70),
        "BC_b2": (11.4, -33.6, 2.80),

        "BM_t0": (0.0, 5.2, 0.45),
        "BM_t1": (9.2, 5.2, 0.45),
        "BM_tr": (17.5, -3.1, 0.45),
        "BM_br": (17.5, -20.0, 0.45),
        "BM_b1": (8.6, -29.8, 0.45),
        "BM_b0": (0.0, -29.8, 0.45),
        "MF_0": (0.0, -11.4, 0.45),     # flat hidden moat floor center

        # Side Armor Shoulder (X = 21.2) & Recessed Side Screw Channel Floor (X = 24.2..29.7)
        "SA_u": (21.2, 3.2, 2.65),
        "SA_m1": (21.2, -2.1, 2.65),
        "SA_m2": (21.2, -22.2, 2.65),
        "SA_l": (21.2, -29.8, 2.60),

        "CH_tu": (23.6, 40.6, 1.95),
        "CH_su": (24.2, 33.8, 1.90),
        "CH_cu": (24.2, 29.8, 0.90),
        "CH_cm1": (24.2, 3.2, 0.90),
        "CH_cm2": (24.2, -5.2, 0.90),
        "CH_cl": (24.2, -29.8, 0.90),
        "CH_sl": (24.2, -32.4, 2.25),

        # Bottom AXON Pocket (2), Walls (3, 4), Chin Prism (5, 6), V-Valleys (7, 8), & Lower Cheeks (9)
        "AX_t0": (0.0, -33.2, 1.65),
        "AX_t1": (7.8, -33.2, 1.65),
        "AX_b1": (7.8, -40.6, 1.65),
        "AX_c1": (6.4, -41.4, 1.65),
        "AX_b0": (0.0, -41.4, 1.65),

        "VV_0": (7.8, -41.3, 1.25),     # V-valley root at lower corner of AXON pocket
        "CK_b1": (11.4, -40.2, 2.75),   # lower-inner crest of cheek 9
        "CK_b2": (21.2, -46.2, 1.90),   # lower-outer crest of cheek 9

        "CHIN_c0": (0.0, -43.4, 2.85),  # horizontal chin crest center
        "CHIN_c1": (5.6, -43.4, 2.85),  # horizontal chin crest corner
    }

    for k, (ax, az) in enumerate(ot2_arc):
        V[f"O_t2_{k}"] = (ax, az, 0.00)
    for k, (ax, az) in enumerate(otr_arc):
        V[f"O_tr_{k}"] = (ax, az, 0.00)
    for k, (ax, az) in enumerate(obr_arc):
        V[f"O_br_{k}"] = (ax, az, 0.00)
    for k, (ax, az) in enumerate(ob2_arc):
        V[f"O_b2_{k}"] = (ax, az, 0.00)

    for k, (ax, az) in enumerate(rt2_arc):
        V[f"R_t2_{k}"] = (ax, az, 1.50 + 0.15 * (k / 3.0))
    for k, (ax, az) in enumerate(rtr_arc):
        V[f"R_tr_{k}"] = (ax, az, 1.85)
    for k, (ax, az) in enumerate(rbr_arc):
        V[f"R_br_{k}"] = (ax, az, 1.75)
    for k, (ax, az) in enumerate(rb2_arc):
        V[f"R_b2_{k}"] = (ax, az, 1.35 - 0.20 * (k / 3.0))

    # Ordered outer & inner chains (top-center -> +X -> bottom-center)
    O_chain = (
        ["O_tc", "O_t1"]
        + [f"O_t2_{k}" for k in range(4)]
        + [f"O_tr_{k}" for k in range(4)]
        + ["O_su", "O_cu", "O_cm1", "O_cm2", "O_cl", "O_sl"]
        + [f"O_br_{k}" for k in range(4)]
        + [f"O_b2_{k}" for k in range(4)]
        + ["O_bc"]
    )
    R_chain = (
        ["R_tc", "R_t1"]
        + [f"R_t2_{k}" for k in range(4)]
        + [f"R_tr_{k}" for k in range(4)]
        + ["R_su", "R_cu", "R_cm1", "R_cm2", "R_cl", "R_sl"]
        + [f"R_br_{k}" for k in range(4)]
        + [f"R_b2_{k}" for k in range(4)]
        + ["R_bc"]
    )

    # Right-half face list (CCW in XZ when viewed from -Y -> normal points toward -Y)
    F = []

    # (a) Outer convex perimeter bevel around entire silhouette
    for i in range(len(O_chain) - 1):
        F.append([R_chain[i], R_chain[i + 1], O_chain[i + 1], O_chain[i]])

    # (b) Upper Crown & Brow facets
    F.extend([
        ["IR_t0", "IR_t1", "R_t1", "R_tc"],                 # symmetric top-center brow trapezoid
        ["IR_t1", "IR_s1", "VX_u1", "R_t1"],                # bright (+X,+Z) diamond brow facet!
        ["R_t1", "VX_u1", "VX_utip", "E_top", "R_t2_0"],    # upper-right brow mic facet (normal -X,+Z)
        # Top-right corner transition & upper screw boss lug (screw_1 at (26.5, 38.8))
        ["E_top", "R_t2_1", "R_t2_0"],
        ["E_top", "R_t2_2", "R_t2_1"],
        ["E_top", "CH_tu", "R_t2_3", "R_t2_2"],
        ["CH_tu", "R_tr_0", "R_t2_3"],
        ["CH_tu", "R_tr_1", "R_tr_0"],
        ["CH_tu", "R_tr_2", "R_tr_1"],
        ["CH_tu", "R_tr_3", "R_tr_2"],
        ["E_top", "E_om1", "CH_su", "CH_tu"],
        ["CH_tu", "CH_su", "R_su", "R_tr_3"],
    ])

    # (c) IR Plateau & its slopes into X-valley
    F.extend([
        ["IR_b0", "IR_b1", "IR_t1", "IR_t0"],
        ["IR_b1", "IR_s1", "IR_t1"],
        ["VX_tc", "VX_t1", "IR_b1", "IR_b0"],               # -Z step directly above lens
        ["VX_t1", "VX_u1", "IR_s1", "IR_b1"],               # slope into upper X-arm
    ])

    # (d) X-Valley floor & Central Lens Field (all coplanar at h = 1.25 mm)
    F.extend([
        ["VX_bc", "VX_b1", "VX_m2", "VX_m1", "VX_t1", "VX_tc"],  # flat central lens pad
        ["VX_t1", "VX_m1", "VX_u2", "VX_u1"],                    # upper X-arm floor (holds upper LED)
        ["VX_u1", "VX_u2", "VX_utip"],
        ["VX_b1", "VX_l1", "VX_l2", "VX_m2"],                    # lower X-arm floor (holds lower LED)
        ["VX_l1", "E_bot", "VX_l2"],
    ])

    # (e) Coplanar Ear Block (speaker shield) & its boomerang inner bevels into X-valley
    F.extend([
        # Boomerang inner bevel walls (blazing white on -X side, dark shadow on +X side!)
        ["VX_utip", "E_top", "E_pu"],
        ["VX_utip", "E_pu", "VX_u2"],
        ["VX_u2", "E_pu", "E_pm1", "VX_m1"],
        ["VX_m1", "E_pm1", "E_pm2", "VX_m2"],
        ["VX_m2", "E_pm2", "E_pl", "VX_l2"],
        ["VX_l2", "E_pl", "E_bot"],
        # Coplanar tilted ear plateau (holds 16 angled speaker capsule slots)
        ["E_pm1", "E_pu", "E_top", "E_om1", "E_om2", "E_bot", "E_pl", "E_pm2"],
    ])

    # (f) Ambient Sensor Trapezoid & Lower-X transition to Button Crest
    F.extend([
        ["SN_t0", "SN_t1", "VX_b1", "VX_bc"],               # +Z bright bevel below lens
        ["SN_t1", "SN_b1", "VX_l1", "VX_b1"],               # +X,+Z bright diagonal bevel beside lower LED
        ["SN_b0", "SN_b1", "SN_t1", "SN_t0"],               # sensor pill plateau
        ["BG_0", "BG_1", "SN_b1", "SN_b0"],                 # micro-groove upper lip
        ["BC_t0", "BC_t1", "BG_1", "BG_0"],                 # micro-groove lower lip up to button crest
        ["BG_1", "VX_l1", "SN_b1"],
        ["BC_t1", "VX_l1", "BG_1"],
        ["BC_t1", "BC_tr", "SA_u", "E_bot", "VX_l1"],       # valley mouth outside upper button chamfer
    ])

    # (g) Side Armor Shoulder & Recessed Vertical Side Screw Channel
    F.extend([
        # -Z ramp from upper screw boss down into side channel (dark under top light)
        ["E_om1", "E_om2", "CH_cu", "CH_su"],
        ["CH_su", "CH_cu", "R_cu", "R_su"],
        # Longitudinal +X bevel from X=21.2 down to channel floor X=24.2 (carries mid mic at (22.7, 4.4))
        ["E_om2", "E_bot", "CH_cm1", "CH_cu"],
        ["E_bot", "SA_u", "CH_cm1"],
        ["SA_u", "SA_m1", "CH_cm2", "CH_cm1"],
        ["SA_m1", "SA_m2", "CH_cl", "CH_cm2"],
        ["SA_m2", "SA_l", "CH_cl"],
        # Narrow shoulder between button crest & side bevel
        ["BC_tr", "BC_br", "SA_m2", "SA_m1"],
        ["BC_br", "BC_b2", "SA_l", "SA_m2"],
        # Flat recessed vertical screw channel floor (X in [24.2, 29.7])
        ["CH_cu", "CH_cm1", "R_cm1", "R_cu"],
        ["CH_cm1", "CH_cm2", "R_cm2", "R_cm1"],
        ["CH_cm2", "CH_cl", "R_cl", "R_cm2"],
        # +Z bright ramp climbing out of side channel onto lower cheek 9!
        ["SA_l", "CH_sl", "CH_cl"],
        ["CH_cl", "CH_sl", "R_sl", "R_cl"],
    ])

    # (h) Event Button Inner Funnel Bevels (1, 10) & Deep Moat Floor
    F.extend([
        ["BM_t0", "BM_t1", "BC_t1", "BC_t0"],               # top inner moat bevel (-Z)
        ["BM_t1", "BM_tr", "BC_tr", "BC_t1"],               # top-right inner moat bevel
        ["BM_tr", "BM_br", "BC_br", "BC_tr"],               # vertical inner moat bevel
        ["BM_b1", "BC_b2", "BC_br", "BM_br"],               # lower diagonal inner bevel (10 -> BRIGHT!)
        ["BM_b1", "AX_t1", "BC_b2"],                        # corner transition triangle
        ["AX_t0", "AX_t1", "BM_b1", "BM_b0"],               # (1) bottom inner funnel bevel (+Z -> BLAZING WHITE!)
        # Flat dark moat floor (hidden under btn_well / btn_pad)
        ["MF_0", "BM_t1", "BM_t0"],
        ["MF_0", "BM_tr", "BM_t1"],
        ["MF_0", "BM_br", "BM_tr"],
        ["MF_0", "BM_b1", "BM_br"],
        ["MF_0", "BM_b0", "BM_b1"],
    ])

    # (i) Exact Bottom Faceted Topology (ab5_bottom_regions.jpg 2, 3, 4, 5, 6, 7, 8, 9)
    F.extend([
        # (2) Flat recessed AXON pocket floor
        ["AX_b0", "AX_c1", "AX_b1", "AX_t1", "AX_t0"],
        # (3 & 4) Sloped side walls of AXON pocket (+X bright on left 3, -X dark on right 4)
        ["AX_b1", "CK_b1", "BC_b2", "AX_t1"],
        # (5) Upward-facing (+Z) bright ramp below AXON up to horizontal chin crest
        ["CHIN_c0", "CHIN_c1", "AX_c1", "AX_b0"],
        # (6) Downward-facing (-Z) dark underside below chin crest to bottom rim
        ["R_bc", "R_b2_0", "CHIN_c1", "CHIN_c0"],
        ["R_bc", "R_b2_1", "R_b2_0"],
        ["R_bc", "R_b2_2", "R_b2_1"],
        ["R_bc", "R_b2_3", "R_b2_2"],
        # (7 & 8 lower) Chin prism side flanks (+X,+Z blazing white on right, -X,+Z grey on left)
        ["CHIN_c1", "R_b2_0", "VV_0", "AX_c1"],
        ["AX_c1", "VV_0", "AX_b1"],
        # (7 & 8 upper) Upper V-valley walls dropping from cheek 9 (-X,-Z dark shadow on right 8!)
        ["VV_0", "CK_b1", "AX_b1"],
        ["VV_0", "CK_b2", "CK_b1"],
        ["VV_0", "R_b2_0", "CK_b2"],
        # (9) Raised lower armor cheek & bottom screw boss lug (screw_5 at (26.4, -40.2))
        ["BC_b2", "CK_b1", "CK_b2", "CH_sl", "SA_l"],
        ["CH_sl", "CK_b2", "R_br_2", "R_br_1", "R_br_0", "R_sl"],
        ["CK_b2", "R_b2_0", "R_br_3", "R_br_2"],
    ])

    # Instantiate right-half & mirrored left-half vertices in bmesh (welding x == 0 centerline)
    bm_r, bm_l = {}, {}
    for name, (x, z, h) in V.items():
        vr = bm.verts.new(v3(x, Y0 - h, z))
        bm_r[name] = vr
        if abs(x) < 1e-6:
            bm_l[name] = vr
        else:
            bm_l[name] = bm.verts.new(v3(-x, Y0 - h, z))

    for f_names in F:
        bm.faces.new([bm_r[n] for n in f_names])
        bm.faces.new([bm_l[n] for n in reversed(f_names)])

    # Extrude closed outer silhouette loop backward (+Y) with crisp front-armor parting groove & rear bevel
    # Closed CCW loop around perimeter (when viewed from -Y): right chain bottom->top, then left chain top->bottom
    perim_loop = [bm_r[n] for n in reversed(O_chain)] + [bm_l[n] for n in O_chain[1:-1]]
    n_p = len(perim_loop)

    # Profile stations along Y from Y0 (-14.0) to YB (+14.0): (y_mm, radial_inset_mm)
    # Includes crisp clamshell parting seam at Y = -9.5 mm visible in ab5_l.png & ab5_r.png!
    y_stations = [
        (-9.70, 0.00),
        (-9.45, 0.28),   # crisp front-to-rear clamshell parting groove
        (-9.20, 0.00),
        (YB - 2.50, 0.00),
        (YB - 1.75, 0.35),
        (YB - 0.95, 1.00),
        (YB - 0.30, 1.80),
        (YB, 2.60),
    ]

    # Compute 2D inward normal at each perimeter vertex for uniform radial inset
    p2d = [Vector((v.co.x / MM, v.co.z / MM)) for v in perim_loop]
    inward_2d = []
    for i in range(n_p):
        t0 = (p2d[i] - p2d[(i - 1) % n_p]).normalized()
        t1 = (p2d[(i + 1) % n_p] - p2d[i]).normalized()
        # For CCW loop, inward normal of edge t=(tx, tz) is (-tz, tx)
        n0 = Vector((-t0.y, t0.x))
        n1 = Vector((-t1.y, t1.x))
        m = (n0 + n1)
        if m.length < 1e-6:
            m = n0
        else:
            m.normalize()
            m /= max(0.5, m.dot(n0))
        inward_2d.append(m)

    prev_ring = perim_loop
    for y_mm, ins_mm in y_stations:
        cur_ring = [
            bm.verts.new(v3(p2d[i].x + inward_2d[i].x * ins_mm, y_mm, p2d[i].y + inward_2d[i].y * ins_mm))
            for i in range(n_p)
        ]
        for i in range(n_p):
            j = (i + 1) % n_p
            bm.faces.new([prev_ring[i], cur_ring[i], cur_ring[j], prev_ring[j]])
        prev_ring = cur_ring

    # Close back face (+Y normal)
    bm.faces.new(list(reversed(prev_ring)))

    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4 * MM)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return assign(finish(bm, "body"), M_5_BODY)


body = build_stealth_body()


# ------------------------------------------------------------------------------------------------
# 2. Lens Assembly, IR Window, Ambient Sensor Pill, 4 Green X-LEDs, & Tilted Capsule Speaker Grilles
# ------------------------------------------------------------------------------------------------
lx, lz = LENS
YL = Y0 - 1.25                    # X-valley floor level (-15.25 mm)
cut(["body"], lambda: disc("lens_pocket_cut", 7.4, lx, lz, YL + 1.4, YL - 4.0, seg=96))
assign(annulus("lens_gap", lx, lz, 6.95, 7.40, YL + 0.15, YL + 1.40, seg=96), M_HOLE)
assign(
    lathe(
        "lens_bezel", lx, lz,
        [(6.95, 1.35), (6.95, 0.05), (6.55, -0.22), (5.25, -0.22), (4.85, 0.25), (4.85, 1.15)],
        YL, seg=96,
    ),
    M_5_BEZEL,
)
assign(annulus("lens_inner_rim", lx, lz, 4.35, 4.86, YL + 0.28, YL + 1.20, seg=80, chamfer_front=0.10), M_SCREW)
assign(disc("lens_seat", 4.38, lx, lz, YL + 1.35, YL + 0.95, seg=72), M_HOLE)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=4.25 * MM)
for v in bm.verts:
    v.co.y *= 1.35 / 4.25
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 1e-7], context="VERTS")
glass = assign(finish(bm, "lens_glass"), M_GLASS)
glass.location = v3(lx, YL + 0.95, lz)

# Beveled recessed IR pill window at (0, +39.6)
Y_IR = Y0 - 3.15
ir_outer = [(x, 39.6 + z) for x, z in stadium_pts_2d(7.6, 3.8, seg_half=10)]
ir_inner = [(x, 39.6 + z) for x, z in stadium_pts_2d(6.3, 2.6, seg_half=10)]
boolean(
    body,
    hull(
        "ir_bevel_cut",
        [(x, Y_IR - 0.35, z) for x, z in ir_outer]
        + [(x, Y_IR - 2.5, z) for x, z in ir_outer]
        + [(x, Y_IR + 0.65, z) for x, z in ir_inner],
    ),
)
cut(["body"], lambda: prism_y("ir_bore_cut", ir_inner, Y_IR + 1.10, 2.5))
assign(prism_y("ir_seat", ir_inner, Y_IR + 1.10, 0.15), M_HOLE)
for ix, sx in enumerate((-1.5, 1.5)):
    assign(disc("ir_diode_%d" % ix, 0.75, sx, 39.6, Y_IR + 0.98, Y_IR + 0.80, seg=20), M_BEZEL)
assign(prism_y("ir_window", [(x, 39.6 + z) for x, z in stadium_pts_2d(6.2, 2.5, seg_half=10)], Y_IR + 0.78, 0.22,
               chamfer=0.08), M_GLASS)

# Beveled recessed Ambient Light Sensor pill at (0, +13.0)
Y_SN = Y0 - 2.85
sn_outer = [(x, 13.0 + z) for x, z in stadium_pts_2d(4.5, 2.1, seg_half=8)]
sn_inner = [(x, 13.0 + z) for x, z in stadium_pts_2d(3.5, 1.3, seg_half=8)]
boolean(
    body,
    hull(
        "sn_bevel_cut",
        [(x, Y_SN - 0.35, z) for x, z in sn_outer]
        + [(x, Y_SN - 2.5, z) for x, z in sn_outer]
        + [(x, Y_SN + 0.55, z) for x, z in sn_inner],
    ),
)
assign(prism_y("sensor_window", [(x, 13.0 + z) for x, z in stadium_pts_2d(3.45, 1.25, seg_half=8)], Y_SN + 0.60, 0.16,
               chamfer=0.06), M_5_BEZEL)

# Four angled lime-green LED bars in beveled dark pockets along the X-valley floor
ARMS = (
    (-12.4, 35.6, -38.0),
    (12.4, 35.6, 38.0),
    (-12.4, 15.2, 40.0),
    (12.4, 15.2, -40.0),
)
for i, (cx, cz, deg) in enumerate(ARMS):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    win_o = [(cx + u * c - v * s, cz + u * s + v * c) for u, v in (
        (-5.0, 0.0), (-3.7, 1.60), (3.7, 1.60), (5.0, 0.0), (3.7, -1.60), (-3.7, -1.60)
    )]
    win_i = [(cx + u * c - v * s, cz + u * s + v * c) for u, v in (
        (-4.1, 0.0), (-3.0, 0.98), (3.0, 0.98), (4.1, 0.0), (3.0, -0.98), (-3.0, -0.98)
    )]
    boolean(
        body,
        hull(
            "led_pocket_cut_%d" % i,
            [(a_, YL - 0.25, b_) for a_, b_ in win_o]
            + [(a_, YL - 2.5, b_) for a_, b_ in win_o]
            + [(a_, YL + 0.68, b_) for a_, b_ in win_i],
        ),
    )
    assign(prism_y("led_seat_%d" % i, win_i, YL + 0.72, 0.08), M_HOLE)
    led_pts = [(cx + u * c - v * s, cz + u * s + v * c) for u, v in (
        (-3.85, 0.0), (-2.85, 0.88), (2.85, 0.88), (3.85, 0.0), (2.85, -0.88), (-2.85, -0.88)
    )]
    assign(prism_y("led_%d" % i, led_pts, YL + 0.66, 0.30, chamfer=0.10, seg=1), M_5_GREEN)

# Speaker grilles: 5 diagonal rows ([2, 4, 4, 4, 2] = 16 capsule slots per side) angled at +-42 deg
# punched directly into the coplanar ear facets (no fake rectangular pad!).
def _rot2d(pts, deg, cx, cz):
    ca, sa = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [(cx + x * ca - z * sa, cz + x * sa + z * ca) for x, z in pts]

cap_base = stadium_pts_2d(1.90, 0.86, seg_half=5)
GRILLE_ROWS = (
    (-2, (-0.5, 0.5)),
    (-1, (-1.5, -0.5, 0.5, 1.5)),
    (0, (-1.5, -0.5, 0.5, 1.5)),
    (1, (-1.5, -0.5, 0.5, 1.5)),
    (2, (-0.5, 0.5)),
)
for side_idx, sx in enumerate((-1, 1)):
    gx, gz = sx * 16.5, 26.2
    slot_deg = sx * 42.0          # +42 deg on right (+X), -42 deg on left (-X), parallel to upper X-arms
    # Row step perpendicular-diagonal so rows stack neatly within the ear shield
    ca, sa = math.cos(math.radians(slot_deg)), math.sin(math.radians(slot_deg))
    bm_cut = bmesh.new()
    bm_hole = bmesh.new()
    for r_idx, u_list in GRILLE_ROWS:
        for u_step in u_list:
            du = u_step * 2.28
            dv = r_idx * 1.62
            hx = gx + du * ca - dv * sa
            hz = gz + du * sa + dv * ca
            y_surf = Y0 - (3.15 - 0.0531915 * (abs(hx) - 11.8))
            pts = _rot2d(cap_base, slot_deg, hx, hz)
            # Cutter prism into body
            f_c = bm_cut.faces.new([bm_cut.verts.new(v3(px, y_surf + 0.65, pz)) for px, pz in pts])
            bm_cut.normal_update()
            if f_c.normal.y > 0:
                f_c.normal_flip()
            ext = bmesh.ops.extrude_face_region(bm_cut, geom=[f_c])
            for v in [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]:
                v.co.y -= 1.60 * MM
            # Dark acoustic mesh backing plate at bottom of each capsule
            f_h = bm_hole.faces.new([bm_hole.verts.new(v3(px, y_surf + 0.58, pz)) for px, pz in pts])
            bm_hole.normal_update()
            if f_h.normal.y > 0:
                f_h.normal_flip()
            ext_h = bmesh.ops.extrude_face_region(bm_hole, geom=[f_h])
            for v in [g for g in ext_h["geom"] if isinstance(g, bmesh.types.BMVert)]:
                v.co.y += 0.12 * MM
    cutter_obj = finish(bm_cut, "grille_cutter_%d" % side_idx)
    boolean(body, cutter_obj, op="DIFFERENCE")
    assign(finish(bm_hole, "grille_holes_%d" % side_idx), M_HOLE)


# ------------------------------------------------------------------------------------------------
# 3. Octagonal Soft-Touch Event Button Pad, 4 Raised Tactile Corner Bars, & Gloss-Black Recessed Delta
# ------------------------------------------------------------------------------------------------
bx, bz = BTN


def octagon_pts(hwid, top, bot, ch):
    return [
        (-hwid + ch, top), (hwid - ch, top), (hwid, top - ch), (hwid, bot + ch),
        (hwid - ch, bot), (-hwid + ch, bot), (-hwid, bot + ch), (-hwid, top - ch),
    ]


# Dark moat liner at base of the body's octagonal moat
moat_liner_pts = rounded_poly([(-9.2, 5.2), (9.2, 5.2), (17.5, -3.1), (17.5, -20.0), (8.6, -29.8),
                               (-8.6, -29.8), (-17.5, -20.0), (-17.5, -3.1)], 1.2, 3)
assign(prism_y("btn_moat_liner", moat_liner_pts, Y0 - 0.42, 0.08), M_HOLE)

# Concave dished octagonal button pad with flat outer locator rim
PAD_FRONT = Y0 - 2.38             # rim height (h = 2.38 mm)
DISH = 1.32                       # smooth central dish depth (mm)
R_DISH_START = 12.8               # inner edge of the flat octagonal rim where concave dish begins


def dish_depth(px_, pz_):
    r_ = math.hypot(px_ - bx, pz_ - bz)
    if r_ >= R_DISH_START:
        return 0.0
    t = 1.0 - (r_ / R_DISH_START) ** 2
    return DISH * (t ** 1.35)


def build_dish_pad(name, outline_pts, y_back, y_front, chamfer=0.65):
    bm = bmesh.new()
    n = len(outline_pts)
    span = max(math.hypot(x - bx, z - bz) for x, z in outline_pts)
    prof = [(1.0, y_back), (1.0, y_front + chamfer)]
    prof += [
        (1.0 - (chamfer / span) * (1.0 - math.cos(math.pi / 2.0 * k / 3.0)),
         y_front + chamfer * (1.0 - math.sin(math.pi / 2.0 * k / 3.0)))
        for k in range(1, 4)
    ]
    s0 = prof[-1][0]
    rings = [[bm.verts.new(v3(bx + (x - bx) * s, yy, bz + (z - bz) * s)) for x, z in outline_pts] for s, yy in prof]
    for k in range(1, 20):
        s = s0 * (1.0 - k / 20.0)
        ring = []
        for x, z in outline_pts:
            px_, pz_ = bx + (x - bx) * s, bz + (z - bz) * s
            ring.append(bm.verts.new(v3(px_, y_front + dish_depth(px_, pz_), pz_)))
        rings.append(ring)
    centre = bm.verts.new(v3(bx, y_front + DISH, bz))
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([r0[i], r0[j], r1[j], r1[i]])
    for i in range(n):
        bm.faces.new([rings[-1][i], rings[-1][(i + 1) % n], centre])
    bm.faces.new(list(reversed(rings[0])))
    return finish(bm, name)


pad_outline = rounded_poly(octagon_pts(16.4, 4.4, -27.2, 8.0), 1.8, 4)
pad = assign(build_dish_pad("btn_pad", pad_outline, Y0 - 0.44, PAD_FRONT), M_5_PAD)

# 4 slim RAISED tactile stadium corner ribs along the 4 diagonal chamfers (ab5_bottom_regions.jpg top!)
rib_2d = stadium_pts_2d(4.6, 0.72, seg_half=6)
for rib_i, (sx, sz) in enumerate(((-1, 1), (1, 1), (-1, -1), (1, -1))):
    rcx, rcz = bx + sx * 11.2, bz + sz * 10.6
    # Chamfer tangent runs at +-45 deg: top-right (+1,+1) slopes -45 deg; top-left (-1,+1) slopes +45 deg
    rib_deg = -45.0 * sx * sz
    rpts = _rot2d(rib_2d, rib_deg, rcx, rcz)
    y_rib_base = PAD_FRONT + dish_depth(rcx, rcz) + 0.12
    assign(prism_y("btn_corner_rib_%d" % rib_i, rpts, y_rib_base, 0.34, chamfer=0.14, seg=2), M_5_PAD)

# Flush/slightly-recessed solid gloss-black 3-blade Axon Delta centered at (0, -13.2), R = 8.0 mm
# (Matches zone_mid.jpg: apex at Z = -5.2, base at Z = -17.2 spanning X in [-6.9, +6.9])
DELTA_CX, DELTA_CZ, DELTA_R = 0.0, -13.2, 8.0
for b_idx, poly in enumerate(delta_polys(DELTA_R, DELTA_CX, DELTA_CZ)):
    # Carve crisp recessed pocket into btn_pad following dish curvature, then seat solid gloss-black blade
    bm_dcut = bmesh.new()
    f_dc = bm_dcut.faces.new([bm_dcut.verts.new(v3(px, PAD_FRONT + dish_depth(px, pz) + 0.22, pz)) for px, pz in poly])
    bm_dcut.normal_update()
    if f_dc.normal.y > 0:
        f_dc.normal_flip()
    ext_dc = bmesh.ops.extrude_face_region(bm_dcut, geom=[f_dc])
    for v in [g for g in ext_dc["geom"] if isinstance(g, bmesh.types.BMVert)]:
        v.co.y -= 1.8 * MM
    boolean(pad, finish(bm_dcut, "delta_cut_%d" % b_idx), op="DIFFERENCE")

    # Curved gloss-black blade conforming to the concave dish (recessed 0.14 mm below pad dish surface)
    bm_bl = bmesh.new()
    front_vs = [bm_bl.verts.new(v3(px, PAD_FRONT + dish_depth(px, pz) + 0.14, pz)) for px, pz in poly]
    back_vs = [bm_bl.verts.new(v3(px, PAD_FRONT + dish_depth(px, pz) + 0.30, pz)) for px, pz in poly]
    bm_bl.faces.new(front_vs)
    bm_bl.faces.new(list(reversed(back_vs)))
    nb = len(poly)
    for k in range(nb):
        kn = (k + 1) % nb
        bm_bl.faces.new([back_vs[k], back_vs[kn], front_vs[kn], front_vs[k]])
    bm_bl.normal_update()
    if b_idx == 0:
        bmesh.ops.recalc_face_normals(bm_bl, faces=bm_bl.faces[:])
    assign(finish(bm_bl, "delta_blade_%d" % b_idx), M_GLOSS)


# ------------------------------------------------------------------------------------------------
# 4. Six Torx Screws, Three Front Mic Pinholes, & AXON Wordmark
# ------------------------------------------------------------------------------------------------
# Carve U-shaped outer rim notches for the recessed middle side screws (screw_2, 3 at Z = -1.0)
for sx in (-1, 1):
    notch_pts = [(sx * (26.6 + x), -1.0 + z) for x, z in stadium_pts_2d(9.6, 5.4, seg_half=8)]
    cut(["body"], lambda: prism_y("mid_screw_notch", notch_pts, Y0 - 0.90, 3.0))

SCREW_POS = (
    (-26.5, 38.8), (26.5, 38.8),
    (-26.6, -1.0), (26.6, -1.0),
    (-26.4, -40.2), (26.4, -40.2),
)
for i, (sx_pos, sz_pos) in enumerate(SCREW_POS):
    hit_loc, _ = surface_at(sx_pos, sz_pos)
    screw("screw_%d" % i, sx_pos, sz_pos, hit_loc.y / MM + 0.42, r_bore=1.90, r_head=1.42, targets=("body",))

# Upper-right brow mic pinhole (zone_top.jpg: (+13.8, +43.6)) + symmetric mid-rail pinholes ((+-22.7, +4.4))
for m_idx, (mx, mz, mr) in enumerate(((13.8, 43.6, 0.52), (-22.7, 4.4, 0.46), (22.7, 4.4, 0.46))):
    loc, nor = surface_at(mx, mz)
    # Recessed bore in body + dark backing disc
    bore = disc("mic_cut_%d" % m_idx, mr, 0.0, 0.0, 0.55, -0.60, seg=20)
    bore.location = loc
    bore.rotation_euler = facing(nor).to_euler()
    boolean(body, bore, op="DIFFERENCE")
    hole = assign(disc("mic_%d" % m_idx, mr * 0.98, 0.0, 0.0, 0.55, 0.35, seg=20), M_HOLE)
    hole.location = loc
    hole.rotation_euler = facing(nor).to_euler()

# Crisp white AXON wordmark centered inside recessed pocket (2) at (0.0, -37.2)
front_text("axon_txt", "AXON", 0.0, -37.2, 11.2, M_TEXT, font=r"C:\Windows\Fonts\GOTHIC.TTF",
           extrude=0.08, lift=0.02, space=1.06)


# ------------------------------------------------------------------------------------------------
# 5. Sides (ab5_r.png Left Buttons + Lanyard Notch; ab5_l.png Right Port Seam + 45-deg Slash Grip),
#    Top Display/LED, Bottom USB-C + Pogo Contacts, & Rear RapidLock Mount
# ------------------------------------------------------------------------------------------------
# Right side (+X, ab5_l.png): upper flush port/SIM door seam + lower recessed 45-deg diagonal rib grip panel
boolean(body, box("r_port_seam_cut", 0.8, 12.0, 18.0, (hw - 0.1, -1.0, 24.5), bevel=0.3, seg=1))
assign(box("r_port_door", 0.6, 11.4, 17.4, (hw - 0.15, -1.0, 24.5), bevel=0.3, seg=2), M_5_BODY)

boolean(body, box("grip_cut", 2.2, 16.4, 48.0, (hw + 0.4, 0.2, -11.5), bevel=0.5, seg=2))
assign(box("grip_floor", 0.35, 16.0, 47.6, (hw - 0.55, 0.2, -11.5)), M_RUBBER)
# 26 parallel 45-degree diagonal tactile grip ribs matching ab5_l.png right flank
bm_grip = bmesh.new()
y_g0, y_g1 = -7.2, 7.6
z_g0, z_g1 = -34.5, 11.5
for k in range(-18, 22):
    # Line z - y = c_k clipped to [y_g0, y_g1] x [z_g0, z_g1]
    ck = k * 1.95 - 10.0
    ya = max(y_g0, z_g0 - ck)
    yb = min(y_g1, z_g1 - ck)
    if yb - ya < 2.2:
        continue
    za, zb = ya + ck, yb + ck
    hw_r = 0.38
    pts_yz = [(ya - hw_r, za + hw_r), (yb - hw_r, zb + hw_r), (yb + hw_r, zb - hw_r), (ya + hw_r, za - hw_r)]
    v_base = [bm_grip.verts.new(v3(hw - 0.50, yy, zz)) for yy, zz in pts_yz]
    v_top = [bm_grip.verts.new(v3(hw - 0.05, yy * 0.99 + 0.01 * ((ya + yb) / 2), zz)) for yy, zz in pts_yz]
    bm_grip.faces.new(list(reversed(v_base)))
    bm_grip.faces.new(v_top)
    for j in range(4):
        jn = (j + 1) % 4
        bm_grip.faces.new([v_base[j], v_base[jn], v_top[jn], v_top[j]])
assign(finish(bm_grip, "grip_ribs"), M_RUBBER)

# Left side (-X, ab5_r.png & ab5_ofcr_2.png):
# 1) Upper programmable button + tactile pill bar (Z = +31.5)
# 2) Deep beveled holster/lanyard retention notch (Z = +23.5)
# 3) Middle button with dual horizontal tactile ribs (Z = +9.5)
# 4) Lower rocker/power pad with 3 ribs + triangle mark (Z = -21.0)
boolean(body, box("l_notch_cut", 3.6, 15.0, 4.4, (-hw - 0.2, -2.5, 23.5), bevel=0.8, seg=2))

for b_i, (zc, zl) in enumerate(((31.5, 9.6), (9.5, 11.2), (-21.0, 20.0))):
    boolean(body, box("l_btn_well_%d" % b_i, 1.8, 12.2, zl + 1.2, (-hw + 0.1, -1.2, zc), bevel=0.6, seg=2))
    assign(box("l_btn_seam_%d" % b_i, 0.5, 11.8, zl + 0.8, (-hw + 0.55, -1.2, zc), bevel=0.3, seg=1), M_HOLE)
    assign(box("l_btn_%d" % b_i, 1.7, 11.0, zl, (-hw - 0.10, -1.2, zc), bevel=0.75, seg=3), M_RUBBER)

# Tactile marks on left buttons matching ab5_r.png!
assign(box("l_mark_top", 0.65, 5.4, 1.4, (-hw - 1.05, -1.2, 31.5), bevel=0.30, seg=2), M_RUBBER)
for r_k, dz in enumerate((-1.5, 1.5)):
    assign(box("l_mark_mid_%d" % r_k, 0.65, 5.6, 1.25, (-hw - 1.05, -1.2, 9.5 + dz), bevel=0.28, seg=2), M_RUBBER)
for r_k, dz in enumerate((5.5, 2.5, -0.5)):
    assign(box("l_mark_low_%d" % r_k, 0.55, 5.6, 1.15, (-hw - 1.00, -1.2, -21.0 + dz), bevel=0.24, seg=2), M_RUBBER)
assign(
    prism_x("l_mark_tri", [(-1.2 - 1.7, -26.5), (-1.2 + 1.7, -26.5), (-1.2, -29.2)], -hw - 0.90, -0.45,
            chamfer=0.10, seg=1),
    M_RUBBER,
)

# Top (+Z): flush-recessed status OLED display window + operation LED (does not protrude above Z_TOP + 0.25!)
boolean(body, box("top_disp_cut", 22.4, 9.6, 1.4, (0.0, -1.8, hh + 0.1), bevel=0.5, seg=2))
assign(box("top_display_bezel", 21.8, 9.0, 0.8, (0.0, -1.8, hh - 0.20), bevel=0.4, seg=2), M_RUBBER)
assign(box("top_display", 17.8, 5.8, 0.4, (0.0, -1.8, hh + 0.06), bevel=0.2, seg=2), M_GLASS)
assign(cyl_z("top_led", 1.05, -14.2, -2.2, hh - 0.5, hh + 0.15, seg=20, chamfer=0.20), M_5_GREEN)

# Bottom (-Z): recessed waterproof USB-C socket + 2 pogo dock contacts
usbc = [(x, -1.2 + y) for x, y in stadium_pts_2d(9.0, 3.2, seg_half=8)]
cut(["body"], lambda: prism_z("usbc_cut", usbc, -hh + 2.5, -4.0))
assign(prism_z("usbc_shell", [(x, -1.2 + y) for x, y in stadium_pts_2d(8.6, 2.8, seg_half=8)], -hh + 2.4, -2.2), M_BEZEL)
assign(box("usbc_tongue", 6.4, 0.7, 1.5, (0.0, -1.2, -hh + 1.2), bevel=0.15, seg=1), M_SCREW)
for i, px_pogo in enumerate((-13.5, 13.5)):
    cut(["body"], lambda: cyl_z("pogo_cut", 1.55, px_pogo, -1.2, -hh + 0.9, -hh - 1.0, seg=24))
    assign(cyl_z("pogo_%d" % i, 1.30, px_pogo, -1.2, -hh + 0.85, -hh + 0.08, seg=24, chamfer=0.18), M_SCREW)

# Back (+Y): RapidLock quarter-turn mount receiver, alignment magnets, & regulatory label plate
assign(annulus("rapidlock_rim", 0.0, 4.0, 10.6, 12.6, YB + 0.75, YB - 0.30, seg=72, chamfer_front=0.25), M_MOUNT)
assign(disc("rapidlock_well", 10.65, 0.0, 4.0, YB - 0.30, YB + 0.25, seg=64), M_HOLE)
assign(disc("rapidlock_boss", 4.5, 0.0, 4.0, YB - 0.30, YB + 1.15, seg=36, chamfer=0.28, cseg=2), M_MOUNT)
for i, ang_deg in enumerate((0, 180)):
    assign(box("rapidlock_lug_%d" % i, 3.0, 1.0, 2.0, (7.6 * math.cos(math.radians(ang_deg)), YB + 0.82, 4.0),
               bevel=0.28, seg=1), M_MOUNT)
for i, mz_mag in enumerate((31.0, -24.0)):
    assign(disc("magnet_%d" % i, 5.4, 0.0, mz_mag, YB - 0.30, YB + 0.14, seg=40, chamfer=0.12, cseg=2), M_MAGNET)
assign(box("label", 30.0, 0.34, 10.0, (0.0, YB + 0.02, -38.5), bevel=0.55, seg=2), M_LABEL)
for i, (txt_s, tz, sz_mm) in enumerate((("AXON BODY 5", -36.8, 1.8), ("AXON ENTERPRISE, INC.", -40.0, 1.0))):
    tx = make_text_mesh("label_txt_%d" % i, txt_s, sz_mm, 0.05, space=1.04, res_u=2)
    tx.rotation_euler = (math.radians(90), 0, math.radians(180))
    tx.location = v3(0.0, YB + 0.23, tz)
    assign(tx, M_5_BODY)

# Keep razor-sharp stealth facets with crisp 6-degree split normals (zero boolean bevel pinching!)
bm_clean = bmesh.new()
bm_clean.from_mesh(body.data)
bmesh.ops.remove_doubles(bm_clean, verts=bm_clean.verts[:], dist=0.0005 * MM)
bm_clean.to_mesh(body.data)
bm_clean.free()

meshes = smooth_all(flat=[body], angle=30, flat_angle=6)
print("zbc_bodycam_5: %d parts" % len(meshes))
