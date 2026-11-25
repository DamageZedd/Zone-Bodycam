"""Zone Bodycam - builds the Axon Body 2 (AX1001 / #74001, 2016) item model in Blender.

Run inside Blender with __file__ set (export_variant.py does this):
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
Creates the scene "zbc_bodycam_2", every part its own single-material object, ready for export_variant.py.

1:1 CAD & photometric alignment verified against:
- Official Axon Body 2 User Guide orthographic drawings (front 865x1063 @ 12.357 px/mm, top/bottom, back)
- Official Aileron Design high-resolution studio product render & field photographs
Envelope: 70.0 mm max width (67.4 mm core shell + overhanging top-left lens pod & right Function button),
86.9 mm max height (Z in [-43.0, +43.0], crown +42.9), 24.0 mm body depth (25.8 mm at lens pod).
Units are metres in Blender, millimetres below. Front faces -Y, Z is up, X is right as seen from the front.
"""
import math
import os
import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

SCENE = "zbc_bodycam_2"
COMMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "axon_common.py")
exec(compile(open(COMMON, encoding="utf-8").read(), COMMON, "exec"), globals())
setup_scene()
std_materials()

# ---- core dimensions (mm) measured 1:1 on official drawing & Aileron studio photo
W_SHELL = 67.4                     # core body width (X in [-33.7, +33.7]); lens pod overhangs to -35.15, total 70.0
hw = W_SHELL / 2.0
Z_TOP = 39.2                       # right-side shoulder deck height
Z_CROWN = 42.9                     # continuous upper-left sync crown height
Z_BOT = -43.0                      # bottom face
Y_BACK = 12.0                      # back face (24.0 mm core depth)
Y_PLAT = -12.0                     # front plateau
H_MAX = 4.2                        # front hip-roof plateau height above zero lines
Y0 = Y_PLAT + H_MAX                # roof base level (h = 0)
CORNER_R = 2.6
FRONT_R = 1.6
BACK_BEVEL = 2.0

LENS = (-25.25, 30.85)             # lens pod centre (overhangs left edge to X = -35.15)
POD_R = 9.9
BTN = (0.0, -1.82)                 # Event button centre (measured 1.82 mm below Z=0)
BTN_R = 23.1                       # outer Event collar radius

# Hip-roof zero planes centred vertically around BTN[1] = -1.82 so all 4 X-ridges align 1:1
XA, ZA_T, ZA_B = 34.4, 42.6, -46.2
KX, KZ = 0.355, 0.296              # KX / KZ = 1.20 matches diagonal X-arms on drawing


def stipple_material(name, base_col, rough, spec=0.45, scale_coarse=2100.0, scale_fine=7500.0):
    """Coarse two-octave tactical polymer stipple wired to both Base Color (for DDS bake) and Bump."""
    m = own_material(name, base_col, rough, spec=spec)
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    b = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    tex = N.new("ShaderNodeTexCoord")

    n_coarse = N.new("ShaderNodeTexVoronoi")
    n_coarse.feature = "F1"
    n_coarse.inputs["Scale"].default_value = scale_coarse
    n_coarse.inputs["Randomness"].default_value = 0.92
    L.new(tex.outputs["Object"], n_coarse.inputs["Vector"])

    n_fine = N.new("ShaderNodeTexNoise")
    n_fine.inputs["Scale"].default_value = scale_fine
    n_fine.inputs["Detail"].default_value = 5.0
    n_fine.inputs["Roughness"].default_value = 0.70
    L.new(tex.outputs["Object"], n_fine.inputs["Vector"])

    mix_h = N.new("ShaderNodeMath")
    mix_h.operation = "MULTIPLY_ADD"
    mix_h.inputs[1].default_value = 0.62
    L.new(n_coarse.outputs["Distance"], mix_h.inputs[0])
    L.new(n_fine.outputs["Fac"], mix_h.inputs[2])

    # Tactile dark charcoal albedo variation so Cycles DIFFUSE bake preserves the stipple in-game
    c_mix = N.new("ShaderNodeMix")
    c_mix.data_type = "RGBA"
    c_mix.inputs["A"].default_value = (*(v * 0.56 for v in base_col), 1.0)
    c_mix.inputs["B"].default_value = (*(min(1.0, v * 1.65 + 0.005) for v in base_col), 1.0)
    L.new(n_fine.outputs["Fac"], c_mix.inputs["Factor"])
    L.new(c_mix.outputs["Result"], b.inputs["Base Color"])

    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.62
    bump.inputs["Distance"].default_value = 0.00020
    L.new(mix_h.outputs[0], bump.inputs["Height"])
    L.new(bump.outputs[0], b.inputs["Normal"])
    return m


