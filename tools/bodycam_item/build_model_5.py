"""Zone Bodycam - builds the Axon Body 5 (2026) item model in Blender.

Run inside Blender with __file__ set (export_variant.py does this):
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
Creates the scene "zbc_bodycam_5", every part its own single-material object, ready for export_variant.py.

Reference: Axon's own launch images (the near-frontal og image on axon.com, measured at 10.32 px per mm, and
the two-camera 3/4 render published with the launch on officer.com and PR Newswire). Axon has not published
dimensions; 62 x 99 x 28 mm is scaled from those images (front aspect 1.59, depth about 0.45 of the width).
Look: a tall black body with six Torx screws in the side rails, a lighter faceted centre plate carrying one
lens in an octagonal boss inside an X of four green LED bars, diamond-hole speaker grilles either side, an IR
window above the lens and a sensor pill below it, a big octagonal cushioned Event button with the Axon delta,
AXON under it; a ribbed grip down the right side, buttons on the left, RapidLock mount on the back.
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
PZ = (45.0, -45.5)                # centre plate top and bottom

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
# centre plate: faceted, the big angled facets of the photo above the LED X and below AXON
# ------------------------------------------------------------------------------------------------
plate_pts = [(-PX + 9.0, PZ[0]), (PX - 9.0, PZ[0]), (PX, PZ[0] - 9.0), (PX, PZ[1] + 9.0), (PX - 9.0, PZ[1]),
             (-PX + 9.0, PZ[1]), (-PX, PZ[1] + 9.0), (-PX, PZ[0] - 9.0)]
plate = prism_y("plate", rounded_poly(plate_pts, 1.2, 3), Y0 + 0.4, H_PLATE + 0.4, chamfer=0.7, seg=2)
# the big angled facets: from the LED arms the front falls away 3 mm to the top corners, and from under
# AXON to the bottom corners; they cut through the plate into the body
for sx in (-1, 1):
    for name, zs in (("brow", (40.0, 46.0, 33.0, 52.0)), ("chin", (-41.5, -47.0, -34.0, -53.0))):
        z_in, z_mid, z_side, z_out = zs
        k = 1 if z_in > 0 else -1
        pts = [(sx * x, y, z) for x, y, z in (
            (5.0, YP - 0.01, z_in + 2.5 * k), (14.0, YP - 0.01, z_in), (PX + 1.0, YP - 0.01, z_side),
            (hw + 2, Y0 + 0.2, z_side + 3.0 * k), (5.0, Y0 + 3.0, z_out), (hw + 2, Y0 + 3.0, z_out),
            (5.0, YP - 3, z_in + 2.5 * k), (hw + 2, YP - 3, z_side), (5.0, YP - 3, z_out), (hw + 2, YP - 3, z_out))]
        for tgt in ("plate", "body"):
            boolean(sc.objects[tgt], hull(name + "_cut", pts))
# recessed triangles either side of the lens between the LED arms (the grilles sit in them)
for sx in (-1, 1):
    tri = [(sx * 22.5, 39.0), (sx * 8.0, 25.7), (sx * 22.5, 12.0)]
    boolean(plate, hull("side_recess_cut", [(x, y, z) for x, z in tri for y in (YP + 0.9, YP - 3.0)]
                        + [(sx * 24.0, YP + 0.9, 25.7)]))
assign(plate, M_FACE)

# ------------------------------------------------------------------------------------------------
# lens in an octagonal boss, IR window above, sensor pill below
# ------------------------------------------------------------------------------------------------
lx, lz = LENS
octo = [(lx + 8.2 * math.cos(math.radians(22.5 + 45 * i)), lz + 8.2 * math.sin(math.radians(22.5 + 45 * i)))
        for i in range(8)]
YL = YP - 1.4
boolean(plate, prism_y("lens_boss", octo, YP + 0.3, 1.7, chamfer=0.9, seg=2), op="UNION")
cut(["plate"], lambda: disc("lens_pocket_cut", 6.9, lx, lz, YL + 0.9, YL - 5, seg=96))
assign(annulus("lens_gap", lx, lz, 6.4, 6.9, YL + 0.88, YL + 1.1, seg=96), M_HOLE)
assign(lathe("lens_bezel", lx, lz, [(6.4, 0.9), (6.4, -0.1), (5.9, -0.3), (5.0, -0.3), (4.5, 0.3), (4.5, 1.0)],
             YL, seg=96), M_SCREW)
assign(disc("lens_seat", 4.5, lx, lz, YL + 1.2, YL + 0.9, seg=72), M_HOLE)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=36, v_segments=18, radius=4.3 * MM)
for v in bm.verts:
    v.co.y *= 1.4 / 4.3
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 1e-7], context="VERTS")
glass = assign(finish(bm, "lens_glass"), M_GLASS)
glass.location = v3(lx, YL + 0.9, lz)

cut(["plate"], lambda: prism_y("ir_cut", [(x, 39.7 + z) for x, z in stadium_pts_2d(7.0, 3.0, seg_half=8)],
                               YP + 0.6, 4.0))
assign(prism_y("ir_window", [(x, 39.7 + z) for x, z in stadium_pts_2d(6.8, 2.8, seg_half=8)], YP + 0.7, 0.3,
               chamfer=0.1), M_GLASS)
assign(prism_y("sensor", [(x, 13.1 + z) for x, z in stadium_pts_2d(3.6, 1.5, seg_half=6)], YP + 0.2, 0.25,
               chamfer=0.1), M_LABEL)

# four green LED bars in an X around the lens, each in a dark slot
for i, (x, z, a) in enumerate(((-11.6, 36.0, -35), (12.1, 36.0, 35), (-12.1, 15.0, 35), (12.1, 15.0, -35))):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))

    def bar(L, Wd, x=x, z=z, c=c, s=s):
        return [(x + u * c - v * s, z + u * s + v * c) for u, v in stadium_pts_2d(L, Wd, seg_half=4)]
    cut(["plate"], lambda: prism_y("led_slot_cut", bar(8.2, 2.9), YP + 0.8, 4.0))
    assign(prism_y("led_slot_%d" % i, bar(8.2, 2.9), YP + 0.85, 0.1), M_HOLE)
    assign(prism_y("led_%d" % i, bar(7.3, 2.1), YP + 0.8, 0.55, chamfer=0.2, seg=2), M_5_GREEN)

# speaker grilles: diamond grids of round holes in dark pads either side of the lens
for sx, gx, gz in ((-1, -17.0, 27.1), (1, 17.4, 27.6)):
    pad_pts = rounded_poly([(gx - 3.9, gz + 5.3), (gx + 3.9, gz + 5.3), (gx + 3.9, gz - 5.3), (gx - 3.9, gz - 5.3)],
                           1.4, 3)
    cut(["plate"], lambda: prism_y("grille_cut", pad_pts, YP + 1.4, 3.0))
    assign(prism_y("grille_pad_%d" % (sx > 0), pad_pts, YP + 1.5, 0.12), M_BODY)
    bm = bmesh.new()
    for iz in range(-3, 4):
        for ix in range(-2, 3):
            if (ix + iz) % 2:
                continue
            hx, hz = gx + ix * 1.45, gz + iz * 1.45
            bmesh.ops.create_circle(bm, cap_ends=True, segments=10, radius=0.55 * MM,
                                    matrix=Matrix.Translation(v3(hx, YP + 1.37, hz))
                                    @ Matrix.Rotation(math.radians(90), 4, "X"))
    assign(finish(bm, "grille_holes_%d" % (sx > 0)), M_HOLE)

# ------------------------------------------------------------------------------------------------
# Event button: octagonal bezel, cushioned pad with the delta
# ------------------------------------------------------------------------------------------------
bx, bz = BTN


def octagon(hwid, top, bot, ch):
    return [(-hwid + ch, top), (hwid - ch, top), (hwid, top - ch), (hwid, bot + ch), (hwid - ch, bot),
            (-hwid + ch, bot), (-hwid, bot + ch), (-hwid, top - ch)]


boolean(plate, prism_y("btn_bezel_add", rounded_poly(octagon(*BTN_OUT, 7.0), 2.0, 4), YP + 0.3, 1.9, chamfer=1.2,
                       seg=2), op="UNION")
well = rounded_poly(octagon(17.0, 5.6, -27.9, 6.0), 1.6, 4)
cut(["plate"], lambda: prism_y("btn_well_cut", well, YP - 0.2, 4.0))
assign(prism_y("btn_well", well, YP - 0.1, 0.1), M_HOLE)
assign(prism_y("btn_pad", rounded_poly(octagon(*BTN_PAD, 5.6), 2.2, 4), YP - 0.1, 2.3, chamfer=1.8, seg=5), M_5_PAD)
lg = flat_logo("logo", delta_polys(7.0, bx, bz), 0.25, M_LOGO, chamfer=0.08)
lg.location = v3(0, YP - 2.35, 0)

# screws, microphones, wordmark
for i, (x, z) in enumerate(((-26.5, 38.8), (26.5, 38.8), (-26.5, -1.0), (26.5, -1.0), (-26.5, -40.2), (26.5, -40.2))):
    screw("screw_%d" % i, x, z, surface_at(x, z)[0].y / MM + 0.35)   # seated on the (possibly sloped) rail
front_mic("mic_1", -22.6, 4.4, 0.5)
front_mic("mic_2", 22.6, 4.4, 0.5)
front_text("axon_txt", "AXON", 0.0, -36.8, 11.6, M_TEXT, font=r"C:\Windows\Fonts\segoeuil.ttf")

# ------------------------------------------------------------------------------------------------
# sides, top, bottom, back
# ------------------------------------------------------------------------------------------------
# right side: ribbed grip panel
boolean(body, box("grip_cut", 3.0, 18.0, 62.0, (hw + 0.6, 0.5, -3.0), bevel=0.5, seg=2))
assign(box("grip_floor", 0.3, 17.6, 61.6, (hw - 0.85, 0.5, -3.0)), M_RUBBER)
for i in range(22):
    assign(box("grip_rib_%d" % i, 1.1, 16.4, 1.3, (hw - 0.45, 0.5, -32.0 + i * 2.75), bevel=0.35, seg=2), M_RUBBER)

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
