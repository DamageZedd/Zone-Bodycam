"""Zone Bodycam - builds the Axon Body 3 (AX1023, 2020) item model in Blender.

Run inside Blender with __file__ set (export_variant.py does this):
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
Creates the scene "zbc_bodycam_3", every part its own single-material object, ready for export_variant.py.

Reference: official Axon Body 3 User Manual orthographic front/top/bottom drawings (13.89 px/mm) and
Axon product studio renders (3/4 front-right glamor and 3/4 front-left p01_03). 66.0 x 93.2 x 28.0 mm.
Look: stealth dark charcoal octagonal chassis with coarse pebble-stippled front armor wings sloping
flush into a smooth satin-matte center strip + circular Event boss (zero step), recessed middle-screw
pockets, contoured circular lens scoop with matte-black stepped barrel & AR glass, 7-slot speaker
grille, satin-black Event collar, fine micro-knurled dish with 3 slim ruby-red Triad LED arcs,
matte center disc with gloss-black Axon delta, AXON wordmark + bevelled bottom mic, left-side 4-pad
control strip (Vol+ triangle, proud 3-bar Select, Vol- triangle, diamond-knurled Program pad),
right-side dual recessed micro-knurled grip panels split by a horizontal belt bridge, top Op LED slot
+ monochrome LCD + Power button, bottom USB-C + dual concentric mic ports, and rear RapidLock.
Units are metres in Blender, millimetres below. Front faces -Y, Z is up, X is right as seen from front.
"""
import math
import os
import bpy
import bmesh
from mathutils import Vector, Matrix

SCENE = "zbc_bodycam_3"
COMMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "axon_common.py")
exec(compile(open(COMMON, encoding="utf-8").read(), COMMON, "exec"), globals())
setup_scene()
std_materials()

# ---- body (mm)
W, D = 66.0, 28.0
hw = W / 2.0
Z_TOP, Z_BOT = 46.6, -46.6
TOP_CUT = (20.3, 40.7)            # top corner cuts: (+-20.3, Z_TOP) -> (+-hw, 40.7)
BOT_CUT = (20.3, -40.9)
CORNER_R = 2.6
FRONT_R = 1.6
BACK_BEVEL = 2.6
Y0 = -D / 2.0                     # front reference plane (-14.0 mm)
YB = D / 2.0                      # rear wall (+14.0 mm)
H_PLAT = 1.65                     # height of smooth center strip + Event boss forward of Y0
YP = Y0 - H_PLAT                  # -15.65 mm

LENS = (0.0, 31.2)
GRILLE = (17.6, 30.7)
BTN = (0.0, -9.4)
BOSS_R = 24.9                     # round boss around the Event button
PANEL_X = 14.3                    # half-width of the smooth center strip
PANEL_Z = (42.3, -43.0)

# ------------------------------------------------------------------------------------------------
# AB3-specific photometric materials (zbc_3_* -> isolated item_zbc_bodycam_3_*.dds)
# ------------------------------------------------------------------------------------------------


def make_stipple_body_mat(name):
    """Coarse tactical pebble-grain polycarbonate (bakes 1024x1024 UV texture + crisp Cycles bump)."""
    m = own_material(name, (0.010, 0.010, 0.012), 0.65, spec=0.45)
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = next(n for n in N if n.type == "BSDF_PRINCIPLED")

    tc = N.new("ShaderNodeTexCoord")
    tc.label = "stipple_coords"
    sc_mm = N.new("ShaderNodeVectorMath")
    sc_mm.operation = "SCALE"
    sc_mm.inputs["Scale"].default_value = 1000.0  # metres -> mm
    L.new(tc.outputs["Object"], sc_mm.inputs[0])

    vor = N.new("ShaderNodeTexVoronoi")
    vor.feature = "F1"
    vor.inputs["Scale"].default_value = 2.05       # ~0.49 mm coarse tactical pebbles
    vor.inputs["Randomness"].default_value = 0.88
    L.new(sc_mm.outputs[0], vor.inputs["Vector"])

    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 3.8
    nz.inputs["Detail"].default_value = 4.0
    nz.inputs["Roughness"].default_value = 0.68
    L.new(sc_mm.outputs[0], nz.inputs["Vector"])

    # Combine Voronoi pebble peaks (1 - Distance) with micro-noise for authentic molded pebble grain
    inv_d = N.new("ShaderNodeMath")
    inv_d.operation = "SUBTRACT"
    inv_d.inputs[0].default_value = 1.0
    L.new(vor.outputs["Distance"], inv_d.inputs[1])

    clamp_d = N.new("ShaderNodeMath")
    clamp_d.operation = "POWER"
    clamp_d.inputs[1].default_value = 1.35
    L.new(inv_d.outputs[0], clamp_d.inputs[0])

    mix_h = N.new("ShaderNodeMath")
    mix_h.operation = "MULTIPLY_ADD"
    mix_h.inputs[1].default_value = 0.72
    L.new(clamp_d.outputs[0], mix_h.inputs[0])

    nz_scaled = N.new("ShaderNodeMath")
    nz_scaled.operation = "MULTIPLY"
    nz_scaled.inputs[1].default_value = 0.28
    L.new(nz.outputs["Fac"], nz_scaled.inputs[0])
    L.new(nz_scaled.outputs[0], mix_h.inputs[2])

    col_mix = N.new("ShaderNodeMix")
    col_mix.data_type = "RGBA"
    col_mix.inputs["A"].default_value = (0.006, 0.006, 0.007, 1.0)
    col_mix.inputs["B"].default_value = (0.013, 0.014, 0.016, 1.0)
    L.new(mix_h.outputs[0], col_mix.inputs["Factor"])
    L.new(col_mix.outputs["Result"], bsdf.inputs["Base Color"])

    bp = N.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.75
    bp.inputs["Distance"].default_value = 0.00032
    L.new(mix_h.outputs[0], bp.inputs["Height"])
    L.new(bp.outputs[0], bsdf.inputs["Normal"])
    return m