# Per-camera AB2 materials (export_variant.py writes item_zbc_bodycam_2_*.dds automatically)
BAKED = ("zbc_2_body", "zbc_2_face")
M_BODY2 = stipple_material("zbc_2_body", (0.016, 0.017, 0.019), 0.70, spec=0.42)
M_FACE2 = stipple_material("zbc_2_face", (0.019, 0.020, 0.023), 0.72, spec=0.40)
M_RING = own_material("zbc_2_ring", (0.012, 0.026, 0.016), 0.16, spec=0.88)      # dark smoked translucent ring
M_RED = own_material("zbc_2_red", (0.58, 0.014, 0.010), 0.36)                    # deep crimson ON flag
M_WINDOW = own_material("zbc_2_window", (0.010, 0.011, 0.013), 0.14, spec=0.90)  # dark glossy battery window core
M_LED_SMK = own_material("zbc_2_led_smk", (0.28, 0.29, 0.31), 0.22, spec=0.85)   # frosted smoked lightpipe loop
M_BOT_LED = own_material("zbc_2_bot_led", (0.22, 0.020, 0.018), 0.24, spec=0.85) # unlit dark-red bottom dock bar


def prism_y_concave(name, pts_xz, y_back, depth, chamfer=0.0, seg=1):
    """Extrude a possibly concave 2D XZ polygon cleanly and triangulate its caps (manifold for booleans)."""
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new(v3(x, y_back, z)) for x, z in pts_xz])
    bm.normal_update()
    if (depth > 0 and f.normal.y > 0) or (depth < 0 and f.normal.y < 0):
        f.normal_flip()
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]:
        v.co.y -= depth * MM
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    caps = [fc for fc in bm.faces if len(fc.verts) > 4]
    if caps:
        bmesh.ops.triangulate(bm, faces=caps, quad_method="BEAUTY", ngon_method="BEAUTY")
    if chamfer > 0:
        yf = (y_back - depth) * MM
        fe = [e for e in bm.edges if all(abs(v.co.y - yf) < 1e-8 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=fe, offset=chamfer * MM, segments=seg, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return finish(bm, name)


def roof_h(x, z):
    return min(KX * (XA - abs(x)), KZ * (ZA_T - z), KZ * (z - ZA_B), H_MAX)


# ------------------------------------------------------------------------------------------------
# 1. Main Housing Shell: hip-roof front + continuous upper-left crown + 45 deg side grip shoulders
# ------------------------------------------------------------------------------------------------
px = XA - H_MAX / KX
pzt = ZA_T - H_MAX / KZ
pzb = ZA_B + H_MAX / KZ
pts = []
for sx in (-1, 1):
    pts += [
        (sx * XA, Y0, ZA_T + 5.0),
        (sx * XA, Y0, ZA_B),
        (sx * px, Y_PLAT, pzt),
        (sx * px, Y_PLAT, pzb),
        (sx * XA, Y_BACK + 1.5, ZA_T + 5.0),
        (sx * XA, Y_BACK + 1.5, ZA_B),
    ]
body = assign(hull("body", pts), M_BODY2)

outline = (
    [(LENS[0] + POD_R * math.cos(math.radians(a)), LENS[1] + POD_R * math.sin(math.radians(a)))
     for a in range(180, 94, -10)]
    + [
        (-24.5, Z_CROWN), (-5.5, Z_CROWN), (-1.5, Z_TOP), (29.2, Z_TOP),
        (hw, 34.4),
        (hw, 19.6), (hw - 1.4, 17.8), (hw - 1.4, -27.2), (hw, -29.0),
        (hw, -38.0), (29.2, Z_BOT), (-29.2, Z_BOT), (-hw, -38.0),
        (-hw, -29.0), (-hw + 1.4, -27.2), (-hw + 1.4, 17.8), (-hw, 19.6),
        (-hw, 27.0),
    ]
)


def outline_cutter(name):
    o = prism_y(name, outline, Y_BACK, 30.0)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    ye = []
    for e in bm.edges:
        if abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-9 and abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-9:
            vx = e.verts[0].co.x / MM
            vz = e.verts[0].co.z / MM
            if math.hypot(vx - LENS[0], vz - LENS[1]) > POD_R + 0.5 and abs(vx) > 27.0 and abs(vz) > 35.0:
                ye.append(e)
    if ye:
        bmesh.ops.bevel(bm, geom=ye, offset=CORNER_R * MM, segments=6, profile=0.5, affect="EDGES", clamp_overlap=True)
    be = [e for e in bm.edges if all(abs(v.co.y - Y_BACK * MM) < 1e-9 for v in e.verts)]
    bmesh.ops.bevel(bm, geom=be, offset=BACK_BEVEL * MM, segments=4, profile=0.5, affect="EDGES", clamp_overlap=True)
    bm.to_mesh(o.data)
    bm.free()
    return o


boolean(body, outline_cutter("outline_cut"), op="INTERSECT")

# Top front sloped chamfer: slopes back from Z=36.8 at front plateau up to Z_CROWN / Z_TOP at Y=-4.0
boolean(body, hull("top_chamfer_cut", [
    (x, y, z) for x in (-40, 40)
    for y, z in ((-12.8, 36.8), (-4.0, 43.2), (-4.0, 50.0), (-20.0, 50.0), (-20.0, 32.0))
]))

# Right-side step down of the center-top recessed deck & power slider pocket (x > -5.5 drops from Z_CROWN to Z_TOP)
boolean(body, hull("top_deck_step_cut", [
    (-5.5, y, Z_CROWN) for y in (-16.0, 16.0)
] + [
    (-1.5, y, Z_TOP) for y in (-16.0, 16.0)
] + [
    (36.0, y, Z_TOP) for y in (-16.0, 16.0)
] + [
    (x, y, 50.0) for x in (-5.5, 36.0) for y in (-16.0, 16.0)
]))

# Top-right angled U-pocket carved into front/top chamfer for the power slider wedge & red ON flag
pocket_poly = [
    (3.8, 41.0), (8.2, 33.7), (23.6, 33.7), (28.2, 38.4), (29.2, 41.0)
]
boolean(body, prism_y("slider_pocket_cut", pocket_poly, 3.8, 18.0, chamfer=0.4, seg=2))

# Semicircular concave front U-scoop carved into the continuous upper-left sync crown (X = -11.05)
scoop = disc("scoop_cut", 4.1, -11.05, Z_CROWN - 0.1, 1.5, -15.0, seg=48, r_front=4.6)
boolean(body, scoop)

# Lens pod: round boss at top-left corner standing 1.8 mm proud of plateau (25.8 mm total thickness)
lx, lz = LENS
Y_POD = Y_PLAT - 1.8
boolean(body, disc("pod", POD_R, lx, lz, Y0 + 3.0, Y_POD, seg=96, chamfer=0.9, cseg=3), op="UNION")

# Diagonal X-ridge V-creases
bx, bz = BTN
for x0, z0, x1, z1 in (
    (-14.2, 13.8, -19.2, 20.8),
    (14.6, 13.4, 30.8, 34.4),
    (-15.2, -17.8, -32.2, -39.2),
    (15.2, -17.8, 32.2, -39.2),
):
    pts_rib = stroke([(x0, z0), (x1, z1)], 0.52)
    y_fl = Y0 - min(roof_h(x0, z0), roof_h(x1, z1)) + 0.42
    boolean(body, prism_y("x_groove", pts_rib, y_fl + 1.5, 8.0))

# Round front perimeter edge gently
bm = bmesh.new()
bm.from_mesh(body.data)
bm.normal_update()
fe = []
for e in bm.edges:
    if len(e.link_faces) != 2:
        continue
    n1, n2 = (f.normal for f in e.link_faces)
    if (n1.y < -0.35 and abs(n2.y) < 0.25) or (n2.y < -0.35 and abs(n1.y) < 0.25):
        if all(v.co.z / MM < 34.0 for v in e.verts):
            fe.append(e)
bmesh.ops.bevel(bm, geom=fe, offset=FRONT_R * MM, segments=3, profile=0.5, affect="EDGES", clamp_overlap=True)
bm.to_mesh(body.data)
bm.free()

# ------------------------------------------------------------------------------------------------
# 2. Coarse Side Diamond-Pyramid TPE Grips (2.4 mm pitch, visible in front silhouette!)
# ------------------------------------------------------------------------------------------------
GRIP_Z = (-27.0, 17.6)
for s in (-1, 1):
    zt, zb = GRIP_Z[1], GRIP_Z[0]
    boolean(body, box("grip_cut", 3.2, 14.5, zt - zb + 1.4, (s * (hw - 0.1), 1.4, (zt + zb) / 2), bevel=0.35, seg=2))
    assign(box("grip_floor_%d" % (s > 0), 0.35, 14.2, zt - zb + 0.6, (s * (hw - 1.50), 1.4, (zt + zb) / 2)), M_RUBBER)
    knurl_patch(
        "grip_%s" % ("l" if s < 0 else "r"),
        "x",
        s * (hw - 1.45),
        (-5.6, 8.4),
        (zb - 0.2, zt + 0.2),
        2.40,
        1.42,
        M_RUBBER,
        sign=s,
    )

# ------------------------------------------------------------------------------------------------
# 3. Lens Assembly: stepped anodized barrel + multi-coated convex glass dome
# ------------------------------------------------------------------------------------------------
cut(["body"], lambda: disc("lens_well_cut", 8.3, lx, lz, Y_POD + 1.6, Y_POD - 5.0, seg=96))
assign(annulus("lens_gap", lx, lz, 7.7, 8.3, Y_POD + 1.55, Y_POD + 1.85, seg=96), M_HOLE)
assign(lathe("lens_bezel", lx, lz, [
    (7.7, 1.55), (7.7, 0.22), (7.2, 0.05), (6.7, 0.05), (6.4, 0.45), (6.4, 1.35)
], Y_POD, seg=96), M_BEZEL)
assign(disc("lens_barrel", 6.4, lx, lz, Y_POD + 1.85, Y_POD + 1.30, seg=72), M_HOLE)

# Deep wide-angle convex optic (smaller crisp dome radius avoids giant flat box glare)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=4.6 * MM)
for v in bm.verts:
    v.co.y *= 1.35 / 4.6
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 1e-7], context="VERTS")
glass = assign(finish(bm, "lens_glass"), M_GLASS)
glass.location = v3(lx, Y_POD + 1.35, lz)
assign(annulus("lens_ring_mid", lx, lz, 4.5, 6.3, Y_POD + 0.90, Y_POD + 1.32, seg=64), M_BEZEL)
assign(annulus("lens_inner", lx, lz, 0.85, 2.1, Y_POD + 0.30, Y_POD + 0.75, seg=48), M_BEZEL)
assign(disc("lens_pupil", 0.85, lx, lz, Y_POD + 0.75, Y_POD + 0.26, seg=32), M_GLASS)

