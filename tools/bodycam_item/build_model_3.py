"""Zone Bodycam - builds the Axon Body 3 (AX1023, 2020) item model in Blender.

Run inside Blender with __file__ set (export_variant.py does this):
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
Creates the scene "zbc_bodycam_3", every part its own single-material object, ready for export_variant.py.

Reference: the front-view line drawing of the official Axon Body 3 User Manual (13.97 px per mm across),
its top and bottom views, and Axon's product renders (glamor and isolated shots). 66 x 93.2 x 28 mm: the
manual's drawing at one scale gives 93.2 mm high (some retailer sheets say 96.5).
Look: black octagonal body with six Torx screws in a stippled frame, a the frame sloping up to a smooth raised centre platform that swells
into a round boss around the Event button, the lens centred near the top with a seven-slot speaker grille to
its right, a knurled button ring with three red LED arcs (upper left, upper right, bottom) around a centre
disc carrying the Axon delta, AXON under the button; the control buttons down the left side, the status
display on top, USB-C underneath, RapidLock mount on the back.
Units are metres in Blender, millimetres below. Front faces -Y, Z is up, X is right as seen from the front.
"""
import math
import os
import bpy
import bmesh
from mathutils import Vector

SCENE = "zbc_bodycam_3"
COMMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "axon_common.py")
exec(compile(open(COMMON, encoding="utf-8").read(), COMMON, "exec"), globals())
setup_scene()
std_materials()

# ---- body (mm)
W, D = 66.0, 28.0
hw = W / 2
Z_TOP, Z_BOT = 46.6, -46.6
TOP_CUT = (20.3, 40.7)            # top corner cuts: (+-20.3, Z_TOP) -> (+-hw, 40.7)
BOT_CUT = (20.3, -40.9)
CORNER_R = 2.6
FRONT_R = 1.6
BACK_BEVEL = 2.6
Y0 = -D / 2                       # front of the frame

LENS = (0.0, 31.2)
GRILLE = (17.6, 30.7)
BTN = (0.0, -9.4)
BOSS_R = 24.9                     # round boss of the centre panel around the button
PANEL_X = 14.3                    # half width of the centre panel
PANEL_Z = (42.3, -43.0)

M_3_BUTTON = own_material("zbc_3_button", (0.044, 0.045, 0.049), 0.70)
knurl(M_3_BUTTON, BTN[0], BTN[1], 13.1, 19.3, 0.80,
      (0.039, 0.040, 0.044), (0.050, 0.051, 0.056), (0.010, 0.010, 0.012))
M_3_LCD = own_material("zbc_3_lcd", (0.010, 0.014, 0.012), 0.08, spec=1.0)
M_3_LCD_SEG = own_material("zbc_3_lcd_seg", (0.028, 0.038, 0.031), 0.14, spec=0.80)
M_3_YELLOW = own_material("zbc_3_yellow", (0.950, 0.630, 0.005), 0.38, spec=0.55)
M_3_RED = own_material("zbc_3_red", (0.85, 0.05, 0.04), 0.30, emission=(0.6, 0.02, 0.02))
M_LED = shared_material("zbc_led", (0.35, 0.03, 0.03), 0.20)

# ------------------------------------------------------------------------------------------------
# shell: octagonal block, flat front frame
# ------------------------------------------------------------------------------------------------
outline = [(-TOP_CUT[0], Z_TOP), (TOP_CUT[0], Z_TOP), (hw, TOP_CUT[1]), (hw, BOT_CUT[1]),
           (BOT_CUT[0], Z_BOT), (-BOT_CUT[0], Z_BOT), (-hw, BOT_CUT[1]), (-hw, TOP_CUT[1])]