M_3_BODY = make_stipple_body_mat("zbc_3_body")
M_3_FACE = own_material("zbc_3_face", (0.011, 0.011, 0.013), 0.44, spec=0.48)
surface_noise(M_3_FACE, scale=14000, strength=0.04)

M_3_RUBBER = own_material("zbc_3_rubber", (0.009, 0.009, 0.011), 0.72, spec=0.38)
M_3_GRIP = own_material("zbc_3_grip", (0.008, 0.008, 0.010), 0.75, spec=0.40)
M_3_BEZEL = own_material("zbc_3_bezel", (0.007, 0.007, 0.009), 0.52, metal=0.0, spec=0.45)
M_3_COLLAR = own_material("zbc_3_collar", (0.009, 0.009, 0.011), 0.34, spec=0.52)
M_3_DISC = own_material("zbc_3_disc", (0.010, 0.011, 0.012), 0.52, spec=0.45)
M_3_LOGO = own_material("zbc_3_logo", (0.003, 0.003, 0.004), 0.20, spec=0.70)

M_3_BUTTON = own_material("zbc_3_button", (0.010, 0.010, 0.012), 0.64)
knurl(M_3_BUTTON, BTN[0], BTN[1], 13.1, 19.4, 0.70,
      (0.008, 0.008, 0.010), (0.013, 0.014, 0.016), (0.002, 0.002, 0.003))

M_3_GLASS = own_material("zbc_3_glass", (0.001, 0.004, 0.006), 0.02, spec=1.0)
_g_bsdf = M_3_GLASS.node_tree.nodes["Principled BSDF"]
if "Coat Weight" in _g_bsdf.inputs:
    _g_bsdf.inputs["Coat Weight"].default_value = 0.90
    _g_bsdf.inputs["Coat Roughness"].default_value = 0.03
if "Specular Tint" in _g_bsdf.inputs:
    _g_bsdf.inputs["Specular Tint"].default_value = (0.45, 0.95, 0.85, 1.0)

M_3_RED = own_material("zbc_3_red", (0.95, 0.006, 0.003), 0.22, emission=(1.1, 0.015, 0.005))
M_3_RED.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.4
M_3_LCD = own_material("zbc_3_lcd", (0.005, 0.007, 0.006), 0.06, spec=1.0)
M_3_LCD_SEG = own_material("zbc_3_lcd_seg", (0.012, 0.016, 0.013), 0.14, spec=0.75)
M_3_YELLOW = own_material("zbc_3_yellow", (0.950, 0.630, 0.005), 0.38, spec=0.55)
M_LED = shared_material("zbc_led", (0.35, 0.03, 0.03), 0.20)

# ------------------------------------------------------------------------------------------------
# 2D Contour Geometry Helpers for Continuous Height-Field Shell & Smooth Panel
# ------------------------------------------------------------------------------------------------


def ray_poly_r(poly, theta):
    """Distance from origin (0, 0) along direction (cos(theta), sin(theta)) to a closed 2D star-shaped polygon."""
    dx, dz = math.cos(theta), math.sin(theta)
    best = 1e9
    n = len(poly)
    for i in range(n):
        x0, z0 = poly[i]
        x1, z1 = poly[(i + 1) % n]
        sx, sz = x1 - x0, z1 - z0
        denom = dx * sz - dz * sx
        if abs(denom) < 1e-12:
            continue
        t = (x0 * sz - z0 * sx) / denom
        u = (x0 * dz - z0 * dx) / denom
        if t > 1e-9 and -1e-6 <= u <= 1.0 + 1e-6:
            if t < best:
                best = t
    return best


def inset_convex_2d(pts, t):
    """Inset a convex 2D polygon by scalar t (mm)."""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    sgn = 1.0 if area > 0 else -1.0
    lines = []
    for i in range(n):
        x0, z0 = pts[i]
        x1, z1 = pts[(i + 1) % n]
        dx, dz = x1 - x0, z1 - z0
        ln = math.hypot(dx, dz)
        nx, nz = -dz / ln * sgn, dx / ln * sgn
        lines.append((x0 + nx * t, z0 + nz * t, dx, dz))
    out = []
    for i in range(n):
        x0, z0, dx0, dz0 = lines[i - 1]
        x1, z1, dx1, dz1 = lines[i]
        den = dx0 * dz1 - dz0 * dx1
        if abs(den) < 1e-12:
            out.append((x1, z1))
        else:
            u = ((x1 - x0) * dz1 - (z1 - z0) * dx1) / den
            out.append((x0 + u * dx0, z0 + u * dz0))
    return out


