"""Zone Bodycam - builds the first Axon Body (TASER AXON body, 2013 - Model #73002) item model in Blender.

Run inside Blender with __file__ set (export_variant.py does this):
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
Creates the scene "zbc_bodycam_1", every part its own single-material object, ready for export_variant.py.

Reference: TASER's near-orthographic front product photo (officer_front_2013.png: 10.85 px per mm,
features placed straight from pixels with ph()), 3/4 product photos (officer_drama_2013.png,
officer_plugged_2013.png, officer_unplugged_2013.png), and the TASER AXON body User Manual (MMU0046).
Size 66.0 x 82.2 x 20.0 mm. Front faces -Y, Z is up, X is right as seen from the front.
"""
import math
import os
import bpy
import bmesh
from mathutils import Vector

SCENE = "zbc_bodycam_1"
COMMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "axon_common.py")
exec(compile(open(COMMON, encoding="utf-8").read(), COMMON, "exec"), globals())
setup_scene()
std_materials()

PX_MM, PX_C = 10.85, (386.0, 510.0)    # photo scale and the pixel of the body centre


def ph(px, py):
    """Photo pixel -> (x, z) mm."""
    return ((px - PX_C[0]) / PX_MM, (PX_C[1] - py) / PX_MM)


def phs(pts):
    return [ph(*p) for p in pts]


# ---- body (mm)
W, H, D = 66.0, 82.2, 20.0
hw, hh = W / 2, H / 2
Z_TOP, Z_BOT = hh, -hh
CORNER_R = 5.4
FRONT_R = 2.0
BACK_BEVEL = 2.3
Y0 = -D / 2

LENS = ph(345.0, 184.5)
BTN = ph(387.0, 514.5)


def make_stipple_body_mat(name="zbc_1_body"):
    """Deep tactical matte-black polymer with realistic EDM pebble stipple for Cycles + 1024x1024 bake."""
    m = own_material(name, (0.015, 0.016, 0.018), 0.45, spec=0.58)
    m["baked"] = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    b = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    tc = N.new("ShaderNodeTexCoord")
    # Fine EDM pebble grain (~0.26 mm cell) + subtle macro variation
    vor = N.new("ShaderNodeTexVoronoi")
    vor.feature = "F1"
    vor.inputs["Scale"].default_value = 3600.0
    vor.inputs["Randomness"].default_value = 0.88
    L.new(tc.outputs["Object"], vor.inputs["Vector"])

    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 2500.0
    nz.inputs["Detail"].default_value = 4.0
    nz.inputs["Roughness"].default_value = 0.65
    L.new(tc.outputs["Object"], nz.inputs["Vector"])

    # Combine Voronoi domes (1 - dist) with noise
    inv = N.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    L.new(vor.outputs["Distance"], inv.inputs[1])

    mix_h = N.new("ShaderNodeMath")
    mix_h.operation = "MULTIPLY_ADD"
    mix_h.inputs[1].default_value = 0.76
    L.new(inv.outputs[0], mix_h.inputs[0])
    nz_sc = N.new("ShaderNodeMath")
    nz_sc.operation = "MULTIPLY"
    nz_sc.inputs[1].default_value = 0.24
    L.new(nz.outputs["Fac"], nz_sc.inputs[0])
    L.new(nz_sc.outputs[0], mix_h.inputs[2])

    # Crisp tactical black micro-albedo modulation so both Cycles & OGF bake show realistic stipple grain
    col_mix = N.new("ShaderNodeMix")
    col_mix.data_type = "RGBA"
    col_mix.inputs["A"].default_value = (0.010, 0.011, 0.012, 1.0)
    col_mix.inputs["B"].default_value = (0.023, 0.024, 0.026, 1.0)
    L.new(mix_h.outputs[0], col_mix.inputs["Factor"])
    L.new(col_mix.outputs["Result"], b.inputs["Base Color"])

    bp = N.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.72
    bp.inputs["Distance"].default_value = 0.00028
    L.new(mix_h.outputs[0], bp.inputs["Height"])
    L.new(bp.outputs[0], b.inputs["Normal"])
    return m


