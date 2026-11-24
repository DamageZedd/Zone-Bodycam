"""Zone Bodycam - builds the Axon Body 2 (AX1001, 2016) item model in Blender.

Run inside Blender with __file__ set (export_variant.py does this):
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
Creates the scene "zbc_bodycam_2", every part its own single-material object, ready for export_variant.py.

Reference: the front-view line drawing of the official Axon Body 2 User Guide (12.35 px per mm) and Axon's
product photo on its cover, cross-checked with two in-use photos. Spec sheet: 70 x 87 x 24 mm (25.8 mm at
the lens), 142 g. Look: a shallow hip-roof front whose four hip ridges form the big X, the lens in a round
pod at the top-left corner, a large Event button with the three-blade swirl and a green status ring, the
battery-status window above the AXON wordmark, diamond-knurled grips down both sides, the power slider
hump on top with its red on/off flag at the top-right corner.
Units are metres in Blender, millimetres below. Front faces -Y, Z is up, X is right as seen from the front.
"""
import math
import os
import bpy
import bmesh
from mathutils import Vector

SCENE = "zbc_bodycam_2"
COMMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "axon_common.py")
exec(compile(open(COMMON, encoding="utf-8").read(), COMMON, "exec"), globals())
setup_scene()
std_materials()

# ---- body (mm): width 70, top 40.5 (the slider hump reaches 43), bottom -42.4, 24 deep
W = 70.0
hw = W / 2
Z_TOP, Z_BOT = 40.5, -42.4
Y_BACK = 12.0                    # back face
Y_PLAT = -12.0                   # front plateau (24 mm body)
H_MAX = 3.8                      # plateau height above the zero lines of the roof planes
Y0 = Y_PLAT + H_MAX              # roof base level (h = 0)
XA, ZA_T, ZA_B = 36.5, 43.5, -44.0   # zero lines of the four roof planes (just outside the outline)
KX, KZ = 0.312, 0.253            # roof slopes; KX / KZ = 1.23 is the hip-ridge angle measured on the drawing
CORNER_R = 3.2
FRONT_R = 2.0
BACK_BEVEL = 2.2

LENS = (-25.3, 30.9)             # lens pod centre
POD_R = 9.9
BTN = (0.0, 0.0)                 # Event button centre
BTN_R = 23.0

M_GREEN = own_material("zbc_2_green", (0.06, 0.62, 0.16), 0.30, emission=(0.03, 0.40, 0.09))
M_RED = own_material("zbc_2_red", (0.80, 0.07, 0.05), 0.40)
M_WINDOW = own_material("zbc_2_window", (0.11, 0.12, 0.13), 0.12, spec=0.9)

# ------------------------------------------------------------------------------------------------
# shell: the hip-roof front is convex (the space under a minimum of planes), so it is the hull of the
# zero-line rectangle, the plateau rectangle and the back; then cut to the silhouette
# ------------------------------------------------------------------------------------------------
px, pzt, pzb = XA - H_MAX / KX, ZA_T - H_MAX / KZ, ZA_B + H_MAX / KZ
pts = []
for sx in (-1, 1):
    pts += [(sx * XA, Y0, ZA_T), (sx * XA, Y0, ZA_B), (sx * px, Y_PLAT, pzt), (sx * px, Y_PLAT, pzb),
            (sx * XA, Y_BACK + 1.0, ZA_T), (sx * XA, Y_BACK + 1.0, ZA_B)]   # past the back: the cutter makes that face
body = assign(hull("body", pts), M_BODY)

# the top-left corner is the lens pod itself: the outline follows the pod's circle there
outline = ([(LENS[0] + POD_R * math.cos(math.radians(a)), LENS[1] + POD_R * math.sin(math.radians(a)))
            for a in range(180, 89, -10)]
           + [(29.6, Z_TOP), (hw, 34.6), (hw, -37.6), (31.4, Z_BOT), (-31.4, Z_BOT), (-hw, -37.6)])