def build_panel_2d_outline():
    """Smooth center strip [-PANEL_X, +PANEL_X] x [PANEL_Z[1], PANEL_Z[0]] unioned with Event boss circle."""
    bx, bz = BTN
    # Exact circle-line intersections at |x| = PANEL_X
    dz_int = math.sqrt(BOSS_R ** 2 - PANEL_X ** 2)  # ~20.38 mm
    z_top_int = bz + dz_int                         # ~+10.98 mm
    z_bot_int = bz - dz_int                         # ~-29.78 mm

    # Build right side (+X) from top-center clockwise to bottom-center, then mirror to -X
    pts_r = []
    # Top edge -> top-right rounded corner
    pts_r.append((0.0, PANEL_Z[0]))
    pts_r.append((PANEL_X - 3.2, PANEL_Z[0]))
    for k in range(1, 9):
        a = math.radians(90.0 - 90.0 * k / 8.0)
        pts_r.append((PANEL_X - 3.2 + 3.2 * math.cos(a), PANEL_Z[0] - 3.2 + 3.2 * math.sin(a)))
    # Straight right edge down to smooth tangent fillet above Event boss
    fillet_dz = 3.2
    pts_r.append((PANEL_X, z_top_int + fillet_dz))
    # Smooth quadratic Bezier from (PANEL_X, z_top_int + 3.2) onto circle at a_start
    a_top_int = math.degrees(math.atan2(z_top_int - bz, PANEL_X))  # ~+54.9 deg
    a_start = a_top_int - 7.5
    p_circ_start = (bx + BOSS_R * math.cos(math.radians(a_start)), bz + BOSS_R * math.sin(math.radians(a_start)))
    for p in bezier((PANEL_X, z_top_int + fillet_dz), (PANEL_X, z_top_int + 0.3), p_circ_start, n=8)[1:]:
        pts_r.append(p)
    # Circular arc on right side down to lower fillet
    a_bot_int = math.degrees(math.atan2(z_bot_int - bz, PANEL_X))  # ~-54.9 deg
    a_end = a_bot_int + 7.5
    n_arc = 40
    for k in range(1, n_arc):
        a = math.radians(a_start + (a_end - a_start) * k / n_arc)
        pts_r.append((bx + BOSS_R * math.cos(a), bz + BOSS_R * math.sin(a)))
    p_circ_end = (bx + BOSS_R * math.cos(math.radians(a_end)), bz + BOSS_R * math.sin(math.radians(a_end)))
    for p in bezier(p_circ_end, (PANEL_X, z_bot_int - 0.3), (PANEL_X, z_bot_int - fillet_dz), n=8):
        pts_r.append(p)
    # Bottom-right rounded corner -> bottom-center
    pts_r.append((PANEL_X, PANEL_Z[1] + 3.2))
    for k in range(1, 9):
        a = math.radians(0.0 - 90.0 * k / 8.0)
        pts_r.append((PANEL_X - 3.2 + 3.2 * math.cos(a), PANEL_Z[1] + 3.2 + 3.2 * math.sin(a)))
    pts_r.append((0.0, PANEL_Z[1]))

    # Mirror left side (-X) bottom-to-top
    pts_l = [(-x, z) for x, z in reversed(pts_r[1:-1])]
    raw = pts_r + pts_l
    out = []
    for p in raw:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-4:
            out.append(p)
    if len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) <= 1e-4:
        out.pop()
    return out


def x_pinch_at(z):
    """Outer X boundary of the raised stippled wing in the middle pinched zone (mm)."""
    az = abs(z)
    if az <= 24.5:
        return 26.2
    if az <= 34.5:
        t = (az - 24.5) / 10.0
        return 26.2 + t * (30.8 - 26.2)
    return 99.0


# ------------------------------------------------------------------------------------------------
# 1. Continuous Piecewise Height-Field Shell (body = stippled armor, panel = smooth center strip)
# ------------------------------------------------------------------------------------------------
outline = [
    (-TOP_CUT[0], Z_TOP), (TOP_CUT[0], Z_TOP), (hw, TOP_CUT[1]), (hw, BOT_CUT[1]),
    (BOT_CUT[0], Z_BOT), (-BOT_CUT[0], Z_BOT), (-hw, BOT_CUT[1]), (-hw, TOP_CUT[1]),
]
outline_oct = rounded_poly(outline, CORNER_R, seg=8)
outline_chamfer = rounded_poly(inset_convex_2d(outline, FRONT_R), max(0.4, CORNER_R - FRONT_R), seg=8)
outline_back = rounded_poly(inset_convex_2d(outline, BACK_BEVEL), max(0.4, CORNER_R - BACK_BEVEL), seg=8)
panel_poly = build_panel_2d_outline()

# Build ray angles covering all vertices of panel_poly, outline_chamfer, and uniform polar grid
angles_set = [2.0 * math.pi * i / 280.0 for i in range(280)]
for poly in (panel_poly, outline_chamfer, outline_oct):
    for px, pz in poly:
        angles_set.append(math.atan2(pz, px) % (2.0 * math.pi))
# Add exact pinch Z angles (|z| = 24.5, 34.5 on left and right)
for zx in ((26.2, 24.5), (-26.2, 24.5), (26.2, -24.5), (-26.2, -24.5),
           (30.8, 34.5), (-30.8, 34.5), (30.8, -34.5), (-30.8, -34.5)):
    angles_set.append(math.atan2(zx[1], zx[0]) % (2.0 * math.pi))
# Add diagonal brow/chin corner angles (+-20.3, Z_TOP/Z_BOT)
for cx, cz in ((-TOP_CUT[0], Z_TOP), (TOP_CUT[0], Z_TOP), (BOT_CUT[0], Z_BOT), (-BOT_CUT[0], Z_BOT)):
    angles_set.append(math.atan2(cz, cx) % (2.0 * math.pi))

angles_set.sort()
angles = []
for a in angles_set:
    if not angles or abs(a - angles[-1]) > 0.0025:
        angles.append(a)
if abs(angles[-1] - angles[0] - 2.0 * math.pi) < 0.0025:
    angles.pop()


def classify_and_eval(theta):
    """Return continuous radial rings (r, y) from inner panel seam out to rear bevel along ray theta."""
    c, s = math.cos(theta), math.sin(theta)
    rp = ray_poly_r(panel_poly, theta)
    rc = ray_poly_r(outline_chamfer, theta)
    ro = ray_poly_r(outline_oct, theta)
    rb = ray_poly_r(outline_back, theta)

    xc, zc = rc * c, rc * s
    ax, az = abs(xc), abs(zc)

    # Continuous outer chamfer height: 0.62 on flanks (|z| < 40.7), tapering to 0 on top/bot flats
    t_edge = max(0.0, min(1.0, (ax - 17.5) / (30.8 - 17.5)))
    t_z = 1.0 - max(0.0, min(1.0, (az - 40.5) / 4.5))
    h_ch = 0.62 * t_edge * t_z

    # Smooth pinch blending for the middle-screw pockets (only active where |z| < 34.5 and |x| > 24)
    if az < 34.5 and ax > 24.5:
        xp_edge = x_pinch_at(zc)
        rw = min(rc - 0.04, xp_edge / max(abs(c), 1e-6))
        rw = max(rp + 0.35, rw)
        rf = min(rc - 0.02, rw + 1.25 / max(abs(c), 0.35))
        rf = max(rw + 0.04, rf)
        t_fl = max(0.0, min(1.0, (az - 24.5) / 10.0))
        hw_ridge = 1.15 * (1.0 - t_fl) + h_ch * t_fl
        rmid = 0.5 * (rp + rw)
        hmid = 0.5 * (H_PLAT + hw_ridge)
        return {
            "rp": rp, "yp": Y0 - H_PLAT,
            "rmid": rmid, "ymid": Y0 - hmid,
            "rw": rw, "yw": Y0 - hw_ridge,
            "rf": rf, "yf": Y0,
            "rc": rc, "yc": Y0,
            "ro": ro, "yo": Y0 + FRONT_R,
            "rb": rb,
        }
    else:
        rmid = 0.5 * (rp + rc)
        hmid = 0.5 * (H_PLAT + h_ch)
        return {
            "rp": rp, "yp": Y0 - H_PLAT,
            "rmid": rmid, "ymid": Y0 - hmid,
            "rw": rc * 0.996, "yw": Y0 - h_ch,
            "rf": rc * 0.998, "yf": Y0 - h_ch,
            "rc": rc, "yc": Y0 - h_ch,
            "ro": ro, "yo": Y0 + FRONT_R * (1.0 - 0.25 * t_edge * t_z),
            "rb": rb,
        }