# ------------------------------------------------------------------------------------------------
# 4. Event Button: raised collar, dark smoked lightpipe ring, stippled face & inlaid 3-blade swirl
# ------------------------------------------------------------------------------------------------
cut(["body"], lambda: disc("btn_seat_cut", BTN_R + 0.35, bx, bz, Y_PLAT + 1.2, Y_PLAT - 6.0, seg=160))
assign(annulus("btn_gap", bx, bz, BTN_R - 0.1, BTN_R + 0.35, Y_PLAT + 1.18, Y_PLAT + 1.45, seg=160), M_HOLE)
assign(lathe("btn_bezel", bx, bz, [
    (BTN_R, 1.2), (BTN_R, -0.85), (BTN_R - 0.45, -1.25), (21.6, -1.25), (21.3, -0.75), (21.3, 0.9)
], Y_PLAT, seg=160), M_GLOSS)
assign(annulus("btn_ring", bx, bz, 20.2, 21.3, Y_PLAT + 0.50, Y_PLAT + 1.05, seg=160), M_RING)
assign(lathe("btn_inner_rim", bx, bz, [
    (20.2, 0.9), (20.2, -0.35), (19.6, -0.35), (19.3, 0.25), (18.6, 0.55)
], Y_PLAT, seg=160), M_GLOSS)

