"""Zone Bodycam - builds the first Axon Body (TASER AXON body, 2013) item model in Blender.

Run inside Blender with __file__ set (export_variant.py does this):
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
Creates the scene "zbc_bodycam_1", every part its own single-material object, ready for export_variant.py.

Reference: TASER's near-orthographic front product photo (officer.com, 2013: 10.85 px per mm, features are
placed straight from its pixels with ph()), the labelled front / top / bottom views of the TASER AXON body
User Manual, and the 3/4 product photos. Size 66 x 82 x 20 mm (3.3 x 2.6 x 0.8 in, 3.5 oz).
Look: a slim black stippled body whose front is broken into angular plates by grooves running out from the
round Event button; the button carries the TASER bolt in an open ring inside raised collars (the battery LED
ring); the lens sits in a round housing at the upper left, the on/off switch hump on top at the right with its
red flag, the shield-shaped battery button right of the Event button.
Units are metres in Blender, millimetres below. Front faces -Y, Z is up, X is right as seen from the front.
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
CORNER_R = 5.0
FRONT_R = 2.4
BACK_BEVEL = 2.0
Y0 = -D / 2

LENS = ph(345, 185)
BTN = ph(385, 520)

M_1_RED = own_material("zbc_1_red", (0.85, 0.10, 0.04), 0.40)
M_1_RING = own_material("zbc_1_ring", (0.025, 0.035, 0.030), 0.20, spec=0.8)   # battery LED ring, unlit

# ------------------------------------------------------------------------------------------------
# shell: rounded slab
# ------------------------------------------------------------------------------------------------
outline = rounded_poly([(-hw, hh), (hw, hh), (hw, -hh), (-hw, -hh)], CORNER_R, 6)
body = prism_y("body", outline, D / 2, D)
bm = bmesh.new()
bm.from_mesh(body.data)
fe = [e for e in bm.edges if all(abs(v.co.y - Y0 * MM) < 1e-9 for v in e.verts)]
bmesh.ops.bevel(bm, geom=fe, offset=FRONT_R * MM, segments=4, profile=0.5, affect="EDGES", clamp_overlap=True)
be = [e for e in bm.edges if all(abs(v.co.y - (D / 2) * MM) < 1e-9 for v in e.verts)]
bmesh.ops.bevel(bm, geom=be, offset=BACK_BEVEL * MM, segments=3, profile=0.5, affect="EDGES", clamp_overlap=True)
bm.to_mesh(body.data)
bm.free()
assign(body, M_BODY)

# ------------------------------------------------------------------------------------------------
# front plates: the photo's angular grooves (dark) and plate edges (light), cut as grooves
# ------------------------------------------------------------------------------------------------
GROOVES = [   # (pixel polyline, width mm, depth mm)
    ([(20, 165), (240, 270), (292, 345)], 1.3, 0.8),            # upper left, deep
    ([(20, 266), (215, 330), (250, 380)], 0.7, 0.4),            # upper left plate edge
    ([(20, 503), (150, 548), (178, 610), (215, 690)], 0.7, 0.4),  # left plate edge down to the collar
    ([(20, 836), (130, 770), (240, 708)], 0.7, 0.4),            # lower left
    ([(140, 772), (310, 815), (372, 970)], 0.7, 0.4),           # bottom plate edge
    ([(475, 700), (525, 765), (760, 858)], 1.3, 0.8),           # lower right, deep
    ([(548, 322), (640, 288), (760, 246)], 0.7, 0.4),           # upper right plate edge
    ([(680, 518), (760, 525)], 0.7, 0.4),                       # right edge over the battery button
    ([(690, 640), (760, 704)], 0.7, 0.4),                       # right edge under the battery button
    ([(20, 160), (90, 130), (260, 125)], 0.6, 0.3),             # top left plate edge
]
for pl, w, dep in GROOVES:          # one straight cut per segment (a mitred multi-segment cut broke the boolean)
    q = phs(pl)
    for p0, p1 in zip(q, q[1:]):
        cut(["body"], lambda: prism_y("groove_cut", stroke([p0, p1], w), Y0 + dep, 8.0))
    for p_ in q[1:-1]:
        cut(["body"], lambda: disc("groove_joint", w / 2, p_[0], p_[1], Y0 + dep, Y0 - 8.0, seg=12))

# ------------------------------------------------------------------------------------------------
# lens housing: round, standing 2.6 mm proud, dark ring, big glass
# ------------------------------------------------------------------------------------------------
lx, lz = LENS
YL = Y0 - 2.6
boolean(body, disc("lens_housing", 7.9, lx, lz, Y0 + 1.0, YL, seg=96, chamfer=0.8, cseg=3), op="UNION")
cut(["body"], lambda: disc("lens_cut", 6.6, lx, lz, YL + 1.2, YL - 4.0, seg=96))
assign(lathe("lens_ring", lx, lz, [(6.6, 1.2), (6.6, 0.1), (6.2, -0.1), (5.4, -0.1), (4.9, 0.5), (4.9, 1.3)], YL,
             seg=96), M_GLOSS)
assign(disc("lens_seat", 4.9, lx, lz, YL + 1.5, YL + 1.2, seg=64), M_HOLE)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=36, v_segments=18, radius=4.6 * MM)
for v in bm.verts:
    v.co.y *= 1.6 / 4.6
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 1e-7], context="VERTS")
glass = assign(finish(bm, "lens_glass"), M_GLASS)
glass.location = v3(lx, YL + 1.2, lz)

# ------------------------------------------------------------------------------------------------
# top-right hump (on/off switch housing) with its red flag
# ------------------------------------------------------------------------------------------------
hump = phs([(385, 70), (500, 44), (622, 78), (572, 190), (452, 182), (420, 152)])
boolean(body, prism_y("hump", hump, Y0 + 1.0, 2.2, chamfer=0.6, seg=2), op="UNION")
boolean(body, hull("hump_top", [(x, y, z) for x, z in ((0.0, hh - 1.0), (20.5, hh - 1.0)) for y in (-8.0, 4.0)]
                   + [(x, y, hh + 2.0) for x in (4.0, 16.0) for y in (-7.0, 3.0)]), op="UNION")
flag = phs([(585, 175), (640, 90), (705, 80), (700, 112), (628, 190)])
assign(prism_y("flag", flag, Y0 + 0.6, 2.0, chamfer=0.3, seg=1), M_1_RED)
assign(hull("flag_top", [(x, y, z) for x, z in ((23.0, hh - 0.2), (29.5, hh - 0.2)) for y in (-9.5, -4.0)]
            + [(x, y, hh + 0.6) for x in (23.5, 29.0) for y in (-9.0, -4.5)]), M_1_RED)

# ------------------------------------------------------------------------------------------------
# Event button: wide raised collar, battery LED ring, second ring, cap with the open ring and the bolt
# ------------------------------------------------------------------------------------------------
bx, bz = BTN
YB_ = Y0 - 1.5
boolean(body, disc("btn_collar", 18.6, bx, bz, Y0 + 1.0, YB_, seg=160, chamfer=1.0, cseg=3), op="UNION")
cut(["body"], lambda: disc("btn_seat_cut", 16.2, bx, bz, YB_ + 1.2, YB_ - 4.0, seg=160))
assign(annulus("btn_led", bx, bz, 15.1, 16.2, YB_ + 1.18, YB_ + 0.7, seg=160), M_1_RING)
assign(lathe("btn_ring", bx, bz, [(15.1, 1.2), (15.1, 0.3), (14.6, -0.2), (13.4, -0.2), (13.0, 0.4), (13.0, 1.2)],
             YB_, seg=160), M_GLOSS)
assign(annulus("btn_gap", bx, bz, 12.4, 13.0, YB_ + 0.6, YB_ + 1.4, seg=160), M_HOLE)
assign(disc("btn_cap", 12.4, bx, bz, YB_ + 1.4, YB_ + 0.1, seg=160, chamfer=0.6, cseg=3), M_FACE)
YC = YB_ + 0.1
# the open ring: a C from r 7.4 to 9.7, open where the bolt crosses it
for i, (a0, a1) in enumerate(((70.0, 222.0), (250.0, 402.0))):
    assign(annulus("btn_c_%d" % i, bx, bz, 7.4, 9.7, YC - 0.5, YC + 0.1, a0=a0, a1=a1, seg=120), M_GLOSS)
bolt = phs([(400, 410), (440, 418), (392, 495), (425, 492), (345, 628), (368, 530), (340, 532)])
assign(prism_y("btn_bolt", bolt, YC + 0.1, 0.6, chamfer=0.15, seg=1), M_GLOSS)

# battery button: tilted shield with a recessed slot
shield = phs([(570, 522), (600, 506), (690, 518), (690, 618), (642, 690), (580, 672), (548, 640)])
boolean(body, prism_y("shield", shield, Y0 + 1.0, 2.0, chamfer=0.5, seg=2), op="UNION")
slot = phs([(605, 540), (660, 545), (650, 640), (620, 660), (595, 640)])
cut(["body"], lambda: prism_y("shield_slot_cut", rounded_poly(slot, 1.2, 3), Y0 - 0.3, 3.0))
assign(prism_y("shield_btn", rounded_poly(phs([(610, 548), (655, 552), (646, 634), (622, 652), (600, 636)]), 1.0, 3),
               Y0 - 0.2, 0.9, chamfer=0.3, seg=2), M_RUBBER)

# speaker and microphone
front_mic("speaker", *ph(492, 262), 0.6)
front_mic("mic", *ph(212, 862), 0.6)

# ------------------------------------------------------------------------------------------------
# top: operation LED and ETM socket at the left, on/off switch windows in the hump; bottom: pairing /
# volume button and the upload LED; back: holster rails and label
# ------------------------------------------------------------------------------------------------
assign(box("top_led", 2.4, 2.4, 0.6, (-26.0, -5.0, hh + 0.05), bevel=0.3, seg=2), M_1_RED)
assign(cyl_z("etm_ring", 2.6, -18.5, -1.0, hh - 0.4, hh + 0.35, seg=32, chamfer=0.2), M_BEZEL)
assign(cyl_z("etm_socket", 1.3, -18.5, -1.0, hh - 0.2, hh + 0.4, seg=24), M_HOLE)
for i, x in enumerate((7.0, 13.5)):
    assign(box("switch_window_%d" % i, 5.6, 6.6, 0.6, (x, -1.5, hh + 1.9), bevel=0.4, seg=2), M_HOLE)
assign(box("switch_slider", 4.6, 5.6, 1.0, (7.0, -1.5, hh + 2.1), bevel=0.4, seg=2), M_RUBBER)
hexb = [(16.0 + 5.5 * math.cos(math.radians(a)), 0.5 + 3.0 * math.sin(math.radians(a))) for a in range(0, 360, 60)]
assign(prism_z("pair_btn", hexb, -hh + 0.4, -1.4, chamfer=0.4, seg=2), M_RUBBER)
assign(box("upload_led", 2.4, 2.4, 0.6, (-14.0, -6.0, -hh - 0.05), bevel=0.3, seg=2), M_1_RED)

YBK = D / 2
for i, x in enumerate((-17.0, 17.0)):
    assign(box("rail_%d" % i, 3.0, 1.4, 44.0, (x, YBK + 0.4, 6.0), bevel=0.5, seg=2), M_MOUNT)
assign(box("label", 38.0, 0.3, 13.0, (0.0, YBK + 0.05, -27.0), bevel=0.6, seg=2), M_LABEL)
for i, (t, z, s) in enumerate((("TASER  AXON BODY", -24.4, 1.7), ("MODEL 73002", -27.4, 1.2),
                               ("TASER INTERNATIONAL", -30.0, 1.0))):
    tx = make_text_mesh("label_txt_%d" % i, t, s, 0.05, space=1.04, res_u=2)
    tx.rotation_euler = (math.radians(90), 0, math.radians(180))
    tx.location = v3(0, YBK + 0.22, z)
    assign(tx, M_BODY)

finish_shell(body, bevel=0.25)
meshes = smooth_all(flat=[body])
print("zbc_bodycam_1: %d parts" % len(meshes))