# Build watertight `body` mesh via exact radial rings (with 3 intermediate wing rings for smooth shading)
bm = bmesh.new()
n_ang = len(angles)
rings = [[] for _ in range(11)]  # 0:inner_recess, 1:panel_seam, 2..4:wing_q25/50/75, 5:wing_outer, 6:pocket_foot, 7:chamfer, 8:side_front, 9:side_back, 10:back_bevel

for a in angles:
    c, s = math.cos(a), math.sin(a)
    d = classify_and_eval(a)
    ri = max(2.0, d["rp"] - 0.6)
    r25 = 0.75 * d["rp"] + 0.25 * d["rw"]
    y25 = 0.75 * d["yp"] + 0.25 * d["yw"]
    r50 = 0.50 * d["rp"] + 0.50 * d["rw"]
    y50 = 0.50 * d["yp"] + 0.50 * d["yw"]
    r75 = 0.25 * d["rp"] + 0.75 * d["rw"]
    y75 = 0.25 * d["yp"] + 0.75 * d["yw"]
    coords = [
        (ri * c, Y0 + 0.5, ri * s),
        (d["rp"] * c, d["yp"], d["rp"] * s),
        (r25 * c, y25, r25 * s),
        (r50 * c, y50, r50 * s),
        (r75 * c, y75, r75 * s),
        (d["rw"] * c, d["yw"], d["rw"] * s),
        (d["rf"] * c, d["yf"], d["rf"] * s),
        (d["rc"] * c, d["yc"], d["rc"] * s),
        (d["ro"] * c, d["yo"], d["ro"] * s),
        (d["ro"] * c, YB - BACK_BEVEL, d["ro"] * s),
        (d["rb"] * c, YB, d["rb"] * s),
    ]
    for k, (vx, vy, vz) in enumerate(coords):
        rings[k].append(bm.verts.new(v3(vx, vy, vz)))

for k in range(len(rings) - 1):
    r0, r1 = rings[k], rings[k + 1]
    for i in range(n_ang):
        j = (i + 1) % n_ang
        bm.faces.new([r0[i], r1[i], r1[j], r0[j]])

# Cap inner front recess behind panel + flat rear wall
bm.faces.new(list(reversed(rings[0])))
bm.faces.new(rings[-1])

bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005 * MM)
# Triangulate front wing faces cleanly before boolean grille/screw cuts so no sliver creases occur
wing_faces = [f for f in bm.faces if f.normal.y < -0.15 and len(f.verts) >= 4]
bmesh.ops.triangulate(bm, faces=wing_faces)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
body = assign(finish(bm, "body"), M_3_BODY)

# ------------------------------------------------------------------------------------------------
# Smooth satin-matte center panel (`panel`) + contoured circular lens scoop
# ------------------------------------------------------------------------------------------------
panel = prism_y("panel", panel_poly, Y0 + 0.5, H_PLAT + 0.5, chamfer=0.07, seg=1)
assign(panel, M_3_FACE)

# Smooth concave lens scoop around LENS = (0, 31.2): r = 12.2 (flush at YP) -> r = 9.0 (recessed 0.95 mm)
lx, lz = LENS
bm_sc = bmesh.new()
scoop_prof = []
n_sc = 14
for i in range(n_sc + 1):
    t = i / n_sc
    rr = 12.2 - t * (12.2 - 8.7)
    # Cosine curve: zero slope at r=12.2 (flush tangent with panel!), smooth dish down to 0.95 mm deep
    dy = 0.95 * 0.5 * (1.0 - math.cos(math.pi * t))
    scoop_prof.append((rr, dy))
# Close top of cutter in front of YP so boolean DIFFERENCE carves a clean circular scoop
scoop_rings = []
for rr, dy in scoop_prof:
    ring = []
    for k in range(96):
        ang = 2.0 * math.pi * k / 96.0
        ring.append(bm_sc.verts.new(v3(lx + rr * math.cos(ang), YP + dy, lz + rr * math.sin(ang))))
    scoop_rings.append(ring)
# Outer cap back toward -Y (in front of panel)
cap_out = [bm_sc.verts.new(v3(lx + 12.2 * math.cos(2.0 * math.pi * k / 96.0), YP - 2.0, lz + 12.2 * math.sin(2.0 * math.pi * k / 96.0))) for k in range(96)]
cap_in = [bm_sc.verts.new(v3(lx + 8.7 * math.cos(2.0 * math.pi * k / 96.0), YP - 2.0, lz + 8.7 * math.sin(2.0 * math.pi * k / 96.0))) for k in range(96)]
for r_idx in range(len(scoop_rings) - 1):
    for k in range(96):
        nk = (k + 1) % 96
        bm_sc.faces.new([scoop_rings[r_idx][k], scoop_rings[r_idx + 1][k], scoop_rings[r_idx + 1][nk], scoop_rings[r_idx][nk]])