M_1_BODY = make_stipple_body_mat("zbc_1_body")
M_1_RED = own_material("zbc_1_red", (0.55, 0.012, 0.008), 0.34, spec=0.55)
M_1_RING = own_material("zbc_1_ring", (0.010, 0.013, 0.012), 0.14, spec=0.70)   # dark smoked battery LED ring
M_1_GLASS = own_material("zbc_1_glass", (0.002, 0.005, 0.010), 0.02, spec=0.45)  # multi-coated dark optic glass
M_1_GLOSS = own_material("zbc_1_gloss", (0.008, 0.009, 0.010), 0.14, spec=0.80)  # deep satin-gloss black trim
M_1_BEZEL = own_material("zbc_1_bezel", (0.004, 0.004, 0.005), 0.22, spec=0.50)  # deep optical black lens baffle
M_1_LABEL = own_material("zbc_1_label", (0.065, 0.067, 0.070), 0.55)             # dark anodized rear plate
M_1_LTXT = own_material("zbc_1_ltxt", (0.45, 0.46, 0.48), 0.45)                  # laser-etched label text


# ------------------------------------------------------------------------------------------------
# custom bmesh helpers (kept inside build_model_1.py per file-ownership rules)
# ------------------------------------------------------------------------------------------------

def vgroove_cutter(name, p0, p1, w_top, w_bot, y_floor, y_front=-18.0):
    """Beveled V-channel cutter along segment p0->p1 (XZ mm) from y_front to y_floor."""
    v0, v1 = Vector(p0), Vector(p1)
    d = v1 - v0
    ln = d.length
    if ln < 1e-6:
        return None
    t = d / ln
    n = Vector((-t.y, t.x))
    # Extend slightly along tangent at ends for clean miter overlap
    a = v0 - t * 0.4
    b = v1 + t * 0.4
    ht, hb = w_top / 2.0, w_bot / 2.0
    pts_top = [tuple(a + n * ht), tuple(b + n * ht), tuple(b - n * ht), tuple(a - n * ht)]
    pts_bot = [tuple(a + n * hb), tuple(b + n * hb), tuple(b - n * hb), tuple(a - n * hb)]
    bm = bmesh.new()
    vf = [bm.verts.new(v3(x, y_front, z)) for x, z in pts_top]
    vb = [bm.verts.new(v3(x, y_floor, z)) for x, z in pts_bot]
    bm.faces.new(vf)
    bm.faces.new(list(reversed(vb)))
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new([vf[i], vb[i], vb[j], vf[j]])
    return finish(bm, name)


def closed_lathe(name, cx, cz, prof, y_ref, seg=96):
    """Watertight closed revolved solid around Y axis at (cx, cz) for safe EXACT booleans."""
    bm = bmesh.new()
    rings = []
    for r, dy in prof:
        rings.append([
            bm.verts.new(v3(cx + r * math.cos(2 * math.pi * i / seg), y_ref + dy, cz + r * math.sin(2 * math.pi * i / seg)))
            for i in range(seg)
        ])
    m = len(rings)
    for k in range(m):
        kn = (k + 1) % m
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new([rings[k][i], rings[kn][i], rings[kn][j], rings[k][j]])
    return finish(bm, name)