Y_FACE = Y_PLAT + 0.55
btn_face = assign(disc("btn_face", 18.7, bx, bz, Y_PLAT + 1.1, Y_FACE, seg=160, chamfer=0.25, cseg=2), M_FACE2)

# Exact 59-vertex 3-blade Axon swirl traced 1:1 from official Axon Body 2 CAD drawing (mm)
SWIRL_POLY = [
    (-2.7, 15.8), (-1.4, 16.0), (-0.7, 16.0), (-0.7, 15.6), (-1.4, 14.0), (-2.2, 12.1),
    (-2.9, 10.2), (-3.1, 8.9), (-3.0, 7.6), (-2.6, 6.6), (-1.7, 5.5), (-0.6, 4.9),
    (1.2, 4.7), (5.0, 4.7), (7.3, 4.3), (9.3, 3.3), (11.1, 1.9), (12.8, -0.1),
    (15.2, -3.5), (16.4, -5.0), (16.7, -5.6), (15.5, -8.1), (15.2, -8.3), (14.4, -7.4),
    (12.2, -4.6), (9.9, -1.9), (8.7, -0.7), (7.6, -0.1), (6.5, 0.1), (5.4, -0.1),
    (4.3, -0.8), (3.5, -1.7), (2.7, -3.2), (1.9, -4.8), (0.8, -6.5), (-0.6, -8.0),
    (-2.3, -9.4), (-4.7, -10.8), (-7.9, -12.3), (-11.7, -13.9), (-11.8, -14.1), (-11.1, -15.3),
    (-10.5, -15.6), (-9.0, -15.2), (-6.3, -14.1), (-3.7, -12.8), (-1.9, -11.7), (-0.6, -10.5),
    (0.0, -9.4), (0.2, -8.5), (-0.1, -7.2), (-1.2, -5.3), (-3.7, -1.8), (-4.7, 0.2),
    (-5.1, 2.0), (-5.0, 3.8), (-4.1, 9.7), (-3.6, 12.1), (-2.9, 14.8),
]
swirl_mesh = assign(prism_y_concave("swirl", SWIRL_POLY, Y_FACE + 0.05, 0.19), M_GLOSS)