for k in range(96):
    nk = (k + 1) % 96
    bm_sc.faces.new([cap_out[k], scoop_rings[0][k], scoop_rings[0][nk], cap_out[nk]])
    bm_sc.faces.new([scoop_rings[-1][k], cap_in[k], cap_in[nk], scoop_rings[-1][nk]])
    bm_sc.faces.new([cap_in[k], cap_out[k], cap_out[nk], cap_in[nk]])
bmesh.ops.recalc_face_normals(bm_sc, faces=bm_sc.faces[:])
scoop_cutter = finish(bm_sc, "lens_scoop_cutter")
boolean(panel, scoop_cutter, op="DIFFERENCE")

# ------------------------------------------------------------------------------------------------
# Smooth satin-matte recessed middle-screw pockets (`pocket_l`, `pocket_r`) wrapping onto side walls
# ------------------------------------------------------------------------------------------------
for tag, sx in (("l", -1.0), ("r", 1.0)):
    # Build pocket inlay matching X_pinch + 1.25 -> hw chamfer -> side bridge wrap
    z_pts = [-34.0, -30.0, -24.5, -12.0, 0.0, 12.0, 24.5, 30.0, 34.0]
    poly_pk = []
    for z in z_pts:
        x_in = min(hw - FRONT_R - 0.1, x_pinch_at(z) + 1.15)
        poly_pk.append((sx * x_in, z))
    for z in reversed(z_pts):
        poly_pk.append((sx * (hw - FRONT_R + 0.02), z))
    if sx < 0:
        poly_pk.reverse()
    pk = prism_y("pocket_" + tag, poly_pk, Y0 + 0.25, 0.27, chamfer=0.05, seg=1)
    assign(pk, M_3_FACE)

# ------------------------------------------------------------------------------------------------
# Lens: recessed matte-black outer ring + deep stepped barrel + AR curved glass
# ------------------------------------------------------------------------------------------------
YPL = YP
cut(["panel", "body"], lambda: disc("lens_pocket_cut", 9.0, lx, lz, YPL + 2.6, YPL - 4.0, seg=120))
assign(annulus("lens_gap", lx, lz, 8.65, 9.0, YPL + 0.92, YPL + 1.4, seg=120), M_HOLE)
assign(lathe("lens_bezel", lx, lz, [
    (8.65, 0.98), (8.55, 0.78), (7.9, 0.80), (5.0, 1.05),
    (4.8, 1.25), (4.1, 1.45), (3.8, 1.75), (3.1, 2.08), (3.1, 2.50),
], YPL, seg=120), M_3_BEZEL)
assign(disc("lens_seat", 3.2, lx, lz, YPL + 2.55, YPL + 2.15, seg=96), M_HOLE)
assign(annulus("lens_aperture_ring", lx, lz, 1.4, 2.9, YPL + 1.75, YPL + 2.15, seg=72), M_3_BEZEL)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=36, v_segments=18, radius=3.55 * MM)
for v in bm.verts:
    v.co.y *= 0.72 / 3.55
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 1e-7], context="VERTS")
glass = assign(finish(bm, "lens_glass"), M_3_GLASS)
glass.location = v3(lx, YPL + 1.56, lz)

# ------------------------------------------------------------------------------------------------
# 7-Slot Speaker Grille (+17.6, +30.7): deeply cut into stippled wing, zero proud grey lips
# ------------------------------------------------------------------------------------------------
gx, gz = GRILLE
for i in range(7):
    z = gz + (3 - i) * 1.70
    sl = [(gx + x, z + q) for x, q in stadium_pts_2d(4.8, 0.85, seg_half=6)]
    cut(["body"], lambda: prism_y("grille_cut", sl, Y0 + 1.5, 4.5))
    assign(prism_y("grille_%d" % i, [(gx + x, z + q) for x, q in stadium_pts_2d(4.7, 0.78, seg_half=6)],
                   Y0 + 1.4, 0.25), M_HOLE)

# ------------------------------------------------------------------------------------------------
# Event Button (0, -9.4): sleek dark satin collar, concave micro-knurl dish, 3 slim ruby-red LED arcs, debossed delta
# ------------------------------------------------------------------------------------------------
bx, bz = BTN
cut(["panel", "body"], lambda: disc("btn_seat_cut", 24.0, bx, bz, YP + 2.2, YP - 6.0, seg=160))
assign(annulus("btn_groove", bx, bz, 23.45, 24.0, YP + 1.25, YP + 1.8, seg=160), M_HOLE)
DISH0, DISH1 = 0.25, 1.05           # CONCAVE dish: slopes BACKWARD (+Y) from r=19.4 (0.25) down to r=13.1 (1.05)
assign(lathe("btn_collar", bx, bz, [
    (23.45, 1.35), (23.40, 0.12), (22.7, -0.04), (20.3, -0.02), (19.4, DISH0),
], YP, seg=160), M_3_COLLAR)
assign(funnel("btn_dish", bx, bz, 19.4, YP + DISH0, 13.1, YP + DISH1, seg=160), M_3_BUTTON)
disc_btn = assign(disc("btn_disc", 13.1, bx, bz, YP + DISH1 + 0.8, YP + DISH1 - 0.02, seg=120), M_3_DISC)


def dish_y(r):
    return YP + DISH0 + (DISH1 - DISH0) * (19.4 - r) / (19.4 - 13.1) - 0.03


# 3 slim ruby-red Triad LED arcs positioned near outer perimeter of knurled ring (r = 18.20 .. 18.95 mm)
for tag, a0, a1 in (("ur", 20.0, 52.0), ("ul", 128.0, 160.0), ("bot", 254.0, 286.0)):
    assign(funnel("led_arc_" + tag, bx, bz, 18.95, dish_y(18.95), 18.20, dish_y(18.20),
                  seg=160, a0=a0, a1=a1, thick=0.14), M_3_RED)