body = prism_y("body", outline, D / 2, D)
bm = bmesh.new()
bm.from_mesh(body.data)
ye = [e for e in bm.edges if abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-9 and abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-9]
bmesh.ops.bevel(bm, geom=ye, offset=CORNER_R * MM, segments=8, profile=0.5, affect="EDGES", clamp_overlap=True)
fe = [e for e in bm.edges if all(abs(v.co.y - Y0 * MM) < 1e-9 for v in e.verts)]
bmesh.ops.bevel(bm, geom=fe, offset=FRONT_R * MM, segments=3, profile=0.5, affect="EDGES", clamp_overlap=True)
be = [e for e in bm.edges if all(abs(v.co.y - (D / 2) * MM) < 1e-9 for v in e.verts)]
bmesh.ops.bevel(bm, geom=be, offset=BACK_BEVEL * MM, segments=4, profile=0.5, affect="EDGES", clamp_overlap=True)
bm.to_mesh(body.data)
bm.free()
assign(body, M_BODY)

# ------------------------------------------------------------------------------------------------
# centre platform: the stippled frame slopes gently UP from the outer edge to a raised flat platform (the
# centre panel); the platform swells into a round boss around the button (user-confirmed: no step, a ramp)
# ------------------------------------------------------------------------------------------------
H_PLAT = 1.6                      # platform height above the frame's outer edge
YP = Y0 - H_PLAT
ramp = hull("ramp", [(sx * (hw + 1.0), Y0 + 0.01, sz * (Z_TOP + 1.0)) for sx in (-1, 1) for sz in (-1, 1)]
            + [(sx * PANEL_X, YP, z) for sx in (-1, 1) for z in PANEL_Z]
            + [(sx * (hw + 1.0), Y0 + 1.0, sz * (Z_TOP + 1.0)) for sx in (-1, 1) for sz in (-1, 1)])
clip = prism_y("ramp_clip", outline, D / 2, D + 4.0)
boolean(ramp, clip, op="INTERSECT")
boolean(body, ramp, op="UNION")
strip = rounded_poly([(-PANEL_X, PANEL_Z[0]), (PANEL_X, PANEL_Z[0]), (PANEL_X, PANEL_Z[1]), (-PANEL_X, PANEL_Z[1])],
                     3.0, 6)
panel = prism_y("panel", strip, YP + 0.3, 0.4, chamfer=0.08)   # smooth platform skin, 0.1 mm proud (no z-fighting)
boolean(panel, disc("boss", BOSS_R, BTN[0], BTN[1], Y0 + 0.4, YP - 0.1, seg=160, chamfer=0.6, cseg=2), op="UNION")
assign(panel, M_FACE)

# ------------------------------------------------------------------------------------------------
# lens: its bezel sits sunk in a pocket of the panel, bezel top flush with the panel, dark glass
# ------------------------------------------------------------------------------------------------
lx, lz = LENS
YPL = YP
cut(["panel", "body"], lambda: disc("lens_pocket_cut", 9.4, lx, lz, YPL + 0.7, YPL - 5.0, seg=120))
assign(annulus("lens_gap", lx, lz, 8.9, 9.4, YPL + 0.68, YPL + 0.9, seg=120), M_HOLE)
assign(lathe("lens_bezel", lx, lz, [(8.9, 0.7), (8.9, -0.6), (8.3, -0.8), (7.0, -0.8), (6.4, -0.2), (5.0, 0.2),
                                     (5.0, 0.9)], YPL, seg=120), M_BEZEL)
assign(disc("lens_seat", 5.0, lx, lz, YPL + 1.0, YPL + 0.7, seg=96), M_HOLE)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=36, v_segments=18, radius=4.6 * MM)
for v in bm.verts:
    v.co.y *= 0.95 / 4.6
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 1e-7], context="VERTS")
glass = assign(finish(bm, "lens_glass"), M_GLASS)
glass.location = v3(lx, YPL + 0.7, lz)

# speaker grille: seven horizontal slots cut into the stippled frame right of the panel
gx, gz = GRILLE
for i in range(7):
    z = gz + (3 - i) * 1.75
    sl = [(gx + x, z + q) for x, q in stadium_pts_2d(4.8, 0.9, seg_half=6)]
    cut(["body"], lambda: prism_y("grille_cut", sl, Y0 + 0.9, 3.0))
    assign(prism_y("grille_%d" % i, [(gx + x, z + q) for x, q in stadium_pts_2d(4.7, 0.8, seg_half=6)],
                   Y0 + 1.0, 0.1), M_HOLE)