# ------------------------------------------------------------------------------------------------
# 5. Battery Status Window (hollow frosted trapezoidal loop) & Recessed AXON Chin Plate
# ------------------------------------------------------------------------------------------------
hood_base = [(-9.8, -26.4), (9.8, -26.4), (13.2, -32.8), (-13.2, -32.8)]
boolean(body, hull("hood",
    [(x, Y_PLAT + 2.2, z) for x, z in hood_base]
    + [(x * 0.90, Y_PLAT - 0.65, z - 0.08 * (z + 29.4)) for x, z in hood_base]
), op="UNION")

cut(["body"], lambda: prism_y("window_cut", [(-7.8, -27.6), (7.8, -27.6), (9.8, -31.5), (-9.8, -31.5)], Y_PLAT + 0.45, 4.0))
assign(prism_y("window_center", [(-5.8, -28.7), (5.8, -28.7), (7.5, -30.6), (-7.5, -30.6)], Y_PLAT + 0.55, 0.45, chamfer=0.10), M_WINDOW)

lp_bm = bmesh.new()
lp_out = [(-7.2, -28.0), (7.2, -28.0), (9.2, -31.1), (-9.2, -31.1)]
lp_in = [(-6.1, -28.6), (6.1, -28.6), (7.9, -30.6), (-7.9, -30.6)]
yf, yb = Y_PLAT + 0.05, Y_PLAT + 0.55
fo_v = [lp_bm.verts.new(v3(x, yf, z)) for x, z in lp_out]
fi_v = [lp_bm.verts.new(v3(x, yf, z)) for x, z in lp_in]
bo_v = [lp_bm.verts.new(v3(x, yb, z)) for x, z in lp_out]
bi_v = [lp_bm.verts.new(v3(x, yb, z)) for x, z in lp_in]
for i in range(4):
    j = (i + 1) % 4
    lp_bm.faces.new([fi_v[i], fo_v[i], fo_v[j], fi_v[j]])
    lp_bm.faces.new([bo_v[i], bi_v[i], bi_v[j], bo_v[j]])
    lp_bm.faces.new([fo_v[i], bo_v[i], bo_v[j], fo_v[j]])
    lp_bm.faces.new([bi_v[i], fi_v[i], fi_v[j], bi_v[j]])
bmesh.ops.bevel(lp_bm, geom=lp_bm.edges[:], offset=0.08 * MM, segments=1, profile=0.5, affect="EDGES", clamp_overlap=True)
assign(finish(lp_bm, "window_led_loop"), M_LED_SMK)