def outline_cutter(name):
    o = prism_y(name, outline, Y_BACK, 30.0)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    ye = [e for e in bm.edges if abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-9
          and abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-9
          and math.hypot(e.verts[0].co.x / MM - LENS[0], e.verts[0].co.z / MM - LENS[1]) > POD_R + 0.5]
    bmesh.ops.bevel(bm, geom=ye, offset=CORNER_R * MM, segments=8, profile=0.5, affect="EDGES", clamp_overlap=True)
    be = [e for e in bm.edges if all(abs(v.co.y - Y_BACK * MM) < 1e-9 for v in e.verts)]
    bmesh.ops.bevel(bm, geom=be, offset=BACK_BEVEL * MM, segments=4, profile=0.5, affect="EDGES", clamp_overlap=True)
    bm.to_mesh(o.data)
    bm.free()
    return o


boolean(body, outline_cutter("outline_cut"), op="INTERSECT")
# top chamfer: the front face ends at z 37.7, a sloped band runs back to the top (drawing's inner top line)
boolean(body, hull("top_chamfer_cut", [(x, y, z) for x in (-40, 40) for y, z in ((-12.6, 37.3), (-5.6, 41.0),
                                                                                 (-5.6, 50.0), (-20, 50.0), (-20, 33.0))]))

# lens pod: a round boss at the top-left corner, standing 1.8 mm proud of the plateau (25.8 mm at the lens)
lx, lz = LENS
Y_POD = Y_PLAT - 1.8
boolean(body, disc("pod", POD_R, lx, lz, Y0 + 2.0, Y_POD, seg=96, chamfer=1.0, cseg=3), op="UNION")
# top humps: the power slider housing (right) and the sync block (left of centre)
boolean(body, hull("hump", [(x, y, z) for x, z in ((4.7, Z_TOP - 1.0), (22.7, Z_TOP - 1.0), (8.0, 43.0),
                                                    (19.2, 43.0)) for y in (-8.0, 5.0)]), op="UNION")
boolean(body, box("sync_block", 11.6, 10.0, 5.2, (-9.3, -1.0, Z_TOP), bevel=2.4, seg=5), op="UNION")

# round the front perimeter
bm = bmesh.new()
bm.from_mesh(body.data)
bm.normal_update()
fe = []
for e in bm.edges:
    if len(e.link_faces) != 2:
        continue
    n1, n2 = (f.normal for f in e.link_faces)
    if (n1.y < -0.3 and abs(n2.y) < 0.2) or (n2.y < -0.3 and abs(n1.y) < 0.2):
        fe.append(e)
bmesh.ops.bevel(bm, geom=fe, offset=FRONT_R * MM, segments=3, profile=0.5, affect="EDGES", clamp_overlap=True)
bm.to_mesh(body.data)
bm.free()

# side grip bands: 0.9 mm deep recess down each side, filled with diamond knurl teeth
GRIP = {-1: (19.5, -28.3), 1: (16.0, -28.3)}
for s in (-1, 1):
    zt, zb = GRIP[s]
    boolean(body, box("grip_cut", 4.0, 16.0, zt - zb, (s * (hw + 1.1), -1.5, (zt + zb) / 2), bevel=0.4, seg=2))
    assign(box("grip_floor_%d" % (s > 0), 0.3, 15.6, zt - zb - 0.4, (s * (hw - 1.0), -1.5, (zt + zb) / 2)),
           M_RUBBER)
    knurl_patch("grip_%s" % ("l" if s < 0 else "r"), "x", s * (hw - 0.9), (-9.3, 6.3), (zb + 0.6, zt - 0.6),
                1.25, 0.85, M_RUBBER, sign=s)

# ------------------------------------------------------------------------------------------------
# lens: chamfered pod face, dark gap, bezel, black barrel and a big dark glass dome
# ------------------------------------------------------------------------------------------------
cut(["body"], lambda: disc("lens_well_cut", 8.0, lx, lz, Y_POD + 1.4, Y_POD - 5.0, seg=96))
assign(annulus("lens_gap", lx, lz, 7.4, 8.0, Y_POD + 1.38, Y_POD + 1.60, seg=96), M_HOLE)
assign(lathe("lens_bezel", lx, lz, [(7.4, 1.4), (7.4, 0.25), (7.0, 0.05), (6.6, 0.05), (6.3, 0.45), (6.3, 1.2)],
             Y_POD, seg=96), M_BEZEL)