# ------------------------------------------------------------------------------------------------
# Event button: groove, smooth collar, knurled dish with three red LED arcs, centre disc with the delta
# ------------------------------------------------------------------------------------------------
bx, bz = BTN
cut(["panel", "body"], lambda: disc("btn_seat_cut", 24.0, bx, bz, YP + 1.4, YP - 6.0, seg=160))
assign(annulus("btn_groove", bx, bz, 23.4, 24.0, YP + 1.38, YP + 1.6, seg=160), M_HOLE)
DISH0, DISH1 = 0.9, 0.0           # dish slope, mm behind the panel face, from r 19.3 in to r 13.1
assign(lathe("btn_collar", bx, bz, [(23.4, 1.4), (23.4, 0.05), (22.8, -0.2), (20.2, -0.1), (19.3, DISH0)],
             YP, seg=160), M_GLOSS)
assign(funnel("btn_dish", bx, bz, 19.3, YP + DISH0, 13.1, YP + DISH1, seg=160), M_3_BUTTON)
assign(disc("btn_disc", 13.1, bx, bz, YP + DISH1 + 0.6, YP + DISH1 - 0.02, seg=120), M_DISC)


def dish_y(r):
    return YP + DISH0 - (DISH0 - DISH1) * (19.3 - r) / (19.3 - 13.1) - 0.03


for tag, a0, a1 in (("ur", 22.0, 50.0), ("ul", 130.0, 158.0), ("bot", 256.0, 284.0)):
    assign(funnel("led_arc_" + tag, bx, bz, 17.9, dish_y(17.9), 16.7, dish_y(16.7), seg=160, a0=a0, a1=a1,
                  thick=0.14), M_3_RED)
lg = flat_logo("logo", delta_polys(9.0, bx, bz - 0.4), 0.55, M_LOGO, chamfer=0.15)
lg.location = v3(0, YP + DISH1 - 0.02, 0)

# ------------------------------------------------------------------------------------------------
# screws in the frame, microphones, wordmark
# ------------------------------------------------------------------------------------------------
for i, (x, z) in enumerate(((-27.5, 37.4), (27.5, 37.4), (-29.3, 0.0), (29.3, 0.0), (-27.5, -37.4), (27.5, -37.4))):
    screw("screw_%d" % i, x, z, surface_at(x, z)[0].y / MM + 0.35)   # seated on the sloped frame
front_mic("mic_1", -16.2, 11.4, 0.62)
front_mic("mic_2", 0.0, -39.0, 0.62)
front_text("axon_txt", "AXON", 0.0, -34.4, 16.1, M_TEXT, font=r"C:\Windows\Fonts\segoeuil.ttf")

# bottom cavities, cut before the parts underneath are added
usbc_cut_pts = [(x, -2.0 + y) for x, y in stadium_pts_2d(9.2, 3.4, seg_half=8)]
cut(["body"], lambda: prism_z("usbc_pocket_cut", usbc_cut_pts, Z_BOT + 2.3, -4.0))
for s_ in (-1, 1):
    cut(["body"], lambda: box("dock_pocket_cut", 4.2, 3.6, 2.8, (s_ * 14.5, -2.0, Z_BOT), bevel=0.45, seg=2))

# ------------------------------------------------------------------------------------------------
# 6. Top Deck (+Z = Z_TOP): Op LED (-19.5) + Monochrome LCD (-1.5) + Stadium Power Button (+17.2)
# ------------------------------------------------------------------------------------------------