# AXON chin plate: gently inset 0.25 mm inside crisp V-groove borders
CHIN = [(-13.2, -33.2), (13.2, -33.2), (20.8, -41.7), (-20.8, -41.7)]
for p0, p1 in zip(CHIN, CHIN[1:] + CHIN[:1]):
    floor = Y0 - min(roof_h(*p0), roof_h(*p1)) + 0.60
    cut(["body"], lambda: prism_y("chin_gap_cut", stroke([p0, p1], 0.52), floor, 8.0))

front_text("axon_txt", "AXON", 3.3, -37.5, 16.0, M_TEXT, font=r"C:\Windows\Fonts\segoeuil.ttf")
place_on_front(flat_logo("axon_delta", delta_polys(3.5), 0.10, M_TEXT), -9.2, -37.7, 0.02)

# Dual-channel front microphones
front_mic("mic_1", -25.15, 7.15, 0.65)
front_mic("mic_2", -17.46, -29.00, 0.65)

# ------------------------------------------------------------------------------------------------
# 6. Top: Sculpted Power Slider Wedge, Flush Angled Crimson Flag, Dual LEDs & 2.5mm Sync Port
# ------------------------------------------------------------------------------------------------
# Sculpted trapezoidal/pentagonal angled slider wedge sitting inside top-right pocket (X in [+5.3, +21.7])
wedge_pts = [
    (5.3, 36.7), (8.4, 34.0), (18.6, 34.0), (21.6, 36.7), (16.8, 39.8), (10.2, 39.8)
]
assign(prism_y("slider_wedge", wedge_pts, 3.2, 10.6, chamfer=0.45, seg=3), M_RUBBER)
# Central tactile ridge & twin recessed finger wells on top of slider (matching p08_05 top drawing)
assign(box("slider_tab", 1.5, 6.2, 1.2, (13.5, -1.6, 40.3), bevel=0.32, seg=2), M_RUBBER)
# Flush angled crimson-red ON indicator flag nestled inside the right corner pocket along the top chamfer
flag_pts = [
    (18.6, 33.9), (22.4, 33.9), (26.5, 37.4), (21.9, 37.4)
]
flag_obj = assign(prism_y("flag", flag_pts, -3.5, 6.0, chamfer=0.22, seg=2), M_RED)
# Clip flag front with the exact top front chamfer plane so it lies flush inside the bevel!
boolean(flag_obj, hull("flag_chamfer_clip", [
    (x, y, z) for x in (-40, 40)
    for y, z in ((-12.8, 36.8), (-4.0, 43.2), (-4.0, 50.0), (-20.0, 50.0), (-20.0, 32.0))
]))

# Top LEDs: Function LED (X = -2.4, left of slider) & Operation LED (X = +24.8, right of slider)
assign(box("top_led_fn", 1.1, 2.8, 0.6, (-2.4, -2.5, Z_TOP + 0.05), bevel=0.2, seg=2), M_LED_SMK)
assign(box("top_led_op", 1.1, 2.8, 0.6, (24.8, -1.8, Z_TOP - 0.1), bevel=0.2, seg=2), M_LED_SMK)

# 2.5mm Connection Socket on the continuous upper-left crown (X = -11.05, Y = +0.6)
assign(cyl_z("sync_collar", 3.8, -11.05, 0.6, Z_CROWN - 0.4, Z_CROWN + 0.12, seg=36, chamfer=0.2), M_RUBBER)
assign(cyl_z("sync_port", 1.35, -11.05, 0.6, Z_CROWN - 1.5, Z_CROWN + 0.15, seg=24), M_HOLE)

# Right side: Function button above right grip notch
assign(box("function_seam", 1.0, 8.8, 9.4, (hw - 0.25, -2.0, 26.0), bevel=0.45, seg=2), M_HOLE)
assign(box("function_btn", 1.9, 7.8, 8.4, (hw + 0.30, -2.0, 26.0), bevel=0.70, seg=3), M_RUBBER)

# ------------------------------------------------------------------------------------------------
# 7. Bottom: Recessed Dock Window & Status LED Bar
# ------------------------------------------------------------------------------------------------
cut(["body"], lambda: box("bottom_window_cut", 40.0, 6.2, 2.0, (0, -3.0, Z_BOT), bevel=0.5, seg=2))
assign(box("bottom_window", 39.4, 5.6, 0.35, (0, -3.0, Z_BOT + 0.85), bevel=0.35, seg=2), M_HOLE)
assign(box("battery_bar", 24.0, 1.3, 0.45, (0, -3.8, Z_BOT + 0.72), bevel=0.15, seg=1), M_BOT_LED)