# Debossed gloss-black 3-blade Axon Delta pocket recessed 0.36 mm into btn_disc
delta_p = delta_polys(9.1, bx, bz - 0.45)
for idx_b, p_blade in enumerate(delta_p):
    cut(["btn_disc"], lambda: prism_y("delta_cut_%d" % idx_b, p_blade, YP + DISH1 + 0.36, 1.4))
lg = flat_logo("logo", delta_p, 0.14, M_3_LOGO, chamfer=0.05)
lg.location = v3(0, YP + DISH1 + 0.36, 0)

# ------------------------------------------------------------------------------------------------
# 6 Perimeter Torx Screws, Bevelled Front Microphones, AXON Wordmark
# ------------------------------------------------------------------------------------------------
screw_targets = ("body", "pocket_l", "pocket_r")
for i, (x, z) in enumerate(((-27.5, 37.4), (27.5, 37.4), (-29.3, 0.0), (29.3, 0.0), (-27.5, -37.4), (27.5, -37.4))):
    y_surf = surface_at(x, z)[0].y / MM
    screw("screw_%d" % i, x, z, y_surf + 0.35, targets=screw_targets)


def bevel_front_mic(name, x, z, r_outer=1.05, r_hole=0.58, target="panel"):
    loc, nor = surface_at(x, z)
    ym = loc.y / MM
    cut([target], lambda: disc(name + "_cut", r_outer, x, z, ym + 1.2, ym - 1.0, seg=24))
    assign(lathe(name + "_funnel", x, z, [
        (r_outer, -0.02), (r_hole, 0.55), (r_hole, 0.85),
    ], ym, seg=24), M_3_FACE)
    assign(disc(name, r_hole, x, z, ym + 0.90, ym + 0.52, seg=20), M_HOLE)


bevel_front_mic("mic_1", -16.2, 11.4, r_outer=0.95, r_hole=0.55, target="panel")
bevel_front_mic("mic_2", 0.0, -38.8, r_outer=1.25, r_hole=0.70, target="panel")
front_text("axon_txt", "AXON", 0.0, -34.0, 14.3, M_TEXT, font=r"C:\Windows\Fonts\segoeuil.ttf", extrude=0.05, lift=0.02)

# Bottom cavities cut before bottom parts are added
usbc_cut_pts = [(x, -2.0 + y) for x, y in stadium_pts_2d(9.0, 3.3, seg_half=8)]
cut(["body"], lambda: prism_z("usbc_pocket_cut", usbc_cut_pts, Z_BOT + 2.3, -4.0))
for i, s_ in enumerate((-1, 1)):
    cut(["body"], lambda: cyl_z("bot_mic_cut_%d" % i, 1.75, s_ * 16.0, -2.0, Z_BOT + 1.6, Z_BOT - 2.0, seg=28))

# ------------------------------------------------------------------------------------------------
# Top Deck (+Z = Z_TOP): Vertical Operation LED Slot + Monochrome LCD + Right Power Button
# ------------------------------------------------------------------------------------------------
# 6A. Operation LED (Left: X = -16.1, Y = -2.0): slim vertical pill slot 1.0 W x 4.0 D
op_seam_pts = [(-16.1 + x, -2.0 + y) for x, y in stadium_pts_2d(1.5, 4.6, seg_half=6)]
assign(prism_z("top_led_cup", op_seam_pts, Z_TOP - 0.6, 0.82, chamfer=0.10, seg=1), M_HOLE)
op_led_pts = [(-16.1 + x, -2.0 + y) for x, y in stadium_pts_2d(1.0, 4.0, seg_half=6)]
assign(prism_z("top_led", op_led_pts, Z_TOP - 0.3, 0.72, chamfer=0.18, seg=2), M_LED)

# 6B. Monochrome LCD Window & Rubber Surround (Center: X = -0.3, Y = -2.0)
lcd_bezel = assign(
    box("top_lcd_bezel", 29.8, 14.8, 2.2, (-0.3, -2.0, Z_TOP + 0.3), bevel=0.85, seg=3),
    M_3_RUBBER,
)
boolean(lcd_bezel, box("lcd_well_cut", 25.6, 11.4, 1.4, (-0.3, -2.0, Z_TOP + 1.55), bevel=0.45, seg=2))
assign(box("top_lcd_seam", 25.6, 11.4, 0.3, (-0.3, -2.0, Z_TOP + 0.95), bevel=0.35, seg=2), M_HOLE)
assign(box("top_lcd_window", 25.4, 11.2, 0.8, (-0.3, -2.0, Z_TOP + 0.72), bevel=0.40, seg=2), M_3_LCD)

# Subtle transflective monochrome LCD status readout
assign(box("lcd_bat_body", 4.6, 2.4, 0.06, (7.8, -0.1, Z_TOP + 1.13), bevel=0.02, seg=1), M_3_LCD_SEG)
assign(box("lcd_bat_nub", 0.6, 1.1, 0.06, (10.3, -0.1, Z_TOP + 1.13), bevel=0.01, seg=1), M_3_LCD_SEG)
for k, x_seg in enumerate((-8.8, -5.8, -2.8)):
    assign(box("lcd_stat_seg_%d" % k, 2.1, 0.9, 0.06, (x_seg, -3.7, Z_TOP + 1.13), bevel=0.01, seg=1), M_3_LCD_SEG)

# 6C. Top-Right Power Button (X = +21.8, Y = -2.0): rounded pad + power symbol bar
pwr_seam_pts = [(21.8 + x, -2.0 + y) for x, y in stadium_pts_2d(7.4, 11.2, seg_half=10)]
assign(prism_z("top_pwr_seam", pwr_seam_pts, Z_TOP - 1.2, 1.38, chamfer=0.12, seg=1), M_HOLE)
pwr_btn_pts = [(21.8 + x, -2.0 + y) for x, y in stadium_pts_2d(6.8, 10.6, seg_half=12)]
assign(prism_z("top_pwr_btn", pwr_btn_pts, Z_TOP - 1.2, 2.25, chamfer=0.50, seg=3), M_3_RUBBER)
pwr_bar_pts = [(21.8 + x, -2.0 + y) for x, y in stadium_pts_2d(0.75, 3.6, seg_half=6)]
assign(prism_z("top_pwr_bar", pwr_bar_pts, Z_TOP + 0.90, 0.45, chamfer=0.16, seg=2), M_3_RUBBER)