assign(disc("lens_barrel", 6.3, lx, lz, Y_POD + 1.6, Y_POD + 1.15, seg=72), M_HOLE)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=6.0 * MM)
for v in bm.verts:
    v.co.y *= 1.5 / 6.0
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 1e-7], context="VERTS")
glass = assign(finish(bm, "lens_glass"), M_GLASS)
glass.location = v3(lx, Y_POD + 1.15, lz)
assign(annulus("lens_inner", lx, lz, 1.0, 2.4, Y_POD + 0.15, Y_POD + 0.6, seg=48), M_BEZEL)
assign(disc("lens_pupil", 1.0, lx, lz, Y_POD + 0.6, Y_POD + 0.1, seg=32), M_GLASS)

# ------------------------------------------------------------------------------------------------
# Event button: proud bezel ring, green status ring, matte face with the raised three-blade swirl
# ------------------------------------------------------------------------------------------------
bx, bz = BTN
cut(["body"], lambda: disc("btn_seat_cut", BTN_R + 0.3, bx, bz, Y_PLAT + 1.2, Y_PLAT - 6.0, seg=160))
assign(annulus("btn_gap", bx, bz, BTN_R - 0.1, BTN_R + 0.3, Y_PLAT + 1.18, Y_PLAT + 1.4, seg=160), M_HOLE)
assign(lathe("btn_bezel", bx, bz, [(BTN_R, 1.2), (BTN_R, -0.15), (BTN_R - 0.5, -0.45), (21.6, -0.45),
                                    (21.3, -0.1), (21.3, 0.8)], Y_PLAT, seg=160), M_GLOSS)
assign(annulus("btn_ring", bx, bz, 19.9, 21.3, Y_PLAT + 0.25, Y_PLAT + 0.9, seg=160), M_GREEN)
Y_FACE = Y_PLAT + 0.05
assign(disc("btn_face", 19.9, bx, bz, Y_PLAT + 1.0, Y_FACE, seg=160, chamfer=0.5, cseg=3), M_FACE)


# the three blades, traced on the drawing as smooth quadratic curves from their shared joint
SWIRL = [((1.0, -1.0), (-8.6, 3.4), (-3.4, 15.6)),     # top blade: bows out to the left, tip at the top
         ((1.0, -1.0), (12.4, 5.4), (17.2, -8.4)),     # right blade: arcs over to the right, tip down-right
         ((1.0, -1.0), (-2.6, -11.6), (-12.2, -13.8))]  # lower blade: drops, then sweeps out to the left

arms = [prism_y("swirl_%d" % i, stroke(bezier(*pts, n=14), 3.0), Y_FACE + 0.1, 0.55, chamfer=0.18, seg=2)
        for i, pts in enumerate(SWIRL)]
for a in arms[1:]:
    boolean(arms[0], a, op="UNION")
arms[0].name = "swirl"
assign(arms[0], M_GLOSS)
assign(disc("swirl_hub", 1.5, 1.0, -1.0, Y_FACE + 0.1, Y_FACE - 0.55, seg=32, chamfer=0.18), M_GLOSS)

# ------------------------------------------------------------------------------------------------
# battery-status window (raised hood over a light window) and the AXON wordmark on the bottom facet
# ------------------------------------------------------------------------------------------------
hood_base = [(-8.8, -26.4), (8.8, -26.4), (11.4, -31.6), (-11.4, -31.6)]
boolean(body, hull("hood", [(x, Y_PLAT + 2.2, z) for x, z in hood_base]
                   + [(x * 0.92, Y_PLAT - 0.9, z - 0.1 * (z + 28.7)) for x, z in hood_base]), op="UNION")
cut(["body"], lambda: prism_y("window_cut", [(-6.6, -27.4), (6.6, -27.4), (8.4, -30.6), (-8.4, -30.6)],
                              Y_PLAT + 0.4, 4.0))
assign(prism_y("window", [(-6.5, -27.5), (6.5, -27.5), (8.3, -30.5), (-8.3, -30.5)], Y_PLAT + 0.6, 0.55,
               chamfer=0.12), M_WINDOW)
for i, z in enumerate((-28.2, -29.4)):
    assign(box("window_slat_%d" % i, 9.0 + 2.5 * i, 0.3, 0.45, (0, Y_PLAT + 0.0, z), bevel=0.1, seg=1), M_LIGHTPIPE)

front_text("axon_txt", "AXON", 2.6, -37.5, 16.9, M_TEXT, font=r"C:\Windows\Fonts\segoeuil.ttf")
place_on_front(flat_logo("axon_delta", delta_polys(3.4), 0.10, M_TEXT), -9.3, -37.6, 0.02)