# ------------------------------------------------------------------------------------------------
# 8. Back: Rounded Square Mount Plate + 4 Corner Screws + RapidLock Bayonet + Panels & 6 Rim Screws
# ------------------------------------------------------------------------------------------------
YB = Y_BACK
plate_poly = rounded_poly([(-16.5, -12.5), (16.5, -12.5), (16.5, 20.5), (-16.5, 20.5)], 3.0, seg=4)
assign(prism_y("mount_plate", plate_poly, YB - 0.2, -1.0, chamfer=0.45, seg=2), M_MOUNT)
for i, (sx, sz) in enumerate(((-11.5, 15.5), (11.5, 15.5), (-11.5, -7.5), (11.5, -7.5))):
    assign(disc("mount_screw_well_%d" % i, 1.85, sx, sz, YB + 0.6, YB + 0.86, seg=20), M_HOLE)
    assign(disc("mount_screw_%d" % i, 1.30, sx, sz, YB + 0.6, YB + 0.83, seg=20, chamfer=0.22, cseg=1), M_SCREW)

# RapidLock bayonet keyway mount at (0, +4.0) matching AB2 QSG rear diagram
assign(disc("rapidlock_base", 7.8, 0, 4.0, YB + 0.7, YB + 1.7, seg=48, chamfer=0.4, cseg=2), M_MOUNT)
bayonet_pts = [
    (-5.0, 11.2), (1.8, 11.2), (5.2, 7.6), (5.2, -3.2), (-1.8, -3.2), (-5.2, 0.4)
]
assign(prism_y("rapidlock_key", bayonet_pts, YB + 1.5, -2.0, chamfer=0.35, seg=2), M_MOUNT)
assign(disc("rapidlock_pin_well", 2.4, 0, 4.0, YB + 3.3, YB + 3.58, seg=28), M_HOLE)
assign(disc("rapidlock_pin", 1.2, 0, 4.0, YB + 3.1, YB + 3.55, seg=20, chamfer=0.2, cseg=1), M_SCREW)

# Upper & Lower rear recessed panels + centered pad dots
top_pnl = rounded_poly([(-22.5, 24.5), (22.5, 24.5), (22.5, 35.0), (-22.5, 35.0)], 2.0, seg=3)
assign(prism_y("rear_panel_top", top_pnl, YB - 0.1, -0.32, chamfer=0.15, seg=1), M_MOUNT)
assign(disc("rear_dot_top", 1.9, 0, 29.75, YB + 0.1, YB + 0.28, seg=24, chamfer=0.18), M_BODY2)

bot_pnl = rounded_poly([(-22.5, -29.0), (22.5, -29.0), (22.5, -18.5), (-22.5, -18.5)], 2.0, seg=3)
assign(prism_y("label", bot_pnl, YB - 0.1, -0.32, chamfer=0.15, seg=1), M_LABEL)
assign(disc("rear_dot_bot", 1.9, 0, -23.75, YB + 0.1, YB + 0.28, seg=24, chamfer=0.18), M_BODY2)
for i, (t, z, s) in enumerate((
    ("AXON BODY 2", -20.6, 1.5),
    ("MODEL AX1001  FCC X4GS00947", -26.5, 0.92),
)):
    tx = make_text_mesh("label_txt_%d" % i, t, s, 0.04, space=1.04, res_u=2)
    tx.rotation_euler = (math.radians(90), 0, math.radians(180))
    tx.location = v3(0, YB + 0.26, z)
    assign(tx, M_BODY2)

# 6 perimeter rear Torx assembly screws
for i, (sx, sz) in enumerate((
    (-27.2, 34.0), (27.2, 34.0),
    (-29.4, 4.0), (29.4, 4.0),
    (-27.2, -35.5), (27.2, -35.5),
)):
    assign(disc("rear_screw_well_%d" % i, 1.75, sx, sz, YB - 0.1, YB + 0.08, seg=18), M_HOLE)
    assign(disc("rear_screw_%d" % i, 1.20, sx, sz, YB - 0.1, YB + 0.05, seg=18, chamfer=0.2, cseg=1), M_SCREW)

finish_shell(body)
meshes = smooth_all(flat=[body, btn_face, swirl_mesh])
print("zbc_bodycam_2: %d parts" % len(meshes))