# ------------------------------------------------------------------------------------------------
# Left Side (-X = -33.0 mm, Viewed from Front):
#   Upper 3-Button Strip (Vol+ /\ , proud 3-bar Select ===, Vol- \/ )
#   + Middle Smooth Bridge + Belt Groove
#   + Lower Diamond-Knurled Program Pad (Z = -6.8 .. -27.3)
# ------------------------------------------------------------------------------------------------
# Upper housing bezel base (-X: Z = +4.2..+36.8, Y = -5.5..+4.2)
upper_base_pts = [(-0.6 + y, 20.5 + z) for y, z in stadium_pts_2d(13.2, 32.6, seg_half=10)]
assign(prism_x("left_upper_strip", upper_base_pts, -hw + 0.8, -1.30, chamfer=0.45, seg=2), M_3_RUBBER)


def left_pad(name, z0, z1, proud_mm, y_w=11.4):
    zc = (z0 + z1) / 2.0
    zh = z0 - z1
    b = box(name, proud_mm + 0.8, y_w, zh, (-hw - (proud_mm - 0.8) / 2.0, -0.6, zc), bevel=0.55, seg=2)
    return assign(b, M_3_RUBBER), -hw - proud_mm, zc


# 1) Volume Up (Z = +35.4..+26.6, 0.95 mm proud) + raised upward triangle
_, xf_vu, zc_vu = left_pad("btn_vol_up", 35.4, 26.6, 0.95)
tri_up = [(-0.6 - 1.8, zc_vu - 1.25), (-0.6 + 1.8, zc_vu - 1.25), (-0.6, zc_vu + 1.55)]
assign(prism_x("mark_vol_up", tri_up, xf_vu + 0.12, -0.52, chamfer=0.12, seg=2), M_3_RUBBER)

# 2) Select (Z = +25.4..+13.4, 1.55 mm proud) + 3 raised horizontal tactile grip bars (===)
_, xf_sel, zc_sel = left_pad("btn_select", 25.4, 13.4, 1.55, y_w=12.0)
for k, dz_bar in enumerate((-2.8, 0.0, 2.8)):
    bar_pts = [(-0.6 + y, zc_sel + dz_bar + z) for y, z in stadium_pts_2d(9.0, 1.15, seg_half=5)]
    assign(prism_x("mark_select_bar_%d" % k, bar_pts, xf_sel + 0.12, -0.62, chamfer=0.18, seg=2), M_3_RUBBER)

# 3) Volume Down (Z = +12.2..+4.6, 0.95 mm proud) + raised downward triangle
_, xf_vd, zc_vd = left_pad("btn_vol_down", 12.2, 4.6, 0.95)
tri_dn = [(-0.6 + 1.8, zc_vd + 1.25), (-0.6 - 1.8, zc_vd + 1.25), (-0.6, zc_vd - 1.55)]
assign(prism_x("mark_vol_down", tri_dn, xf_vd + 0.12, -0.52, chamfer=0.12, seg=2), M_3_RUBBER)

# 4) Lower Diamond-Knurled Program Button Pad (Z = -6.5 .. -29.0, 1.55 mm proud + dense diamond pyramids)
prog_pad, xf_pr, zc_pr = left_pad("btn_program", -6.5, -29.0, 1.55, y_w=13.2)
knurl_patch("btn_program_knurl", "x", xf_pr + 0.05, (-6.5, 5.3), (-27.8, -7.6), 1.30, 0.44, M_3_GRIP, sign=-1)

# ------------------------------------------------------------------------------------------------
# Right Side (+X = +33.0 mm, Viewed from Front):
#   Two Recessed Fine Micro-Knurled Grip Panels (+3.8..+35.0 & -35.0..-3.8) Separated by Dual-Groove Bridge
# ------------------------------------------------------------------------------------------------
for tag, z0, z1 in (("upper", 3.8, 35.0), ("lower", -35.0, -3.8)):
    zc = (z0 + z1) / 2.0
    zh = z1 - z0
    cut(["body"], lambda: box("rgrip_cut_" + tag, 1.0, 13.4, zh, (hw, -0.4, zc), bevel=0.22, seg=1))
    assign(box("right_grip_base_" + tag, 0.55, 13.0, zh - 0.5, (hw - 0.48, -0.4, zc), bevel=0.16, seg=1), M_3_GRIP)
    knurl_patch("right_grip_knurl_" + tag, "x", hw - 0.20, (-6.2, 5.4), (z0 + 1.0, z1 - 1.0),
                0.78, 0.16, M_3_GRIP, sign=1)

# Smooth horizontal bridge dual parting grooves at Z = +-2.2 mm + vertical parting seam at Y = +5.8 on both sides
for tag, sx in (("l", -1.0), ("r", 1.0)):
    for gz_tag, gz_val in (("t", 2.2), ("b", -2.2)):
        cut(["body", "pocket_" + tag], lambda: box(f"belt_notch_{tag}_{gz_tag}", 2.2, 17.0, 0.55, (sx * (hw - 0.4), -0.6, gz_val)))
    boolean(body, box("seam_cut_" + tag, 1.0, 0.65, Z_TOP - Z_BOT - 8.0, (sx * hw, 5.8, 0.0)))

# ------------------------------------------------------------------------------------------------
# Bottom View (-Z = Z_BOT): USB-C + 2 Concentric Circular Mic Ports + Drainage Slots
# ------------------------------------------------------------------------------------------------
usbc_bezel = assign(box("bottom_usbc_bezel", 12.2, 6.2, 1.1, (0.0, -2.0, Z_BOT + 0.25), bevel=0.50, seg=2), M_3_RUBBER)
boolean(usbc_bezel, prism_z("usbc_bezel_hole", usbc_cut_pts, Z_BOT + 1.2, -2.5))