# microphones (dual-channel, left side of the face)
front_mic("mic_1", -25.3, 7.4, 0.6)
front_mic("mic_2", -17.2, -28.7, 0.6)

# ------------------------------------------------------------------------------------------------
# top: power slider in its hump with the red on/off flag, sync block, two indicator windows
# ------------------------------------------------------------------------------------------------
assign(box("slider_slot", 9.0, 4.4, 1.0, (13.8, -1.5, 42.8), bevel=0.4, seg=2), M_HOLE)
assign(box("slider", 5.0, 3.8, 1.6, (11.6, -1.5, 43.2), bevel=0.5, seg=3), M_RUBBER)
for k in range(4):
    assign(box("slider_rib_%d" % k, 0.35, 3.6, 0.3, (10.1 + k * 1.0, -1.5, 44.0), bevel=0.1, seg=1), M_RUBBER)
assign(hull("flag", [(x, y, z) for x, z in ((21.8, 42.8), (29.2, 41.2), (29.2, 39.9), (21.6, 41.5))
                     for y in (-9.6, -4.6)]), M_RED)
for i, (x, mat) in enumerate(((-3.6, M_LIGHTPIPE), (-1.2, M_RED))):
    assign(box("top_led_%d" % i, 1.2, 2.6, 0.5, (x, -2.0, Z_TOP + 0.1), bevel=0.25, seg=2), mat)
assign(cyl_z("sync_ring", 2.6, -9.3, -1.0, Z_TOP + 2.45, Z_TOP + 2.8, seg=32, chamfer=0.2), M_BEZEL)
assign(cyl_z("sync_port", 1.6, -9.3, -1.0, Z_TOP + 2.65, Z_TOP + 2.9, seg=24), M_HOLE)

# right side: Function button near the top
assign(box("function_seam", 1.2, 10.0, 9.0, (hw - 0.3, -2.5, 24.5), bevel=0.6, seg=2), M_HOLE)
assign(box("function_btn", 2.2, 9.0, 8.0, (hw + 0.4, -2.5, 24.5), bevel=0.8, seg=3), M_RUBBER)

# bottom: dock window with contacts
assign(box("dock_window", 16.0, 4.6, 0.4, (0, 2.0, Z_BOT + 0.05), bevel=0.3, seg=2), M_HOLE)
for i, x in enumerate((-6.0, -2.0, 2.0, 6.0)):
    assign(box("dock_pin_%d" % i, 1.6, 2.4, 0.4, (x, 2.0, Z_BOT - 0.05), bevel=0.15, seg=1), M_SCREW)

# ------------------------------------------------------------------------------------------------
# back: square holster plate with a round boss and four screws, regulatory label
# ------------------------------------------------------------------------------------------------
YB = Y_BACK
assign(box("mount_plate", 30.0, 1.6, 30.0, (0, YB + 0.5, 6.0), bevel=0.8, seg=3), M_MOUNT)
assign(disc("mount_boss", 7.0, 0, 6.0, YB + 1.0, YB + 2.6, seg=48, chamfer=0.4, cseg=2), M_MOUNT)
assign(disc("mount_boss_hole", 2.6, 0, 6.0, YB + 2.0, YB + 2.65, seg=32), M_HOLE)
for i, (x, z) in enumerate(((-11.5, 17.5), (11.5, 17.5), (-11.5, -5.5), (11.5, -5.5))):
    assign(disc("mount_screw_%d" % i, 1.3, x, z, YB + 1.0, YB + 1.45, seg=20, chamfer=0.25, cseg=1), M_SCREW)
assign(box("label", 40.0, 0.3, 11.0, (0, YB + 0.05, -30.0), bevel=0.6, seg=2), M_LABEL)
for i, (t, z, s) in enumerate((("AXON BODY 2", -27.6, 1.8), ("MODEL AX1001  FCC X4GS00947", -30.6, 1.0),
                               ("AXON ENTERPRISE, INC.", -32.9, 1.0))):
    tx = make_text_mesh("label_txt_%d" % i, t, s, 0.05, space=1.04, res_u=2)
    tx.rotation_euler = (math.radians(90), 0, math.radians(180))
    tx.location = v3(0, YB + 0.22, z)
    assign(tx, M_BODY)

finish_shell(body)
meshes = smooth_all(flat=[body])
print("zbc_bodycam_2: %d parts" % len(meshes))