def tapered_pocket(name, outer_pts, inner_pts, y_front, y_floor):
    """Closed solid frustum from outer_pts at y_front to inner_pts at y_floor (for beveled recesses)."""
    bm = bmesh.new()
    vf = [bm.verts.new(v3(x, y_front, z)) for x, z in outer_pts]
    vb = [bm.verts.new(v3(x, y_floor, z)) for x, z in inner_pts]
    bm.faces.new(vf)
    bm.faces.new(list(reversed(vb)))
    n = len(outer_pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([vf[i], vb[i], vb[j], vf[j]])
    return finish(bm, name)


def make_beveled_loop_2d(name, pts_2d, y_back, h_front, bev_xy=0.14, h_bev=0.12):
    """Build a crisp closed beveled polygon solid on Y=[y_back, y_back - h_front] without bmesh bevel bugs."""
    n = len(pts_2d)
    # Compute clean mitered inward inset by bev_xy
    area = sum(pts_2d[i][0] * pts_2d[(i + 1) % n][1] - pts_2d[(i + 1) % n][0] * pts_2d[i][1] for i in range(n))
    sgn = 1.0 if area > 0 else -1.0
    inset = []
    for i in range(n):
        p_prev = Vector(pts_2d[i - 1])
        p_curr = Vector(pts_2d[i])
        p_next = Vector(pts_2d[(i + 1) % n])
        e0 = (p_curr - p_prev)
        e1 = (p_next - p_curr)
        if e0.length < 1e-6 or e1.length < 1e-6:
            inset.append(tuple(p_curr))
            continue
        e0.normalize()
        e1.normalize()
        n0 = Vector((-e0.y * sgn, e0.x * sgn))
        n1 = Vector((-e1.y * sgn, e1.x * sgn))
        bis = n0 + n1
        if bis.length < 1e-4:
            inset.append(tuple(p_curr + n0 * bev_xy))
        else:
            bis.normalize()
            denom = max(0.35, bis.dot(n0))
            inset.append(tuple(p_curr + bis * min(bev_xy / denom, bev_xy * 2.2)))

    bm = bmesh.new()
    vb = [bm.verts.new(v3(x, y_back, z)) for x, z in pts_2d]
    vm = [bm.verts.new(v3(x, y_back - (h_front - h_bev), z)) for x, z in pts_2d]
    vt = [bm.verts.new(v3(x, y_back - h_front, z)) for x, z in inset]
    bm.faces.new(list(reversed(vb)))
    bm.faces.new(vt)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([vb[i], vm[i], vm[j], vb[j]])
        bm.faces.new([vm[i], vt[i], vt[j], vm[j]])
    return finish(bm, name)


def make_beveled_strip(name, spine_pts, half_w, y_back, h_front, bev_xy=0.14, h_bev=0.12,
                       start_cap_dir=None, end_cap_dir=None):
    """Build a crisp raised beveled strip along a 2D polyline spine_pts with optional angled end caps."""
    n = len(spine_pts)
    left, right = [], []
    for i in range(n):
        p = Vector(spine_pts[i])
        if i == 0:
            t = (Vector(spine_pts[1]) - p).normalized()
            nrm = Vector((-t.y, t.x))
            if start_cap_dir is not None:
                cdir = Vector(start_cap_dir).normalized()
                # intersect lines p +/- nrm*hw + s*t with p + k*cdir
                det = cdir.x * (-t.y) - cdir.y * (-t.x)
                if abs(det) > 0.2:
                    # p + k*cdir = p + nrm*hw + s*t => k*cdir - s*t = nrm*hw
                    # Solve 2x2: [cdir, -t] * [k, s] = side * nrm * hw
                    for side, arr in ((1.0, left), (-1.0, right)):
                        rhs = nrm * (side * half_w)
                        k = (rhs.x * (-t.y) - rhs.y * (-t.x)) / det
                        arr.append(tuple(p + cdir * k))
                    continue
        elif i == n - 1:
            t = (p - Vector(spine_pts[i - 1])).normalized()
            nrm = Vector((-t.y, t.x))
            if end_cap_dir is not None:
                cdir = Vector(end_cap_dir).normalized()
                det = cdir.x * (-t.y) - cdir.y * (-t.x)
                if abs(det) > 0.2:
                    for side, arr in ((1.0, left), (-1.0, right)):
                        rhs = nrm * (side * half_w)
                        k = (rhs.x * (-t.y) - rhs.y * (-t.x)) / det
                        arr.append(tuple(p + cdir * k))
                    continue
        else:
            t0 = (p - Vector(spine_pts[i - 1])).normalized()
            t1 = (Vector(spine_pts[i + 1]) - p).normalized()
            n0 = Vector((-t0.y, t0.x))
            n1 = Vector((-t1.y, t1.x))
            bis = (n0 + n1)
            if bis.length < 1e-4:
                nrm = n0
            else:
                bis.normalize()
                nrm = bis * min(1.0 / max(0.35, bis.dot(n0)), 2.2)
        left.append(tuple(p + nrm * half_w))
        right.append(tuple(p - nrm * half_w))
    poly = left + list(reversed(right))
    return make_beveled_loop_2d(name, poly, y_back, h_front, bev_xy=bev_xy, h_bev=h_bev)


def make_beveled_arc(name, cx, cz, r_in, r_out, a0_deg, a1_deg, y_back, h_front,
                     seg=64, bev=0.14, h_bev=0.12, ang_cap0=None, ang_cap1=None):
    """Raised circular arc with clean inner/outer beveled walls and optional angled end-cuts."""
    n = max(6, int(seg * abs(a1_deg - a0_deg) / 360.0))
    outer, inner = [], []
    for i in range(n + 1):
        a = math.radians(a0_deg + (a1_deg - a0_deg) * i / n)
        outer.append((cx + r_out * math.cos(a), cz + r_out * math.sin(a)))
        inner.append((cx + r_in * math.cos(a), cz + r_in * math.sin(a)))
    if ang_cap0 is not None:
        # Adjust first outer/inner point along tangent or clip cleanly at straight angle
        pass
    poly = outer + list(reversed(inner))
    return make_beveled_loop_2d(name, poly, y_back, h_front, bev_xy=bev, h_bev=h_bev)


# ------------------------------------------------------------------------------------------------
# shell: rounded slab with clamshell parting seam and wrap-around plate grooves
# ------------------------------------------------------------------------------------------------
outline = rounded_poly([(-hw, hh), (hw, hh), (hw, -hh), (-hw, -hh)], CORNER_R, 8)
body = prism_y("body", outline, D / 2, D)
bm = bmesh.new()
bm.from_mesh(body.data)
fe = [e for e in bm.edges if all(abs(v.co.y - Y0 * MM) < 1e-9 for v in e.verts)]
bmesh.ops.bevel(bm, geom=fe, offset=FRONT_R * MM, segments=5, profile=0.5, affect="EDGES", clamp_overlap=True)
be = [e for e in bm.edges if all(abs(v.co.y - (D / 2) * MM) < 1e-9 for v in e.verts)]
bmesh.ops.bevel(bm, geom=be, offset=BACK_BEVEL * MM, segments=4, profile=0.5, affect="EDGES", clamp_overlap=True)
bm.to_mesh(body.data)
bm.free()
assign(body, M_1_BODY)

# Sculpted overhanging dark switch hood/crown: union onto clean base slab BEFORE grooves/pockets!
hood_front = phs([
    (382, 72),   # 0: left top meet
    (442, 56),   # 1: left upper slope
    (502, 43),   # 2: top peak
    (576, 62),   # 3: right upper slope
    (630, 78),   # 4: right top overhang tip
    (610, 118),  # 5: right inner notch tip
    (590, 128),  # 6: V-notch corner
    (566, 186),  # 7: bottom-right overhang corner
    (452, 172),  # 8: bottom-left ridge corner
    (414, 146),  # 9: left diagonal corner
    (382, 102),  # 10: left cheek
])
def assert_body(tag):
    mn_x = min(v.co.x for v in body.data.vertices)
    mx_y = max(v.co.y for v in body.data.vertices)
    assert mn_x < -0.032 and mx_y > 0.009, f"body shell lost at {tag}: min_x={mn_x:.4f}, max_y={mx_y:.4f}, verts={len(body.data.vertices)}"


hood = prism_y("hump", hood_front, -0.60, -0.60 - (Y0 - 1.75), chamfer=0.50, seg=2)
# Cleanly slope the rear-top of hood down to Z=hh at Y=-0.60 using a solid rotated box cut (always manifold!)
boolean(hood, box("hood_slope_cut", 42.0, 16.0, 12.0, (10.0, 2.0, hh + 6.5), rot=(math.radians(-18), 0, 0)), op="DIFFERENCE")
assign(hood, M_1_BODY)
boolean(body, hood, op="UNION")
assert_body("hood_union")

# Carve clean recessed thumb scoop into the top-front slope of the merged crown
cut(["body"], lambda: box("switch_trough_cut", 7.8, 4.8, 1.8, (11.5, -5.2, hh + 1.35), bevel=0.35, seg=2))
assert_body("switch_trough")
assign(box("switch_slider", 7.0, 4.0, 0.55, (11.5, -5.2, hh + 0.45), bevel=0.20, seg=2), M_RUBBER)

# Side/top/bottom clamshell parting groove at Y = 0.0 (hollow rectangular frame cutter)
seam_out = rounded_poly([(-hw - 2.0, hh + 2.0), (hw + 2.0, hh + 2.0), (hw + 2.0, -hh - 2.0), (-hw - 2.0, -hh - 2.0)], 5.0, 4)
seam_in = rounded_poly([(-hw + 0.36, hh - 0.36), (hw - 0.36, hh - 0.36), (hw - 0.36, -hh + 0.36), (-hw + 0.36, -hh + 0.36)], 5.0, 4)
bm_s = bmesh.new()
# Build hollow ring extruded along Y in [-0.24, +0.24] mm
for side_y in (-0.24, 0.24):
    pass
# Simpler: boolean outer box minus inner box -> cut body
seam_cutter = prism_y("seam_cut_outer", seam_out, 0.24, 0.48)
boolean(seam_cutter, prism_y("seam_cut_inner", seam_in, 1.0, 2.0), op="DIFFERENCE")
boolean(body, seam_cutter, op="DIFFERENCE")
assert_body("seam_cutter")

# Front angular plate V-grooves (measured directly on full_front_grid25.jpg, wrapping onto side walls!)
# (pixel polyline, top width mm, bottom width mm, depth mm, back extent y_front)
GROOVES = [
    ([(12, 168), (242, 276), (294, 352)], 1.45, 0.50, 0.80),          # upper left deep diagonal V-groove
    ([(12, 266), (214, 332), (252, 384)], 1.00, 0.34, 0.50),          # upper left lower plate line
    ([(275, 50), (304, 102)], 0.85, 0.28, 0.44),                      # top-left lens shoulder seam
    ([(12, 500), (148, 548), (178, 608), (214, 688)], 1.00, 0.34, 0.50),  # mid left plate line
    ([(12, 848), (138, 772), (242, 706)], 1.10, 0.36, 0.56),          # lower left diagonal groove
    ([(138, 772), (308, 816), (366, 974)], 1.00, 0.34, 0.50),         # bottom chin plate line
    ([(548, 324), (642, 286), (762, 244)], 1.00, 0.34, 0.50),         # upper right plate line
    ([(682, 518), (762, 528)], 1.00, 0.34, 0.50),                     # mid right over shield
    ([(684, 640), (762, 708)], 1.00, 0.34, 0.50),                     # mid right under shield
    ([(484, 706), (544, 774), (762, 878)], 1.45, 0.50, 0.80),         # lower right deep V-groove
    ([(442, 718), (488, 790), (748, 896)], 0.90, 0.30, 0.46),         # lower right inner step line
]
for idx, (pl, wt, wb, dep) in enumerate(GROOVES):
    q = phs(pl)
    for seg_i, (p0, p1) in enumerate(zip(q, q[1:])):
        cut(["body"], lambda p0=p0, p1=p1, wt=wt, wb=wb, dep=dep:
            vgroove_cutter("gcut_%d_%d" % (idx, seg_i), p0, p1, wt, wb, Y0 + dep, y_front=-15.0))
        assert_body(f"groove_{idx}_{seg_i}")


# ------------------------------------------------------------------------------------------------
# lens housing: low-profile raised collar (0.85 mm proud) + recessed moat + deep satin/gloss barrel
# ------------------------------------------------------------------------------------------------
lx, lz = LENS
# Raised outer collar crest at r=7.95mm (Y0 - 0.85) dropping inward to moat r=7.20mm (Y0 + 0.45)
boolean(body, closed_lathe("lens_collar", lx, lz, [
    (9.10, 0.20),
    (8.60, -0.35),
    (8.15, -0.82),
    (7.80, -0.82),
    (7.40, -0.20),
    (7.20, 0.45),
    (7.20, 1.50),
    (9.10, 1.50),
], Y0, seg=96), op="UNION")
assert_body("lens_collar")
cut(["body"], lambda: disc("lens_moat_cut", 7.35, lx, lz, Y0 + 0.45, Y0 - 5.0, seg=96))
assert_body("lens_moat_cut")

# Inner optical baffle & aperture ring (deep smooth satin black matching photo)
assign(lathe("lens_baffle", lx, lz, [
    (7.08, 0.45),
    (7.08, -0.02),
    (6.75, -0.10),
    (4.95, 0.25),
    (4.25, 0.68),
    (4.25, 1.20),
], Y0, seg=96), M_1_BEZEL)

assign(lathe("lens_ring", lx, lz, [
    (4.25, 0.68),
    (4.05, 0.50),
    (3.70, 0.62),
    (3.52, 0.98),
    (3.52, 1.50),
], Y0, seg=96), M_1_GLOSS)

assign(disc("lens_seat", 3.55, lx, lz, Y0 + 1.65, Y0 + 1.15, seg=64), M_HOLE)

# Multi-coated convex wide-angle lens glass (r=3.48mm dome, realistic dark indigo-cyan AR coating)
bm_g = bmesh.new()
bmesh.ops.create_uvsphere(bm_g, u_segments=36, v_segments=18, radius=3.48 * MM)
for v in bm_g.verts:
    v.co.y *= 1.05 / 3.48
bmesh.ops.delete(bm_g, geom=[v for v in bm_g.verts if v.co.y > 1e-7], context="VERTS")
glass = assign(finish(bm_g, "lens_glass"), M_1_GLASS)
glass.location = v3(lx, Y0 + 1.04, lz)


# ------------------------------------------------------------------------------------------------
# top-right switch crown (sculpted overhanging hood) & recessed crimson-red indicator flag
# ------------------------------------------------------------------------------------------------
# 1. Cut recessed beveled V-pocket on top-right front & top for the red flag (leaving outer right corner rim intact!)
pocket_outer = phs([(545, 174), (620, 96), (708, 92), (708, 132), (618, 206), (558, 198)])
pocket_inner = phs([(556, 174), (624, 102), (698, 100), (698, 126), (615, 194), (566, 188)])
cut(["body"], lambda: tapered_pocket("flag_pocket_cut", pocket_outer, pocket_inner, Y0 - 5.0, Y0 + 1.65))
# Top switch trough: runs along top-right front half Y in [-9.2, -1.2], Z down to hh - 2.0
cut(["body"], lambda: box("top_switch_trough", 14.2, 8.2, 3.8, (22.0, -5.2, hh - 0.3)))

# 2. Recessed deep crimson-red ON indicator flag (L-shaped, tucked INSIDE the pocket, wrapping onto top trough!)
flag_pts = phs([(562, 176), (626, 106), (696, 104), (696, 124), (614, 188), (572, 184)])
assign(prism_y("flag", flag_pts, Y0 + 1.75, 1.15, chamfer=0.18, seg=2), M_1_RED)
assign(box("flag_top", 8.2, 5.6, 1.1, (24.0, -5.2, hh - 1.35), bevel=0.20, seg=2), M_1_RED)
assert_body("flag_pocket")


# ------------------------------------------------------------------------------------------------
# Central Event button: exact concentric collars, smoked LED ring, stippled dish, C-ring & recessed TASER bolt
# ------------------------------------------------------------------------------------------------
bx, bz = BTN

# Concentric raised outer collar
boolean(body, closed_lathe("btn_collars", bx, bz, [
    (18.85, 0.25),
    (18.55, -0.35),
    (17.85, -1.42),
    (17.35, -1.48),
    (16.65, -1.35),
    (15.80, -0.10),
    (15.55, 0.25),
    (15.55, 1.20),
    (18.85, 1.20),
], Y0, seg=144), op="UNION")
assert_body("btn_collars")
cut(["body"], lambda: disc("btn_moat_cut", 15.65, bx, bz, Y0 + 0.15, Y0 - 4.0, seg=144))

# Sleek dark satin 2nd concentric ring inside the moat (steep outer rise, wider beveled inner step)
assign(lathe("btn_ring", bx, bz, [
    (14.12, 0.25),
    (13.95, -0.70),
    (13.70, -0.95),
    (13.40, -0.95),
    (12.82, -0.15),
    (12.75, 0.25),
], Y0, seg=144), M_1_GLOSS)

# Smoked translucent battery LED ring sitting in the outer moat (r=14.12..15.65mm)
assign(annulus("btn_led", bx, bz, 14.12, 15.65, Y0 - 0.14, Y0 + 0.22, seg=144), M_1_RING)
# Dark shadow groove between 2nd ring and button cap (r=12.22..12.85mm)
assign(annulus("btn_gap", bx, bz, 12.22, 12.85, Y0 + 0.02, Y0 + 0.45, seg=144), M_HOLE)

# Gently dished stippled Event button cap (near-flat dish: edge Y0-1.05mm -> center Y0-0.96mm)
bm_cap = bmesh.new()
cap_rings = [(12.28, 0.20), (12.12, -0.62), (11.72, -1.05), (9.50, -1.01), (6.00, -0.98), (2.50, -0.96)]
v_rings = []
for rr, dy in cap_rings:
    ring = [bm_cap.verts.new(v3(bx + rr * math.cos(2 * math.pi * i / 128), Y0 + dy, bz + rr * math.sin(2 * math.pi * i / 128)))
            for i in range(128)]
    v_rings.append(ring)
v_ctr = bm_cap.verts.new(v3(bx, Y0 - 0.95, bz))
for k in range(len(v_rings) - 1):
    for i in range(128):
        j = (i + 1) % 128
        bm_cap.faces.new([v_rings[k][i], v_rings[k + 1][i], v_rings[k + 1][j], v_rings[k][j]])
for i in range(128):
    j = (i + 1) % 128
    bm_cap.faces.new([v_rings[-1][i], v_ctr, v_rings[-1][j]])
v_back_ctr = bm_cap.verts.new(v3(bx, Y0 + 0.20, bz))
for i in range(128):
    j = (i + 1) % 128
    bm_cap.faces.new([v_rings[0][j], v_back_ctr, v_rings[0][i]])
cap_obj = assign(finish(bm_cap, "btn_cap"), M_1_BODY)

# Carve the recessed engraved TASER lightning bolt V-grooves cleanly INTO btn_cap
# Offset joint start points slightly past junctions so cutters don't overlap coplanarly
bolt_left_spine = phs([(386, 424), (354, 518), (372, 518), (327, 619)])
bolt_right_spine = phs([(426, 421), (397, 476), (414, 476), (382, 522), (329, 615)])
bolt_mid_spine = phs([(424, 424), (378, 505), (394, 505), (360, 560)])
for tag, spine, wt, wb, dep in (
    ("bl", bolt_left_spine, 0.56, 0.16, 0.34),
    ("br", bolt_right_spine, 0.56, 0.16, 0.34),
    ("bm", bolt_mid_spine, 0.48, 0.14, 0.30),
):
    for si, (p0, p1) in enumerate(zip(spine, spine[1:])):
        cut(["btn_cap"], lambda p0=p0, p1=p1, wt=wt, wb=wb, dep=dep, tag=tag, si=si:
            vgroove_cutter("bolt_cut_%s_%d" % (tag, si), p0, p1, wt, wb, Y0 - 0.96 + dep, y_front=-14.0))

# Surface reference Y on the dished cap for C-ring
YC = Y0 - 0.99

# Open C-ring: r = 8.65..10.10 mm, angled openings matching the TASER bolt's diagonal pass-through
for i, (a0, a1) in enumerate(((88.5, 224.0), (247.0, 419.5))):
    assign(make_beveled_arc("btn_c_%d" % i, bx, bz, 8.65, 10.10, a0, a1,
                            YC + 0.08, 0.32, seg=128, bev=0.14, h_bev=0.12), M_1_GLOSS)


# ------------------------------------------------------------------------------------------------
# Right-side shield battery button: recessed curved shield well + C-arc rocker + inner groove
# ------------------------------------------------------------------------------------------------
shield_outer = phs([
    (584, 494), (630, 482), (698, 510), (696, 575), (686, 622),
    (662, 666), (632, 699), (576, 672), (542, 642), (566, 608), (578, 565), (578, 518),
])
shield_inner = phs([
    (592, 504), (628, 494), (684, 518), (682, 574), (674, 616),
    (654, 656), (630, 684), (584, 660), (558, 638), (576, 608), (586, 565), (586, 522),
])
# Cut recessed beveled well into body (walls slope inward -> bright BR wall under TL light!)
cut(["body"], lambda: tapered_pocket("shield_well_cut", shield_outer, shield_inner, Y0 - 3.0, Y0 + 0.90))

# Curved C-arc rocker button sitting inside the well (concentric around Event BTN = (bx, bz))
# Radial span r=21.2..26.5mm, angular span -31 deg .. +5 deg
assign(make_beveled_arc("shield_rocker", bx, bz, 21.3, 26.2, -30.5, 4.5,
                        Y0 + 0.95, 1.05, seg=96, bev=0.45, h_bev=0.35), M_1_BODY)
# Curved recessed inner groove in the rocker face (cut via a recessed dark arc channel + central curved ridge)
cut(["shield_rocker"], lambda: make_beveled_arc("shield_groove_cut", bx, bz, 22.9, 24.8, -22.5, -2.5,
                                                Y0 - 2.0, 2.40, seg=72, bev=0.22, h_bev=0.30))
assign(make_beveled_arc("shield_ridge", bx, bz, 23.45, 24.25, -20.0, -4.5,
                        Y0 + 0.45, 0.52, seg=64, bev=0.16, h_bev=0.14), M_1_BODY)


# ------------------------------------------------------------------------------------------------
# Speaker & microphone pinholes (from full_front_grid25.jpg)
# ------------------------------------------------------------------------------------------------
for mname, mpos in (("speaker", ph(492, 260)), ("mic", ph(212, 862))):
    mx, mz = mpos
    cut(["body"], lambda mx=mx, mz=mz, mname=mname: disc(mname + "_cone", 0.95, mx, mz, Y0 + 0.70, Y0 - 2.0,
                                                        seg=24, r_front=1.15))
    assign(disc(mname + "_hole", 0.58, mx, mz, Y0 + 0.90, Y0 + 0.65, seg=20), M_HOLE)


# ------------------------------------------------------------------------------------------------
# Top: flush Operation LED & hex-recessed ETM socket; Bottom: flush Upload LED & recessed Pair button
# ------------------------------------------------------------------------------------------------
# Top-left Operation LED (flush)
cut(["body"], lambda: box("top_led_cut", 2.8, 2.6, 1.0, (-25.8, -5.0, hh - 0.1), bevel=0.3, seg=2))
assign(box("top_led", 2.4, 2.2, 0.8, (-25.8, -5.0, hh - 0.25), bevel=0.25, seg=2), M_1_RED)

# Top-left-center ETM Connection Socket in hexagonal recess
hex_etm = [(-18.5 + 4.8 * math.cos(math.radians(a)), -1.0 + 4.8 * math.sin(math.radians(a))) for a in range(0, 360, 60)]
cut(["body"], lambda: prism_z("etm_hex_cut", hex_etm, hh - 0.35, 3.0))
assign(cyl_z("etm_ring", 2.5, -18.5, -1.0, hh - 0.50, hh - 0.22, seg=32, chamfer=0.15), M_BEZEL)
assign(cyl_z("etm_socket", 1.3, -18.5, -1.0, hh - 0.90, hh - 0.20, seg=24), M_HOLE)

# Bottom: recessed Pairing/Volume rocker pocket + flush Upload Status LED (nothing pokes below -hh!)
hex_pair = [(16.0 + 6.4 * math.cos(math.radians(a)), 0.0 + 3.4 * math.sin(math.radians(a))) for a in range(0, 360, 60)]
cut(["body"], lambda: prism_z("pair_well_cut", hex_pair, -hh + 0.75, -4.0))
assign(prism_z("pair_btn", [(16.0 + 5.2 * math.cos(math.radians(a)), 0.0 + 2.4 * math.sin(math.radians(a)))
                            for a in range(0, 360, 60)], -hh + 0.80, -0.72, chamfer=0.35, seg=2), M_RUBBER)
cut(["body"], lambda: box("upload_led_cut", 2.8, 2.6, 1.0, (-23.5, -5.5, -hh + 0.1), bevel=0.3, seg=2))
assign(box("upload_led", 2.4, 2.2, 0.8, (-23.5, -5.5, -hh + 0.25), bevel=0.25, seg=2), M_1_RED)


# ------------------------------------------------------------------------------------------------
# Back: holster rails and realistic dark silver TASER label
# ------------------------------------------------------------------------------------------------
YBK = D / 2
for i, x in enumerate((-17.0, 17.0)):
    assign(box("rail_%d" % i, 3.0, 1.4, 44.0, (x, YBK + 0.4, 6.0), bevel=0.5, seg=2), M_MOUNT)
assign(box("label", 38.0, 0.3, 13.0, (0.0, YBK + 0.05, -27.0), bevel=0.5, seg=2), M_1_LABEL)
for i, (t, z, s) in enumerate((("TASER  AXON BODY", -24.4, 1.7), ("MODEL 73002", -27.4, 1.2),
                               ("TASER INTERNATIONAL", -30.0, 1.0))):
    tx = make_text_mesh("label_txt_%d" % i, t, s, 0.05, space=1.04, res_u=2)
    tx.rotation_euler = (math.radians(90), 0, math.radians(180))
    tx.location = v3(0, YBK + 0.22, z)
    assign(tx, M_1_LTXT)

finish_shell(body, bevel=0.14, angle=32)
assert min(v.co.x for v in body.data.vertices) < -0.032 and max(v.co.y for v in body.data.vertices) > 0.009, "body shell lost!"
meshes = smooth_all(flat=[body])
print("zbc_bodycam_1: %d parts" % len(meshes))
