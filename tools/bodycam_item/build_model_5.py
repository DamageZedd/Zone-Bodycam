"""Zone Bodycam - builds the Axon Body 5 (2026) item model in Blender.

Run inside Blender with __file__ set (export_variant.py does this):
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
Creates the scene "zbc_bodycam_5", every part its own single-material object, ready for export_variant.py.

Reference: Axon's own launch images (the near-frontal og image on axon.com, measured at 10.32 px per mm, and
the two-camera 3/4 render published with the launch on officer.com and PR Newswire). Axon has not published
dimensions; 62 x 99 x 28 mm is scaled from those images (front aspect 1.59, depth about 0.45 of the width).
Look: a tall black body with six Torx screws in the side rails, a lighter faceted centre plate carrying one
lens in the low centre of an X-shaped channel holding four green LED bars, raised trapezoids between its arms, diamond-hole speaker grilles either side, an IR
window above the lens and a sensor pill below it, a big octagonal dished Event button with the engraved Axon delta,
AXON under it; a knurled panel down the right side, buttons on the left, RapidLock mount on the back.
Units are metres in Blender, millimetres below. Front faces -Y, Z is up, X is right as seen from the front.
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

# ---- body (mm)
W, H, D = 62.0, 99.0, 28.0
hw, hh = W / 2, H / 2
CUT_T, CUT_B = 7.5, 6.5             # corner cuts, top and bottom
CORNER_R = 2.4
FRONT_R = 1.6
BACK_BEVEL = 2.5
Y0 = -D / 2                       # front of the side rails
H_PLATE = 1.4                     # centre plate in front of the rails
YP = Y0 - H_PLATE
PX = 21.5                         # centre plate half width
PZ = (45.0, -47.5)                # centre plate top and bottom

LENS = (0.0, 25.7)
BTN = (0.0, -11.1)
BTN_OUT = (20.3, 7.8, -30.0)      # bezel: half width, top, bottom
BTN_PAD = (16.2, 4.8, -27.1)      # cushion pad

M_5_GREEN = own_material("zbc_5_green", (0.55, 0.95, 0.10), 0.30, emission=(0.35, 0.85, 0.05))
M_5_PAD = own_material("zbc_5_pad", (0.026, 0.027, 0.029), 0.55)

# ------------------------------------------------------------------------------------------------
# shell
# ------------------------------------------------------------------------------------------------
outline = [(-hw + CUT_T, hh), (hw - CUT_T, hh), (hw, hh - CUT_T * 0.9), (hw, -hh + CUT_B * 0.9), (hw - CUT_B, -hh),
           (-hw + CUT_B, -hh), (-hw, -hh + CUT_B * 0.9), (-hw, hh - CUT_T * 0.9)]
body = prism_y("body", outline, D / 2, D)
bm = bmesh.new()
bm.from_mesh(body.data)
ye = [e for e in bm.edges if abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-9 and abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-9]
bmesh.ops.bevel(bm, geom=ye, offset=CORNER_R * MM, segments=6, profile=0.5, affect="EDGES", clamp_overlap=True)
fe = [e for e in bm.edges if all(abs(v.co.y - Y0 * MM) < 1e-9 for v in e.verts)]
bmesh.ops.bevel(bm, geom=fe, offset=FRONT_R * MM, segments=3, profile=0.5, affect="EDGES", clamp_overlap=True)
be = [e for e in bm.edges if all(abs(v.co.y - (D / 2) * MM) < 1e-9 for v in e.verts)]
bmesh.ops.bevel(bm, geom=be, offset=BACK_BEVEL * MM, segments=4, profile=0.5, affect="EDGES", clamp_overlap=True)
bm.to_mesh(body.data)
bm.free()
assign(body, M_BODY)

# ------------------------------------------------------------------------------------------------
# centre plate (user-checked against Axon's renders): the whole front is slopes and valleys, only the AXON
# label is flat. The plate's own face is the VALLEY level; every region between the X arms (top, left, right,
# under the lens) and between the bottom legs (bottom block, lower side panels) is a faceted block whose
# sides fall into the valleys and whose top tilts down away from its junction. The valleys left between the
# blocks are the X around the lens and the legs under AXON.
# ------------------------------------------------------------------------------------------------
YC = YP + 1.2                     # valley floor (0.2 mm in front of the body face: no z-fighting)
plate_pts = [(-PX + 9.0, PZ[0]), (PX - 9.0, PZ[0]), (PX, PZ[0] - 9.0), (PX, PZ[1] + 5.0), (PX - 5.0, PZ[1]),
             (-PX + 5.0, PZ[1]), (-PX, PZ[1] + 5.0), (-PX, PZ[0] - 9.0)]
plate = prism_y("plate", rounded_poly(plate_pts, 1.2, 3), Y0 + 0.4, (Y0 + 0.4) - YC, chamfer=0.5, seg=2)


def clip(poly, a_, b_, c_):
    """Keep the part of a convex polygon where a_ * x + b_ * z >= c_."""
    out = []
    n = len(poly)
    for i in range(n):
        p0, p1 = poly[i], poly[(i + 1) % n]
        f0, f1 = a_ * p0[0] + b_ * p0[1] - c_, a_ * p1[0] + b_ * p1[1] - c_
        if f0 >= 0:
            out.append(p0)
        if (f0 >= 0) != (f1 >= 0):
            tt = f0 / (f0 - f1)
            out.append((p0[0] + (p1[0] - p0[0]) * tt, p0[1] + (p1[1] - p0[1]) * tt))
    return out


def plate_clip(poly, inset):
    n = len(plate_pts)
    for i in range(n):
        (x0, z0), (x1, z1) = plate_pts[i], plate_pts[(i + 1) % n]
        a_, b_ = -(z1 - z0), (x1 - x0)                 # inward normal of a CCW? polygon edge
        ln = math.hypot(a_, b_)
        a_, b_ = a_ / ln, b_ / ln
        if a_ * (0 - x0) + b_ * (0 - z0) < 0:          # make it point inside
            a_, b_ = -a_, -b_
        poly = clip(poly, a_, b_, a_ * x0 + b_ * z0 + inset)
    return poly


def line_side(poly, p, d, w, left=True):
    """Keep the side of the line through p with direction d, at least w away from it."""
    nl = (-d[1], d[0]) if left else (d[1], -d[0])
    return clip(poly, nl[0], nl[1], nl[0] * p[0] + nl[1] * p[1] + w)


RISE = 1.8                        # blocks stand 3 mm above the valley floor


def block(name, region, centre, base_w, top_w, tilt=1.4):
    """Frustum over region(w): base outline (valley edge) at the valley floor, top outline set in by the slope
    width; the top sinks by `tilt` mm with distance from `centre` (it falls away from its junction)."""
    base = region(base_w)
    top = region(top_w)
    if len(base) < 3 or len(top) < 3:
        return
    ds = [math.hypot(x - centre[0], z - centre[1]) for x, z in top]
    d0, d1 = min(ds), max(ds)
    pts = [(x, YC + 0.3, z) for x, z in base]
    pts += [(x, YP - RISE + tilt * (dd - d0) / max(d1 - d0, 1e-6), z) for (x, z), dd in zip(top, ds)]
    boolean(plate, hull(name, pts), op="UNION")


lx, lz = LENS
C = (lx, lz)
ARMS = ((-11.6, 36.0, -35), (12.1, 36.0, 35), (-12.1, 15.0, 35), (12.1, 15.0, -35))
ang = {}
for x, z, a in ARMS:
    ang[(x, z)] = math.atan2(z - lz, x - lx)
order = sorted(ang, key=lambda q: ang[q] % (2 * math.pi))     # UR, UL, LL, LR
BIG = [(-40, 60), (40, 60), (40, -60), (-40, -60)][::-1]
Z_BEZ_TOP = BTN_OUT[1] + 1.2                                  # blocks stop above the button bezel
for i in range(4):
    pa, pb = order[i], order[(i + 1) % 4]
    ua = Vector((pa[0] - lx, pa[1] - lz)).normalized()
    ub = Vector((pb[0] - lx, pb[1] - lz)).normalized()
    m = (ua + ub).normalized()

    def region(w, ua=ua, ub=ub, m=m):
        r = line_side(BIG, C, ua, w, left=True)
        r = line_side(r, C, ub, w, left=False)
        r = clip(r, m.x, m.y, m.x * lx + m.y * lz + 8.4 + (w - 2.4))
        r = clip(r, 0, 1, Z_BEZ_TOP + (w - 2.4))
        return plate_clip(r, 0.4 + (w - 2.4))
    block("x_block_%d" % i, region, C, 2.4, 4.2)

# bottom: AXON junction (flat, recessed) with two legs running out to the bottom corners
AX_TOP = [(-11.5, -31.0), (11.5, -31.0), (12.4, -33.0), (6.8, -39.8), (-6.8, -39.8), (-12.4, -33.0)]
AX_FLOOR = [(-9.6, -32.6), (9.6, -32.6), (10.2, -33.8), (5.6, -38.6), (-5.6, -38.6), (-10.2, -33.8)]
LEG = {sx: (Vector((sx * 6.8, -38.6)), (Vector((sx * 24.0, -50.5)) - Vector((sx * 6.8, -38.6))).normalized())
       for sx in (-1, 1)}
Z_BEZ_BOT = BTN_OUT[2] - 1.0
AXC = (0.0, -36.0)


def bottom_region(w):
    r = line_side(BIG, LEG[-1][0], LEG[-1][1], w, left=True)        # below / right of the left leg
    r = line_side(r, LEG[1][0], LEG[1][1], w, left=False)           # below / left of the right leg
    r = clip(r, 0, -1, 39.8 + (w - 2.4) + 0.8)                     # under the AXON junction
    return plate_clip(r, 0.4 + (w - 2.4))


block("bottom_block", bottom_region, AXC, 2.4, 4.0)
for sx in (-1, 1):
    def side_region(w, sx=sx):
        r = line_side(BIG, LEG[sx][0], LEG[sx][1], w, left=(sx > 0))  # above / outside the leg
        r = clip(r, 0, -1, -Z_BEZ_BOT + (w - 2.4))                  # below the bezel
        r = clip(r, sx, 0, 12.6 + (w - 2.4) - 0.8)                  # beside the AXON junction
        return plate_clip(r, 0.4 + (w - 2.4))
    block("side_block_%d" % (sx > 0), side_region, AXC, 2.4, 4.0)

boolean(plate, hull("axon_pocket_cut", [(x, YP - 3.0, z) for x, z in AX_TOP] + [(x, YC + 0.4, z) for x, z in AX_FLOOR]
                    + [(x, YC - 0.01, z) for x, z in AX_TOP]))

# top corners: the front falls away 3 mm to the top corners (cut through the plate and the body)
for sx in (-1, 1):
    z_in, z_side, z_out = 40.0, 33.0, 52.0
    pts = [(sx * x, y, z) for x, y, z in (
        (5.0, YP - 0.01, z_in + 2.5), (14.0, YP - 0.01, z_in), (PX + 1.0, YP - 0.01, z_side),
        (hw + 2, Y0 + 0.2, z_side + 3.0), (5.0, Y0 + 3.0, z_out), (hw + 2, Y0 + 3.0, z_out),
        (5.0, YP - 3, z_in + 2.5), (hw + 2, YP - 3, z_side), (5.0, YP - 3, z_out), (hw + 2, YP - 3, z_out))]
    for tgt in ("plate", "body"):
        boolean(sc.objects[tgt], hull("brow_cut", pts))
# the screw rails slope down from the plate to the outer edges as well
for sx in (-1, 1):
    boolean(body, hull("rail_slope_cut", [(sx * x, y, z) for x, y in ((PX + 0.6, Y0), (hw + 1.0, Y0 + 1.8),
                                                                      (PX + 0.6, Y0 - 6.0), (hw + 1.0, Y0 - 6.0))
                                          for z in (-hh - 2, hh + 2)]))
assign(plate, M_FACE)

# ------------------------------------------------------------------------------------------------
# lens in the low junction, IR window on the top trapezoid, sensor pill on the bottom one
# ------------------------------------------------------------------------------------------------
YL = YC + 0.3                     # bezel top level with the channel floor
cut(["plate", "body"], lambda: disc("lens_pocket_cut", 6.9, lx, lz, YL + 0.9, YL - 5, seg=96))
assign(annulus("lens_gap", lx, lz, 6.4, 6.9, YL + 0.88, YL + 1.1, seg=96), M_HOLE)
assign(lathe("lens_bezel", lx, lz, [(6.4, 0.9), (6.4, -0.1), (5.9, -0.3), (5.0, -0.3), (4.5, 0.3), (4.5, 1.0)],
             YL, seg=96), M_SCREW)          # bright metal bezel ring
assign(disc("lens_seat", 4.5, lx, lz, YL + 1.2, YL + 0.9, seg=72), M_HOLE)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=36, v_segments=18, radius=4.3 * MM)
for v in bm.verts:
    v.co.y *= 1.4 / 4.3
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 1e-7], context="VERTS")
glass = assign(finish(bm, "lens_glass"), M_GLASS)
glass.location = v3(lx, YL + 0.9, lz)

cut(["plate"], lambda: prism_y("ir_cut", [(x, 39.7 + z) for x, z in stadium_pts_2d(7.0, 3.0, seg_half=8)],
                               YP - 0.9, 4.0))
assign(prism_y("ir_window", [(x, 39.7 + z) for x, z in stadium_pts_2d(6.8, 2.8, seg_half=8)], YP - 0.8, 0.3,
               chamfer=0.1), M_GLASS)
assign(prism_y("sensor", [(x, 13.1 + z) for x, z in stadium_pts_2d(3.6, 1.5, seg_half=6)], YP - 0.4, 1.0,
               chamfer=0.1), M_LABEL)

# four green LED bars, each in a pointed window sunk into the channel floor
for i, (x, z, a) in enumerate(ARMS):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    win_o = [(x + u * c - v * s, z + u * s + v * c) for u, v in ((-4.6, 0), (-3.2, 1.55), (3.2, 1.55), (4.6, 0),
                                                                    (3.2, -1.55), (-3.2, -1.55))]
    win_i = [(x + u * c - v * s, z + u * s + v * c) for u, v in ((-3.9, 0), (-2.8, 0.95), (2.8, 0.95), (3.9, 0),
                                                                    (2.8, -0.95), (-2.8, -0.95))]
    for tgt in ("plate", "body"):
        boolean(sc.objects[tgt], hull("led_window_cut", [(a_, YC - 0.01, b_) for a_, b_ in win_o]
                                      + [(a_, YC - 2.0, b_) for a_, b_ in win_o] + [(a_, YC + 0.6, b_) for a_, b_ in win_i]))
    assign(prism_y("led_%d" % i, win_i, YC + 0.7, 0.25, chamfer=0.1, seg=1), M_5_GREEN)

# speaker grilles: diamond grids of round holes in dark pads either side of the lens
for sx, gx, gz in ((-1, -17.0, 27.1), (1, 17.4, 27.6)):
    pad_pts = rounded_poly([(gx - 3.9, gz + 5.3), (gx + 3.9, gz + 5.3), (gx + 3.9, gz - 5.3), (gx - 3.9, gz - 5.3)],
                           1.4, 3)
    cut(["plate"], lambda: prism_y("grille_cut", pad_pts, YP - 0.2, 4.0))       # into the sloped block top
    assign(prism_y("grille_pad_%d" % (sx > 0), pad_pts, YP - 0.1, 0.12), M_BODY)
    bm = bmesh.new()
    for iz in range(-3, 4):
        for ix in range(-2, 3):
            if (ix + iz) % 2:
                continue
            hx, hz = gx + ix * 1.45, gz + iz * 1.45
            bmesh.ops.create_circle(bm, cap_ends=True, segments=10, radius=0.55 * MM,
                                    matrix=Matrix.Translation(v3(hx, YP - 0.23, hz))
                                    @ Matrix.Rotation(math.radians(90), 4, "X"))
    assign(finish(bm, "grille_holes_%d" % (sx > 0)), M_HOLE)

# ------------------------------------------------------------------------------------------------
# Event button: octagonal bezel, cushioned pad with the delta
# ------------------------------------------------------------------------------------------------
bx, bz = BTN


def octagon(hwid, top, bot, ch):
    return [(-hwid + ch, top), (hwid - ch, top), (hwid, top - ch), (hwid, bot + ch), (hwid - ch, bot),
            (-hwid + ch, bot), (-hwid, bot + ch), (-hwid, top - ch)]


# bezel: a frame standing 1.6 mm proud with only a small outer chamfer; its inner wall is a wide funnel down
# to the pad (the photo's lit lower inner rim)
boolean(plate, prism_y("btn_bezel_add", rounded_poly(octagon(*BTN_OUT, 7.0), 2.0, 4), YP + 0.3, 1.9, chamfer=1.0,
                       seg=2), op="UNION")
well = rounded_poly(octagon(17.0, 5.6, -27.9, 6.0), 1.6, 4)
mouth = octagon(19.0, 7.0, -29.4, 6.8)
boolean(plate, hull("btn_funnel_cut", [(a_, YP - 1.61, b_) for a_, b_ in mouth] + [(a_, YP - 4.0, b_) for a_, b_ in mouth]
                    + [(a_, YP - 0.2, b_) for a_, b_ in octagon(17.0, 5.6, -27.9, 6.0)]))
cut(["plate"], lambda: prism_y("btn_well_cut", well, YP + 0.25, 4.0))
assign(prism_y("btn_well", well, YP + 0.3, 0.05), M_HOLE)
# the pad sits inside the raised bezel and is a shallow DISH (photo: its lower part faces the top light);
# the delta on it is an engraved outline, plus four tick grooves at its corners
PAD_FRONT = YP - 1.1
DISH = 1.0                        # depth at the centre
RS = (14.5 ** 2 + DISH ** 2) / (2 * DISH)


def dish_pad(name, outline_pts, cx, cz, y_back, y_front, chamfer=0.6):
    """Clean manifold pad: side wall, a rounded rim, then rings shrinking to the centre whose depth follows a
    sphere of radius RS (the dish), and a flat back. (Booleans with a big sphere left holes.)"""
    bm = bmesh.new()
    n = len(outline_pts)
    span = max(math.hypot(x - cx, z - cz) for x, z in outline_pts)
    prof = [(1.0, y_back), (1.0, y_front + chamfer)]
    prof += [(1.0 - (chamfer / span) * (1 - math.cos(math.pi / 2 * k / 3)),
              y_front + chamfer * (1 - math.sin(math.pi / 2 * k / 3))) for k in range(1, 4)]
    s0 = prof[-1][0]
    rings = [[bm.verts.new(v3(cx + (x - cx) * s, yy, cz + (z - cz) * s)) for x, z in outline_pts] for s, yy in prof]
    for k in range(1, 16):
        s = s0 * (1 - k / 16)
        ring = []
        for x, z in outline_pts:
            px_, pz_ = cx + (x - cx) * s, cz + (z - cz) * s
            r_ = math.hypot(px_ - cx, pz_ - cz)
            ring.append(bm.verts.new(v3(px_, y_front + max(0.0, DISH - r_ * r_ / (2 * RS)), pz_)))
        rings.append(ring)
    centre = bm.verts.new(v3(cx, y_front + DISH, cz))
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([r0[i], r0[j], r1[j], r1[i]])
    for i in range(n):
        bm.faces.new([rings[-1][i], rings[-1][(i + 1) % n], centre])
    bm.faces.new(list(reversed(rings[0])))
    return finish(bm, name)


pad = assign(dish_pad("btn_pad", rounded_poly(octagon(*BTN_PAD, 5.6), 2.2, 4), bx, bz, YP + 0.25, PAD_FRONT), M_5_PAD)


def dish_depth(px_, pz_):
    return DISH - (math.hypot(px_ - bx, pz_ - bz) ** 2) / (2 * RS)


for poly in delta_polys(7.0, bx, bz):
    ring = poly + [poly[0]]
    for p0, p1 in zip(ring, ring[1:]):
        floor = PAD_FRONT + min(dish_depth(*p0), dish_depth(*p1)) + 0.3
        cut(["btn_pad"], lambda: prism_y("delta_groove_cut", stroke([p0, p1], 0.4), floor, 3.0))
for sx in (-1, 1):
    for sz in (-1, 1):
        cx, cz = bx + sx * 12.6, bz + sz * 8.6
        cut(["btn_pad"], lambda: prism_y("tick_cut", stroke([(cx - sx * 1.3, cz + sz * 1.3),
                                                             (cx + sx * 1.3, cz - sz * 1.3)], 0.35),
                                         PAD_FRONT + 0.3, 4.0))

# screws, microphones, wordmark
for i, (x, z) in enumerate(((-26.5, 38.8), (26.5, 38.8), (-26.5, -1.0), (26.5, -1.0), (-26.5, -40.2), (26.5, -40.2))):
    screw("screw_%d" % i, x, z, surface_at(x, z)[0].y / MM + 0.35)   # seated on the (possibly sloped) rail
front_mic("mic_1", -22.6, 4.4, 0.5)
front_mic("mic_2", 22.6, 4.4, 0.5)
front_text("axon_txt", "AXON", 0.0, -35.6, 11.6, M_TEXT, font=r"C:\Windows\Fonts\segoeuil.ttf")

# ------------------------------------------------------------------------------------------------
# sides, top, bottom, back
# ------------------------------------------------------------------------------------------------
# right side: a recessed panel of fine diagonal knurl (Axon's render), not ribs
boolean(body, box("grip_cut", 3.0, 18.0, 62.0, (hw + 0.6, 0.5, -3.0), bevel=0.5, seg=2))
assign(box("grip_floor", 0.3, 17.6, 61.6, (hw - 0.85, 0.5, -3.0)), M_RUBBER)
knurl_patch("grip", "x", hw - 0.7, (-8.0, 9.0), (-33.4, 27.4), 1.1, 0.45, M_RUBBER, sign=1)

# left side: programmable, volume up / down and power buttons, each with a tactile mark
for i, (zc, zl, mark) in enumerate(((30.0, 9.0, "dot"), (17.0, 9.0, "up"), (5.0, 9.0, "down"), (-12.0, 12.0, "bar"))):
    assign(box("side_seam_%d" % i, 1.0, 12.6, zl + 1.2, (-hw + 0.3, -1.0, zc), bevel=0.5, seg=2), M_HOLE)
    assign(box("side_btn_%d" % i, 2.4, 11.6, zl, (-hw - 0.4, -1.0, zc), bevel=0.9, seg=3), M_RUBBER)
    if mark == "dot":
        assign(box("side_mark_%d" % i, 0.5, 2.0, 2.0, (-hw - 1.75, -1.0, zc), bevel=0.24, seg=2), M_RUBBER)
    elif mark in ("up", "down"):
        k = 1 if mark == "up" else -1
        assign(prism_x("side_mark_%d" % i, [(-1.0 - 1.6, zc - 1.1 * k), (-1.0 + 1.6, zc - 1.1 * k), (-1.0, zc + 1.4 * k)],
                       -hw - 1.55, -0.45, chamfer=0.1, seg=1), M_RUBBER)
    else:
        assign(box("side_mark_%d" % i, 0.45, 1.0, 6.0, (-hw - 1.75, -1.0, zc), bevel=0.2, seg=1), M_RUBBER)

# top: status display strip and the operation LED
assign(box("top_display_bezel", 22.0, 10.0, 1.4, (0, -2.0, hh + 0.1), bevel=0.6, seg=2), M_RUBBER)
assign(box("top_display", 18.0, 6.6, 0.6, (0, -2.0, hh + 0.6), bevel=0.25, seg=2), M_GLASS)
assign(cyl_z("top_led", 1.1, -16.0, -3.0, hh - 0.3, hh + 0.45, seg=20, chamfer=0.25), M_5_GREEN)

# bottom: USB-C and two dock contacts
usbc = [(x, -1.5 + y) for x, y in stadium_pts_2d(9.0, 3.2, seg_half=8)]
cut(["body"], lambda: prism_z("usbc_cut", usbc, -hh + 2.5, -4.0))
assign(prism_z("usbc_shell", [(x, -1.5 + y) for x, y in stadium_pts_2d(8.6, 2.8, seg_half=8)], -hh + 2.4, -2.2), M_BEZEL)
assign(box("usbc_tongue", 6.4, 0.7, 1.5, (0, -1.5, -hh + 1.2), bevel=0.15, seg=1), M_SCREW)
for i, x in enumerate((-13.5, 13.5)):
    assign(cyl_z("pogo_%d" % i, 1.2, x, -1.5, -hh + 0.4, -hh - 0.15, seg=20, chamfer=0.2), M_SCREW)

# back: RapidLock receiver, two magnets, regulatory label
YB = D / 2
assign(annulus("rapidlock_rim", 0.0, 4.0, 10.6, 12.5, YB + 0.80, YB - 0.30, seg=72, chamfer_front=0.25), M_MOUNT)
assign(disc("rapidlock_well", 10.65, 0.0, 4.0, YB - 0.30, YB + 0.28, seg=64), M_HOLE)
assign(disc("rapidlock_boss", 4.5, 0.0, 4.0, YB - 0.30, YB + 1.20, seg=36, chamfer=0.28, cseg=2), M_MOUNT)
for i, a in enumerate((0, 180)):
    assign(box("rapidlock_lug_%d" % i, 3.0, 1.0, 2.0, (7.6 * math.cos(math.radians(a)), YB + 0.85, 4.0),
               bevel=0.28, seg=1), M_MOUNT)
for i, z in enumerate((31.0, -24.0)):
    assign(disc("magnet_%d" % i, 5.5, 0.0, z, YB - 0.30, YB + 0.15, seg=40, chamfer=0.12, cseg=2), M_MAGNET)
assign(box("label", 30.0, 0.36, 10.0, (0.0, YB + 0.02, -38.5), bevel=0.55, seg=2), M_LABEL)
for i, (t, z, s) in enumerate((("AXON BODY 5", -36.8, 1.8), ("AXON ENTERPRISE, INC.", -40.0, 1.0))):
    tx = make_text_mesh("label_txt_%d" % i, t, s, 0.05, space=1.04, res_u=2)
    tx.rotation_euler = (math.radians(90), 0, math.radians(180))
    tx.location = v3(0, YB + 0.25, z)
    assign(tx, M_BODY)

finish_shell(body)
finish_shell(plate, bevel=0.2)
meshes = smooth_all(flat=[body, plate])
print("zbc_bodycam_5: %d parts" % len(meshes))