def cyl_z(name, r, cx, cy, z0, z1, seg=32, chamfer=0.0, r_top=None):
    """Cylinder/frustum along Z from z0 to z1."""
    bm = bmesh.new()
    pts = [(r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    f = bm.faces.new([bm.verts.new(v3(cx + x, cy + y, z0)) for x, y in pts])
    bm.normal_update()
    if (z1 > z0 and f.normal.z < 0) or (z1 < z0 and f.normal.z > 0):
        f.normal_flip()
    rr = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [g for g in rr["geom"] if isinstance(g, bmesh.types.BMVert)]
    s = 1.0 if r_top is None else r_top / r
    c = v3(cx, cy, 0)
    for v in top:
        v.co.z = z1 * MM
        v.co.x = c.x + (v.co.x - c.x) * s
        v.co.y = c.y + (v.co.y - c.y) * s
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if chamfer > 0:
        fe = [e for e in bm.edges if all(abs(v.co.z - z1 * MM) < 1e-8 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=fe, offset=chamfer * MM, segments=2, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return finish(bm, name)


# 6A. Operation LED (Left: X = -19.5, Y = -3.5, Z = Z_TOP) inside r = 1.8 mm bevelled cup
assign(cyl_z("top_led_cup", 1.85, -19.5, -3.5, Z_TOP - 0.5, Z_TOP + 0.18, seg=28, chamfer=0.14), M_RUBBER)
assign(cyl_z("top_led_well", 1.35, -19.5, -3.5, Z_TOP - 0.3, Z_TOP + 0.21, seg=24), M_HOLE)
assign(cyl_z("top_led", 1.15, -19.5, -3.5, Z_TOP - 0.2, Z_TOP + 0.42, seg=24, chamfer=0.28), M_LED)

# 6B. Monochrome LCD Window & Rubber Surround (Center: X = -1.5, Y = -3.5, Z = Z_TOP)
# Rubber surround: 25.0 W x 15.0 D x 1.6 mm proud (Z = +49.6), recessed well down to Z = +49.15
lcd_bezel = assign(
    box("top_lcd_bezel", 25.0, 15.0, 2.4, (-1.5, -3.5, Z_TOP + 0.4), bevel=0.9, seg=3),
    M_RUBBER,
)
boolean(lcd_bezel, box("lcd_well_cut", 19.7, 10.2, 1.4, (-1.5, -3.5, Z_TOP + 1.65), bevel=0.5, seg=2))
assign(box("top_lcd_seam", 19.7, 10.2, 0.3, (-1.5, -3.5, Z_TOP + 1.05), bevel=0.4, seg=2), M_HOLE)
assign(box("top_lcd_window", 19.5, 10.0, 0.8, (-1.5, -3.5, Z_TOP + 0.80), bevel=0.45, seg=2), M_3_LCD)

# Subtle transflective monochrome LCD status readout (battery outline + 3 bars + status strip at Z = +49.22)
assign(box("lcd_bat_body", 4.6, 2.4, 0.06, (4.8, -1.6, Z_TOP + 1.21), bevel=0.02, seg=1), M_3_LCD_SEG)
assign(box("lcd_bat_nub", 0.6, 1.1, 0.06, (7.3, -1.6, Z_TOP + 1.21), bevel=0.01, seg=1), M_3_LCD_SEG)
for k, x_seg in enumerate((-7.8, -5.0, -2.2)):
    assign(box("lcd_stat_seg_%d" % k, 2.0, 0.9, 0.06, (x_seg, -5.2, Z_TOP + 1.21), bevel=0.01, seg=1), M_3_LCD_SEG)

# 6C. Top-Right Stadium Power Button (X = +16.2, Y = -3.5, Z = Z_TOP): 8.8 W x 6.2 D x 1.1 proud + power bar
pwr_seam_pts = [(16.2 + x, -3.5 + y) for x, y in stadium_pts_2d(9.5, 6.9, seg_half=10)]
assign(prism_z("top_pwr_seam", pwr_seam_pts, Z_TOP - 1.2, 1.38, chamfer=0.12, seg=1), M_HOLE)

pwr_btn_pts = [(16.2 + x, -3.5 + y) for x, y in stadium_pts_2d(8.8, 6.2, seg_half=12)]
assign(prism_z("top_pwr_btn", pwr_btn_pts, Z_TOP - 1.2, 2.30, chamfer=0.55, seg=3), M_RUBBER)

pwr_bar_pts = [(16.2 + x, -3.5 + y) for x, y in stadium_pts_2d(0.7, 3.4, seg_half=6)]
assign(prism_z("top_pwr_bar", pwr_bar_pts, Z_TOP + 0.95, 0.50, chamfer=0.18, seg=2), M_RUBBER)


_side_before = {o.name for o in sc.objects}
# ------------------------------------------------------------------------------------------------
# 7. Control strip (built on +X, mirrored to the left side below): 4-Button Overmolded TPE Control Strip (Vol+, Select, Vol-, Program)
# ------------------------------------------------------------------------------------------------

# Single overmolded TPE strip base (1.3 mm proud to +34.3, 16.0 mm Y centered at -0.5, Z = -23.5..+31.0)
strip_r_pts = [(-0.5 + y, 3.75 + z) for y, z in stadium_pts_2d(16.0, 54.5, seg_half=12)]
assign(prism_x("right_tpe_strip", strip_r_pts, hw - 0.8, 2.10, chamfer=0.55, seg=2), M_RUBBER)


def right_pad(name, z0, z1, proud_mm):
    zc = (z0 + z1) / 2.0
    zh = z0 - z1
    # Rounded tactical button pad on +X
    b = box(name, proud_mm + 0.8, 13.4, zh, (hw + (proud_mm - 0.8) / 2.0, -0.5, zc), bevel=0.85, seg=3)
    return assign(b, M_RUBBER), hw + proud_mm, zc


# 1) Volume Up (Z = +28.5..+17.5, 2.3 mm proud) + raised upward triangle (3.6 mm wide)
_, xf_vu, zc_vu = right_pad("btn_vol_up", 28.5, 17.5, 2.3)
tri_up = [(-0.5 - 1.8, zc_vu - 1.35), (-0.5 + 1.8, zc_vu - 1.35), (-0.5, zc_vu + 1.65)]
assign(prism_x("mark_vol_up", tri_up, xf_vu - 0.15, 0.60, chamfer=0.14, seg=2), M_RUBBER)

# 2) Select (Z = +16.5..+6.5, 2.1 mm proud) + concave center dimple & tactile ring (r = 2.0 mm)
pad_sel, xf_sel, zc_sel = right_pad("btn_select", 16.5, 6.5, 2.1)
# Carve subtle concave dimple + add raised locator ring around it
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1.65 * MM)
for v in bm.verts:
    v.co.x *= 0.35
dimple_cut = finish(bm, "sel_dimple_cut")
dimple_cut.location = v3(xf_sel + 0.15, -0.5, zc_sel)
boolean(pad_sel, dimple_cut, op="DIFFERENCE")

# Tactile locator ring on +X face (oriented with axis along +X)
sel_ring = assign(annulus("mark_select_ring", 0.0, zc_sel, 1.55, 2.15, 0.0, 0.50, seg=36, chamfer_front=0.15), M_RUBBER)
sel_ring.rotation_euler = (0, 0, math.radians(-90))
sel_ring.location = v3(xf_sel + 0.35, -0.5, 0.0)

# 3) Volume Down (Z = +5.5..-5.5, 2.3 mm proud) + raised downward triangle (3.6 mm wide)
_, xf_vd, zc_vd = right_pad("btn_vol_down", 5.5, -5.5, 2.3)
tri_dn = [(-0.5 + 1.8, zc_vd + 1.35), (-0.5 - 1.8, zc_vd + 1.35), (-0.5, zc_vd - 1.65)]
assign(prism_x("mark_vol_down", tri_dn, xf_vd - 0.15, 0.60, chamfer=0.14, seg=2), M_RUBBER)

# 4) Program Button (Z = -9.5..-19.5, 1.9 mm proud, separated by 4.0 mm tactile gap) + tactile pip (r = 1.1 mm)
_, xf_pr, zc_pr = right_pad("btn_program", -9.5, -19.5, 1.9)
pip_pts = [(-0.5 + 1.1 * math.cos(2 * math.pi * i / 24), zc_pr + 1.1 * math.sin(2 * math.pi * i / 24)) for i in range(24)]
assign(prism_x("mark_program_pip", pip_pts, xf_pr - 0.15, 0.60, chamfer=0.22, seg=2), M_RUBBER)


# ------------------------------------------------------------------------------------------------
# 8. The right side is smooth in the glamor render (no ribs): only the seam where the front and back shells
#    meet, a shallow groove all the way down each side
# ------------------------------------------------------------------------------------------------
for s_ in (-1, 1):
    boolean(body, box("seam_cut", 1.2, 0.6, Z_TOP - Z_BOT, (s_ * hw, 2.0, (Z_TOP + Z_BOT) / 2)))


def mirror_x(o):
    """Bake the object's transform into its mesh and mirror it across X = 0."""
    from mathutils import Matrix
    o.data.transform(Matrix.Scale(-1, 4, (1, 0, 0)) @ o.matrix_world)
    o.matrix_world = Matrix()
    o.data.flip_normals()
    o.data.update()


# the manual's front view has the control buttons on the left edge (items 2-5): the strip above was laid out
# on the right, so mirror it
for o in [o for o in sc.objects if o.name not in _side_before]:
    mirror_x(o)

# ------------------------------------------------------------------------------------------------
# 9. Bottom View (-Z = Z_BOT): USB-C + 2 Axon Dock Pockets + 4th Mic + Drainage Slots
# ------------------------------------------------------------------------------------------------

# Weather-sealed rubberized USB-C surround (15.0 W x 7.2 D) with hollow center
usbc_bezel = assign(box("bottom_usbc_bezel", 15.0, 7.2, 1.2, (0.0, -2.0, Z_BOT + 0.25), bevel=0.55, seg=2), M_RUBBER)
boolean(usbc_bezel, prism_z("usbc_bezel_hole", usbc_cut_pts, Z_BOT + 1.2, -2.5))

# Dark port liner + metallic USB-C inner shell + center tongue (6.6 x 0.7 mm)
usbc_liner_pts = [(x, -2.0 + y) for x, y in stadium_pts_2d(9.0, 3.2, seg_half=8)]
assign(prism_z("bottom_usbc_well", usbc_liner_pts, Z_BOT + 2.25, -0.35), M_HOLE)

usbc_shell = assign(prism_z("bottom_usbc_shell", usbc_liner_pts, Z_BOT + 2.0, -1.85), M_BEZEL)
usbc_inner_pts = [(x, -2.0 + y) for x, y in stadium_pts_2d(8.3, 2.5, seg_half=8)]
boolean(usbc_shell, prism_z("usbc_shell_hollow", usbc_inner_pts, Z_BOT + 2.2, -2.5))

assign(box("bottom_usbc_tongue", 6.6, 0.7, 1.6, (0.0, -2.0, Z_BOT + 1.15), bevel=0.15, seg=1), M_SCREW)

# 2 Rectangular Axon Dock Mechanical Alignment Pocket liners (+-14.5, -2.0, Z_BOT)
for i, s_ in enumerate((-1, 1)):
    assign(box("bottom_dock_liner_%d" % i, 4.05, 3.45, 0.35, (s_ * 14.5, -2.0, Z_BOT + 1.35), bevel=0.35, seg=1), M_HOLE)
    dock_rim = assign(box("bottom_dock_rim_%d" % i, 5.2, 4.6, 0.5, (s_ * 14.5, -2.0, Z_BOT + 0.18), bevel=0.30, seg=1), M_MOUNT)
    boolean(dock_rim, box("dock_rim_cut", 4.2, 3.6, 1.6, (s_ * 14.5, -2.0, Z_BOT), bevel=0.35, seg=1))

# 4th Microphone pinhole (-9.8, -2.0, Z_BOT, r = 0.65 mm)
assign(cyl_z("bottom_mic_4", 0.65, -9.8, -2.0, Z_BOT + 0.40, Z_BOT - 0.03, seg=20), M_HOLE)

# Water drainage slots (+-20.5, +3.5, Z_BOT, 2.8 x 1.3 mm)
for i, s_ in enumerate((-1, 1)):
    dr_pts = [(s_ * 20.5 + x, 3.5 + y) for x, y in stadium_pts_2d(2.8, 1.3, seg_half=6)]
    assign(prism_z("bottom_drain_%d" % i, dr_pts, Z_BOT + 0.35, -0.38, chamfer=0.08, seg=1), M_HOLE)


# ------------------------------------------------------------------------------------------------
# 10. Back View (+Y = +14.0 mm): RapidLock, Dual Magnets, 5-Slot Vent, AX1023 Plate + Yellow Delta
# ------------------------------------------------------------------------------------------------

YB = D / 2.0  # +14.0 mm


def back_disc(name, r, x, z, h, mat, seg=48, chamfer=0.0):
    return assign(disc(name, r, x, z, YB - 0.30, YB + h, seg=seg, chamfer=chamfer, cseg=2), mat)


# RapidLock twist-lock receiver centered at (0.0, +2.0)
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

# Dual internal mount magnet bosses at (0.0, +28.0) and (0.0, -26.0)
for i, z_mag in enumerate((28.0, -26.0)):
    back_disc("magnet_%d" % i, 5.5, 0.0, z_mag, 0.15, M_MAGNET, seg=40, chamfer=0.12)

# Upper GORE-TEX pressure equalization vent: 5 vertical slots (1.0 W x 6.2 H, 3.2 mm pitch) at (0.0, +40.5)
for i in range(5):
    xv = (-2 + i) * 3.2
    v_pts = [(xv + x, 40.5 + z) for x, z in stadium_pts_2d(1.0, 6.2, seg_half=6)]
    assign(prism_y("back_vent_%d" % i, v_pts, YB - 0.25, -0.32, chamfer=0.06, seg=1), M_HOLE)

# Rear lower drainage pinholes
for i, s_ in enumerate((-1, 1)):
    back_disc("back_drain_%d" % i, 0.85, s_ * 20.5, -40.5, 0.04, M_HOLE, seg=14)

# Rear Regulatory / Serial Plate (26.0 W x 10.0 H at (0.0, -38.0)) + Small Yellow Axon Compliance Delta
assign(box("regulatory_plate", 26.0, 0.36, 10.0, (0.0, YB + 0.02, -38.0), bevel=0.55, seg=2), M_LABEL)

# Small Axon Tactical Yellow compliance delta mark on left of plate (X = -9.5, Z = -38.0)
ycx, ycz, yr = -9.5, -38.0, 2.2
ytri = [
    (ycx + yr * math.cos(math.radians(90 + 120 * i)), ycz + yr * math.sin(math.radians(90 + 120 * i)))
    for i in range(3)
]
y_delta = assign(prism_y("regulatory_yellow_delta", ytri, YB + 0.16, -0.10, chamfer=0.03, seg=1), M_3_YELLOW)
# Inner dark triangle cutout inside yellow delta so it reads as an authentic Axon delta outline
ytri_in = [
    (ycx + 0.95 * math.cos(math.radians(90 + 120 * i)), ycz + 0.95 * math.sin(math.radians(90 + 120 * i)))
    for i in range(3)
]
assign(prism_y("regulatory_delta_core", ytri_in, YB + 0.20, -0.08), M_BODY)

# Crisp laser-etched AXON BODY 3 / AX1023 text on regulatory plate
reg_t1 = make_text_mesh("reg_txt_1", "AXON BODY 3", 1.75, 0.05, space=1.04, res_u=2)
reg_t1.rotation_euler = (math.radians(90), 0, math.radians(180))
reg_t1.location = v3(2.2, YB + 0.25, -36.3)
assign(reg_t1, M_BODY)

reg_t2 = make_text_mesh("reg_txt_2", "MODEL AX1023  FCC X4GS00947", 1.05, 0.05, space=1.02, res_u=2)
reg_t2.rotation_euler = (math.radians(90), 0, math.radians(180))
reg_t2.location = v3(2.2, YB + 0.25, -39.5)
assign(reg_t2, M_BODY)


finish_shell(body)
finish_shell(panel, bevel=0.2)
meshes = smooth_all(flat=[body, panel])
print("zbc_bodycam_3: %d parts" % len(meshes))