usbc_liner_pts = [(x, -2.0 + y) for x, y in stadium_pts_2d(8.8, 3.1, seg_half=8)]
assign(prism_z("bottom_usbc_well", usbc_liner_pts, Z_BOT + 2.25, -0.35), M_HOLE)

usbc_shell = assign(prism_z("bottom_usbc_shell", usbc_liner_pts, Z_BOT + 2.0, -1.85), M_3_BEZEL)
usbc_inner_pts = [(x, -2.0 + y) for x, y in stadium_pts_2d(8.1, 2.4, seg_half=8)]
boolean(usbc_shell, prism_z("usbc_shell_hollow", usbc_inner_pts, Z_BOT + 2.2, -2.5))
assign(box("bottom_usbc_tongue", 6.4, 0.7, 1.6, (0.0, -2.0, Z_BOT + 1.15), bevel=0.15, seg=1), M_SCREW)

# 2 Concentric Circular Recessed Microphone Ports at (+-16.0, -2.0, Z_BOT) matching Manual Bottom View
for i, s_ in enumerate((-1, 1)):
    assign(cyl_z("bot_mic_ring_%d" % i, 1.72, s_ * 16.0, -2.0, Z_BOT + 1.4, Z_BOT + 0.04, seg=28, r_top=1.35), M_3_FACE)
    assign(cyl_z("bot_mic_cup_%d" % i, 1.15, s_ * 16.0, -2.0, Z_BOT + 1.45, Z_BOT + 0.55, seg=24), M_3_RUBBER)
    assign(cyl_z("bot_mic_hole_%d" % i, 0.50, s_ * 16.0, -2.0, Z_BOT + 1.60, Z_BOT + 0.50, seg=20), M_HOLE)

for i, s_ in enumerate((-1, 1)):
    dr_pts = [(s_ * 20.5 + x, 4.0 + y) for x, y in stadium_pts_2d(2.8, 1.3, seg_half=6)]
    assign(prism_z("bottom_drain_%d" % i, dr_pts, Z_BOT + 0.35, -0.38, chamfer=0.08, seg=1), M_HOLE)

# ------------------------------------------------------------------------------------------------
# Back View (+Y = +14.0 mm): RapidLock, Dual Magnets, 5-Slot Vent, AX1023 Plate + Yellow Delta
# ------------------------------------------------------------------------------------------------


def back_disc(name, r, x, z, h, mat, seg=48, chamfer=0.0):
    return assign(disc(name, r, x, z, YB - 0.30, YB + h, seg=seg, chamfer=chamfer, cseg=2), mat)


assign(annulus("rapidlock_rim", 0.0, 2.0, 10.6, 12.5, YB + 0.80, YB - 0.30, seg=72, chamfer_front=0.25), M_MOUNT)
back_disc("rapidlock_well", 10.65, 0.0, 2.0, 0.28, M_HOLE, seg=64)
back_disc("rapidlock_boss", 4.5, 0.0, 2.0, 1.20, M_MOUNT, seg=36, chamfer=0.28)
for i, a in enumerate((0, 180)):
    rad = math.radians(a)
    assign(
        box("rapidlock_lug_%d" % i, 3.0, 1.0, 2.0,
            (7.6 * math.cos(rad), YB + 0.85, 2.0 + 7.6 * math.sin(rad)), bevel=0.28, seg=1),
        M_MOUNT,
    )

for i, z_mag in enumerate((28.0, -26.0)):
    back_disc("magnet_%d" % i, 5.5, 0.0, z_mag, 0.15, M_MAGNET, seg=40, chamfer=0.12)

for i in range(5):
    xv = (-2 + i) * 3.2
    v_pts = [(xv + x, 40.5 + z) for x, z in stadium_pts_2d(1.0, 6.2, seg_half=6)]
    assign(prism_y("back_vent_%d" % i, v_pts, YB - 0.25, -0.32, chamfer=0.06, seg=1), M_HOLE)

for i, s_ in enumerate((-1, 1)):
    back_disc("back_drain_%d" % i, 0.85, s_ * 20.5, -40.5, 0.04, M_HOLE, seg=14)

assign(box("regulatory_plate", 26.0, 0.36, 10.0, (0.0, YB + 0.02, -38.0), bevel=0.55, seg=2), M_LABEL)

ycx, ycz, yr = -9.5, -38.0, 2.2
ytri = [(ycx + yr * math.cos(math.radians(90 + 120 * i)), ycz + yr * math.sin(math.radians(90 + 120 * i))) for i in range(3)]
assign(prism_y("regulatory_yellow_delta", ytri, YB + 0.16, -0.10, chamfer=0.03, seg=1), M_3_YELLOW)
ytri_in = [(ycx + 0.95 * math.cos(math.radians(90 + 120 * i)), ycz + 0.95 * math.sin(math.radians(90 + 120 * i))) for i in range(3)]
assign(prism_y("regulatory_delta_core", ytri_in, YB + 0.20, -0.08), M_3_BODY)

reg_t1 = make_text_mesh("reg_txt_1", "AXON BODY 3", 1.75, 0.05, space=1.04, res_u=2)
reg_t1.rotation_euler = (math.radians(90), 0, math.radians(180))
reg_t1.location = v3(2.2, YB + 0.25, -36.3)
assign(reg_t1, M_3_BODY)

reg_t2 = make_text_mesh("reg_txt_2", "MODEL AX1023  FCC X4GS00947", 1.05, 0.05, space=1.02, res_u=2)
reg_t2.rotation_euler = (math.radians(90), 0, math.radians(180))
reg_t2.location = v3(2.2, YB + 0.25, -39.5)
assign(reg_t2, M_3_BODY)

# Keep crisp front seam bevels while smoothly shading curved slopes (eliminates false facet creases)
finish_shell(body, bevel=0.0)
finish_shell(panel, bevel=0.0)
meshes = smooth_all(flat=[body], angle=35, flat_angle=28)
print("zbc_bodycam_3: %d parts" % len(meshes))
