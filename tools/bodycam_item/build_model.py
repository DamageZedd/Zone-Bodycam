"""Zone Bodycam - builds the bodycam item model in Blender: a 1:1 Axon Body 4.

Run inside Blender (Scripting tab, or exec(open(path).read())). Creates the scene "zbc_bodycam" with
every part as its own object (materials included), ready for bake_export.py.

Proportions and feature positions were measured on Axon's orthographic front product render
(axon_2023_axonbody4-product-2, 15.65 px per mm) and checked against a 3/4 product photo:
64.5 x 95.3 mm front, 30 mm body + front relief + rear mount. Units are metres in Blender, millimetres below.
Front faces -Y, Z is up, X is right as seen from the front.
"""
import math
import bpy
import bmesh
from mathutils import Vector, Matrix

SCENE = "zbc_bodycam"
MM = 0.001

sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
bpy.context.window.scene = sc
for o in list(sc.objects):
    bpy.data.objects.remove(o, do_unlink=True)
col = sc.collection

# ---- body dimensions (mm), measured on Axon's orthographic front render
W, D = 64.5, 30.0
Z_TOP, Z_BOT = 47.1, -48.2    # body top and bottom
TOP_CUT = (21.7, 40.6)        # top corner cuts: (+-21.7, Z_TOP) -> (+-W/2, 40.6)
BOT_CUT = (23.0, -40.5)       # bottom corner cuts: (+-23.0, Z_BOT) -> (+-W/2, -40.5)
CORNER_R = 3.0                # rounding of the cut corners
FRONT_R = 1.4                 # rounding of the front edge
Y0 = -D / 2                   # front reference level (the side bevels reach it at |x| 25.5)
EMBED = 0.3                   # relief parts start this far inside the shell

# ---- front relief (approved reference sheet): h(x, z) = min(P(z), bevel(|x|)), mm in front of Y0.
# Each side bevel is ONE plane from the bump tops (|x| 6.75, H_BUMP) down to 0 at |x| 25.5; the three
# bumps T, M, Bo are flat-top pyramids whose sides are those bevels; the lens area and the button area
# sit on the same level, flush with the bevels at the lens area's sides.
H_BUMP = 4.5
X_IN, X_OUT = 6.75, 25.5


def bevel_h(ax):
    return H_BUMP * (X_OUT - ax) / (X_OUT - X_IN)


H_FLOOR = bevel_h(15.4)       # lens area and button area (2.42)
TOP_K, CHIN_K = H_BUMP / 6.2, H_BUMP / 13.8   # top edge slope (36 deg), chin under Bo (18 deg)

LENS = (0.0, 28.0)            # lens centre (X, Z)
BTN = (0.0, -12.0)            # button centre

# ------------------------------------------------------------------------------------------------
# helpers (all inputs in mm)
# ------------------------------------------------------------------------------------------------

def v3(x, y, z):
    return Vector((x * MM, y * MM, z * MM))


def link(name, me):
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    return o


def finish(bm, name):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(name, me)


def prism(name, pts, y_back, depth, chamfer=0.0, seg=1, back_chamfer=0.0, back_seg=2):
    """Extrude an XZ outline from y_back towards -Y by depth; chamfer the front (and back) rim."""
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new(v3(x, y_back, z)) for x, z in pts])
    bm.normal_update()
    if f.normal.y > 0:
        f.normal_flip()
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]:
        v.co.y -= depth * MM
    yf = (y_back - depth) * MM
    if chamfer > 0:
        fe = [e for e in bm.edges if all(abs(v.co.y - yf) < 1e-9 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=fe, offset=chamfer * MM, segments=seg, profile=0.5, affect="EDGES", clamp_overlap=True)
    if back_chamfer > 0:
        be = [e for e in bm.edges if all(abs(v.co.y - y_back * MM) < 1e-9 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=be, offset=back_chamfer * MM, segments=back_seg, profile=0.5, affect="EDGES", clamp_overlap=True)
    return finish(bm, name)


def slab(name, pts, y_back=Y0 + EMBED):
    """Solid whose front face has a height per vertex: pts = [(x, z, h)], front at Y0 - h."""
    bm = bmesh.new()
    back = [bm.verts.new(v3(x, y_back, z)) for x, z, h in pts]
    front = [bm.verts.new(v3(x, Y0 - h, z)) for x, z, h in pts]
    n = len(pts)
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([back[i], back[j], front[j], front[i]])
    return finish(bm, name)


def inset_convex(pts, t):
    """Offset a convex XZ polygon inwards by t (mm, or one value per edge i = pts[i] -> pts[i+1])."""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    sgn = 1.0 if area > 0 else -1.0
    lines = []
    for i in range(n):
        (x0, z0), (x1, z1) = pts[i], pts[(i + 1) % n]
        dx, dz = x1 - x0, z1 - z0
        ln = math.hypot(dx, dz)
        nx, nz = -dz / ln * sgn, dx / ln * sgn          # inward normal
        ti = t[i] if isinstance(t, (list, tuple)) else t
        lines.append(((x0 + nx * ti, z0 + nz * ti), (dx, dz)))
    out = []
    for i in range(n):
        (p, d), (q, e) = lines[i - 1], lines[i]
        den = d[0] * e[1] - d[1] * e[0]
        if abs(den) < 1e-12:
            out.append(q)
            continue
        k = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
        out.append((p[0] + d[0] * k, p[1] + d[1] * k))
    return out


def block(name, pts, h, taper, chamfer=0.25):
    """Raised plateau with sloped sides: base outline on the front plane, top inset by taper."""
    top = inset_convex(pts, taper)
    bm = bmesh.new()
    back = [bm.verts.new(v3(x, Y0 + EMBED, z)) for x, z in pts]
    base = [bm.verts.new(v3(x, Y0, z)) for x, z in pts]
    front = [bm.verts.new(v3(x, Y0 - h, z)) for x, z in top]
    n = len(pts)
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([back[i], back[j], base[j], base[i]])
        bm.faces.new([base[i], base[j], front[j], front[i]])
    bm.normal_update()
    if chamfer > 0:
        fe = [e for e in bm.edges if all(abs(v.co.y - (Y0 - h) * MM) < 1e-9 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=fe, offset=chamfer * MM, segments=2, profile=0.5, affect="EDGES", clamp_overlap=True)
    return finish(bm, name)


def ring_profile(r, seg, ridges=0, depth=0.0):
    pts = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        rr = r - (depth if (ridges and i % 2) else 0.0)
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    return pts


def disc(name, r, cx, cz, y_back, y_front, seg=64, chamfer=0.0, cseg=1, ridges=False, ridge_depth=0.0, r_front=None):
    """Cylinder along Y from y_back to y_front (y_front < y_back), optional ridged outline."""
    bm = bmesh.new()
    pts = ring_profile(r, seg, ridges, ridge_depth)
    f = bm.faces.new([bm.verts.new(v3(cx + x, y_back, cz + z)) for x, z in pts])
    bm.normal_update()
    if f.normal.y > 0:
        f.normal_flip()
    rr = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [g for g in rr["geom"] if isinstance(g, bmesh.types.BMVert)]
    s = 1.0 if r_front is None else r_front / r
    c = v3(cx, 0, cz)
    for v in top:
        v.co.y = y_front * MM
        v.co.x = c.x + (v.co.x - c.x) * s
        v.co.z = c.z + (v.co.z - c.z) * s
    if chamfer > 0:
        fe = [e for e in bm.edges if all(abs(v.co.y - y_front * MM) < 1e-9 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=fe, offset=chamfer * MM, segments=cseg, profile=0.5, affect="EDGES", clamp_overlap=True)
    return finish(bm, name)


def annulus(name, cx, cz, r0, r1, y, a0=0.0, a1=360.0, seg=64, thick=0.05):
    """Thin flat ring (or ring sector, degrees counter-clockwise from +X) facing -Y at depth y."""
    bm = bmesh.new()
    full = abs(a1 - a0) >= 360.0
    n = seg if full else max(2, int(seg * abs(a1 - a0) / 360.0))
    rows = []
    for yy in (y, y + thick):
        inner, outer = [], []
        for i in range(n if full else n + 1):
            a = math.radians(a0 + (a1 - a0) * i / n)
            inner.append(bm.verts.new(v3(cx + r0 * math.cos(a), yy, cz + r0 * math.sin(a))))
            outer.append(bm.verts.new(v3(cx + r1 * math.cos(a), yy, cz + r1 * math.sin(a))))
        rows.append((inner, outer))
    (fi, fo), (bi, bo) = rows
    m = len(fi)
    rng = range(m) if full else range(m - 1)
    for i in rng:
        j = (i + 1) % m
        bm.faces.new([fi[i], fo[i], fo[j], fi[j]])
        bm.faces.new([bi[j], bo[j], bo[i], bi[i]])
        bm.faces.new([fo[i], bo[i], bo[j], fo[j]])
        bm.faces.new([fi[j], bi[j], bi[i], fi[i]])
    if not full:
        bm.faces.new([fi[0], bi[0], bo[0], fo[0]])
        bm.faces.new([fo[-1], bo[-1], bi[-1], fi[-1]])
    return finish(bm, name)


def box(name, sx, sy, sz, loc, bevel=0.0, seg=2, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts:
        v.co = Vector((v.co.x * sx * MM, v.co.y * sy * MM, v.co.z * sz * MM))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel * MM, segments=seg, profile=0.5, affect="EDGES", clamp_overlap=True)
    o = finish(bm, name)
    o.location = v3(*loc)
    o.rotation_euler = rot
    return o


def boolean(target, cutter, op="DIFFERENCE"):
    bpy.context.view_layer.update()
    m = target.modifiers.new("b", "BOOLEAN")
    m.object = cutter
    m.operation = op
    m.solver = "EXACT"
    with bpy.context.temp_override(object=target, active_object=target):
        bpy.ops.object.modifier_apply(modifier="b")
    bpy.data.objects.remove(cutter, do_unlink=True)
    # the cut faces arrive with the cutter's (empty) material slot: give them the target's material
    for p in target.data.polygons:
        p.material_index = 0
    while len(target.data.materials) > 1:
        target.data.materials.pop()


def mirror_x(pts):
    """Close a left-half outline (top to bottom, x <= 0) into a symmetric polygon."""
    right = [(-x, z) for x, z in reversed(pts) if x != 0]
    return pts + right


def material(name, color, rough, metal=0.0, spec=0.5, emission=None):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = spec
    if emission:
        b.inputs["Emission Color"].default_value = (*emission, 1)
        b.inputs["Emission Strength"].default_value = 1.0
    nt.links.new(b.outputs[0], out.inputs[0])
    return m


def math_nodes(nt):
    N, L = nt.nodes, nt.links

    def op(kind, a=None, b_=None, va=None, vb=None):
        n = N.new("ShaderNodeMath")
        n.operation = kind
        if a is not None:
            L.new(a, n.inputs[0])
        elif va is not None:
            n.inputs[0].default_value = va
        if b_ is not None:
            L.new(b_, n.inputs[1])
        elif vb is not None:
            n.inputs[1].default_value = vb
        return n.outputs[0]
    return op


def surface_noise(m, scale=9000, strength=0.12):
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 2
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = strength
    bp.inputs["Distance"].default_value = 0.00005
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs[0], b.inputs["Normal"])


def knurl(m, cx, cz, r_in, r_out, cell, base_a, base_b, groove):
    """Triangle-grid knurl in an annulus (world XZ, mm), as colour and bump."""
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    op = math_nodes(nt)
    b = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    X = op("SUBTRACT", op("MULTIPLY", sep.outputs[0], vb=1 / MM), vb=cx)
    Z = op("SUBTRACT", op("MULTIPLY", sep.outputs[2], vb=1 / MM), vb=cz)
    x = op("MULTIPLY", X, vb=1 / cell)
    z = op("MULTIPLY", Z, vb=1 / cell)
    u = op("ADD", x, op("MULTIPLY", z, vb=1 / math.sqrt(3)))
    v = op("MULTIPLY", z, vb=2 / math.sqrt(3))
    fu, fv = op("FRACT", u), op("FRACT", v)
    fw = op("FRACT", op("ADD", fu, fv))

    def edge(f):
        return op("MINIMUM", f, op("SUBTRACT", None, f, va=1.0))

    d = op("MINIMUM", op("MINIMUM", edge(fu), edge(fv)), edge(fw))
    line = op("LESS_THAN", d, vb=0.08)
    r = op("SQRT", op("ADD", op("POWER", X, vb=2), op("POWER", Z, vb=2)))
    ring = op("MULTIPLY", op("GREATER_THAN", r, vb=r_in), op("LESS_THAN", r, vb=r_out))
    upper = op("GREATER_THAN", op("ADD", fu, fv), vb=1.0)
    gr = op("MULTIPLY", line, ring)
    tint = N.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    L.new(op("MULTIPLY", upper, ring), tint.inputs["Factor"])
    tint.inputs["A"].default_value = (*base_a, 1)
    tint.inputs["B"].default_value = (*base_b, 1)
    c = N.new("ShaderNodeMix")
    c.data_type = "RGBA"
    L.new(gr, c.inputs["Factor"])
    L.new(tint.outputs["Result"], c.inputs["A"])
    c.inputs["B"].default_value = (*groove, 1)
    L.new(c.outputs["Result"], b.inputs["Base Color"])
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.7
    bump.inputs["Distance"].default_value = 0.0002
    L.new(op("SUBTRACT", None, gr, va=1.0), bump.inputs["Height"])
    L.new(bump.outputs[0], b.inputs["Normal"])


def dots(m, axis_u, axis_v, pitch, r, base, dot):
    """Grid of small round bumps (side grip panels), axis_u/axis_v: 0=X 1=Y 2=Z."""
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    op = math_nodes(nt)
    b = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    u = op("MULTIPLY", sep.outputs[axis_u], vb=1 / (pitch * MM))
    v = op("MULTIPLY", sep.outputs[axis_v], vb=1 / (pitch * MM))
    du = op("SUBTRACT", op("FRACT", u), vb=0.5)
    dv = op("SUBTRACT", op("FRACT", v), vb=0.5)
    dist = op("SQRT", op("ADD", op("POWER", du, vb=2), op("POWER", dv, vb=2)))
    bumpv = op("LESS_THAN", dist, vb=r / pitch)
    c = N.new("ShaderNodeMix")
    c.data_type = "RGBA"
    L.new(bumpv, c.inputs["Factor"])
    c.inputs["A"].default_value = (*base, 1)
    c.inputs["B"].default_value = (*dot, 1)
    L.new(c.outputs["Result"], b.inputs["Base Color"])
    bp = N.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.6
    bp.inputs["Distance"].default_value = 0.0002
    L.new(bumpv, bp.inputs["Height"])
    L.new(bp.outputs[0], b.inputs["Normal"])


def assign(o, m):
    o.data.materials.clear()
    o.data.materials.append(m)
    return o


# ------------------------------------------------------------------------------------------------
# materials
# ------------------------------------------------------------------------------------------------

CHAR = (0.034, 0.035, 0.038)
M_BODY = material("zbc_body", CHAR, 0.62)
M_FACE = material("zbc_face", (0.038, 0.039, 0.042), 0.58)
M_RUBBER = material("zbc_rubber", (0.022, 0.022, 0.024), 0.75)
M_GLOSS = material("zbc_gloss", (0.020, 0.021, 0.023), 0.18)
M_BEZEL = material("zbc_bezel", (0.016, 0.016, 0.018), 0.45)
M_LENSFACE = material("zbc_lensface", (0.050, 0.051, 0.055), 0.40)
M_GLASS = material("zbc_glass", (0.004, 0.005, 0.008), 0.03, spec=1.0)
M_HOLE = material("zbc_hole", (0.002, 0.002, 0.002), 0.9)
M_SCREW = material("zbc_screw", (0.035, 0.035, 0.038), 0.40, metal=1.0)
M_TEXT = material("zbc_text", (0.72, 0.72, 0.72), 0.45)
M_LOGO = material("zbc_logo", (0.006, 0.006, 0.007), 0.30)
M_LIGHTPIPE = material("zbc_lightpipe", (0.62, 0.63, 0.65), 0.25)
M_BUTTON = material("zbc_button", (0.045, 0.046, 0.050), 0.70)
M_DISC = material("zbc_disc", (0.056, 0.057, 0.062), 0.50)
M_GRIP = material("zbc_grip", (0.020, 0.020, 0.022), 0.80)
M_MOUNT = material("zbc_mount", (0.018, 0.018, 0.020), 0.50)
M_TAB = material("zbc_tab", (0.085, 0.087, 0.092), 0.45)
M_DISPLAY = material("zbc_display", (0.006, 0.009, 0.016), 0.05, spec=1.0)
M_LABEL = material("zbc_label", (0.30, 0.30, 0.31), 0.6)
M_MAGNET = material("zbc_magnet", (0.05, 0.05, 0.055), 0.35, metal=1.0)
for m in (M_BODY, M_FACE, M_DISC, M_MOUNT):
    surface_noise(m)
knurl(M_BUTTON, BTN[0], BTN[1], 13.5, 18.85, 0.85, (0.040, 0.041, 0.045), (0.050, 0.051, 0.056), (0.010, 0.010, 0.011))
dots(M_GRIP, 1, 2, 1.35, 0.42, (0.016, 0.016, 0.018), (0.034, 0.034, 0.037))

# ------------------------------------------------------------------------------------------------
# shell
# ------------------------------------------------------------------------------------------------

hw = W / 2
outline = [(-TOP_CUT[0], Z_TOP), (TOP_CUT[0], Z_TOP), (hw, TOP_CUT[1]), (hw, BOT_CUT[1]),
           (BOT_CUT[0], Z_BOT), (-BOT_CUT[0], Z_BOT), (-hw, BOT_CUT[1]), (-hw, TOP_CUT[1])]
F, HB = H_FLOOR, H_BUMP
BF = bevel_h(22.1)                               # the roof's own level under the button area
# centre-line profile P(z), top to bottom (extended past the top and bottom edges)
PROF = [(Z_TOP + 3.0, HB - (Z_TOP + 3.0 - 44.4) * TOP_K), (44.4, HB), (40.75, HB), (35.0, F), (20.3, F),
        (14.4, HB), (10.75, HB), (4.4, BF), (-28.4, BF), (-34.25, HB), (-37.75, HB),
        (Z_BOT - 3.0, HB - (-37.75 - (Z_BOT - 3.0)) * CHIN_K)]


def Yh(h):
    """Y of a point h mm in front of the reference level."""
    return Y0 - h


def roof(name):
    """The whole front relief as one closed solid. Per band of P(z): a flat strip on the P plane
    between |x| = xc(z), and the two side bevel planes outside it (xc: where the bevel reaches P)."""
    xe = hw + 3.0
    he = bevel_h(xe)
    yb = D / 2 + 4.0
    bm = bmesh.new()
    rows = []
    for z, p in PROF:
        xc = X_OUT - p * (X_OUT - X_IN) / HB
        f = [bm.verts.new(v3(x, Yh(h), z)) for x, h in ((-xe, he), (-xc, p), (xc, p), (xe, he))]
        k = [bm.verts.new(v3(x, yb, z)) for x in (-xe, xe)]
        rows.append((f, k))
    for (f0, k0), (f1, k1) in zip(rows, rows[1:]):
        for i in range(3):
            bm.faces.new([f0[i], f0[i + 1], f1[i + 1], f1[i]])
        bm.faces.new([k0[0], k1[0], k1[1], k0[1]])
        bm.faces.new([f0[0], f1[0], k1[0], k0[0]])
        bm.faces.new([f0[3], k0[1], k1[1], f1[3]])
    f, k = rows[0]
    bm.faces.new([k[0], f[0], f[1], f[2], f[3], k[1]])
    f, k = rows[-1]
    bm.faces.new([k[1], f[3], f[2], f[1], f[0], k[0]])
    return finish(bm, name)


def outline_cutter(name):
    """Outline prism from the back face to well in front of the relief; cut corners and back rim rounded."""
    o = prism(name, outline, D / 2, D + 12.0)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    ye = [e for e in bm.edges if abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-9 and abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-9]
    bmesh.ops.bevel(bm, geom=ye, offset=CORNER_R * MM, segments=4, profile=0.5, affect="EDGES", clamp_overlap=True)
    be = [e for e in bm.edges if all(abs(v.co.y - D / 2 * MM) < 1e-9 for v in e.verts)]
    bmesh.ops.bevel(bm, geom=be, offset=3.0 * MM, segments=3, profile=0.5, affect="EDGES", clamp_overlap=True)
    bm.to_mesh(o.data)
    bm.free()
    return o


def hull(name, pts):
    bm = bmesh.new()
    for q in pts:
        bm.verts.new(v3(*q))
    bmesh.ops.convex_hull(bm, input=bm.verts[:])
    return finish(bm, name)


body = assign(roof("body"), M_BODY)
boolean(body, outline_cutter("outline_cut"), op="INTERSECT")

# round the front edge (between the front faces and the side walls)
bm = bmesh.new()
bm.from_mesh(body.data)
bm.normal_update()
fe = []
for e in bm.edges:
    if len(e.link_faces) != 2:
        continue
    n1, n2 = (fc.normal for fc in e.link_faces)
    if (n1.y < -0.3 and abs(n2.y) < 0.2) or (n2.y < -0.3 and abs(n1.y) < 0.2):
        fe.append(e)
bmesh.ops.bevel(bm, geom=fe, offset=FRONT_R * MM, segments=3, profile=0.5, affect="EDGES", clamp_overlap=True)
bm.to_mesh(body.data)
bm.free()


def plateau(name):
    """Button area on the lens level, with the band under M and the band over Bo (planes) leading up
    to the bump tops; short walls where it stands above the side bevels."""
    zt, zb, hb = 11.0, -34.5, HB - 0.02
    ring = [(-6.75, zt, hb), (6.75, zt, hb), (22.1, 4.4, F), (22.1, -28.4, F),
            (6.75, zb, hb), (-6.75, zb, hb), (-22.1, -28.4, F), (-22.1, 4.4, F)]
    bm = bmesh.new()
    fr = [bm.verts.new(v3(x, Yh(h), z)) for x, z, h in ring]
    bk = [bm.verts.new(v3(x, Yh(-1.0), z)) for x, z, h in ring]
    bm.faces.new([fr[0], fr[1], fr[2], fr[7]])
    bm.faces.new([fr[7], fr[2], fr[3], fr[6]])
    bm.faces.new([fr[6], fr[3], fr[4], fr[5]])
    bm.faces.new(list(reversed(bk)))
    for i in range(8):
        j = (i + 1) % 8
        bm.faces.new([fr[j], fr[i], bk[i], bk[j]])
    return finish(bm, name)


boolean(body, plateau("button_area"), op="UNION")

# recessed side channels for the middle screws, with a sloped triangle at each end
CH_FLOOR = -1.5
for s_ in (-1, 1):
    quad = [(25.5, 28.6), (30.35, 24.5), (30.35, -26.25), (25.5, -28.75)]   # outer wall just past the triangles'
    boolean(body, hull("channel_cut", [(s_ * x, Yh(h), z) for x, z in quad for h in (CH_FLOOR, 8.0)]))
    for tri in (((25.5, 28.6, 0.0), (30.25, 24.4, CH_FLOOR), (30.25, 31.25, bevel_h(30.25) - 0.02)),
                ((25.5, -28.75, 0.0), (30.25, -26.15, CH_FLOOR), (30.25, -32.0, bevel_h(30.25) - 0.02))):
        pts = [(s_ * x, Yh(h), z) for x, z, h in tri] + [(s_ * x, Yh(8.0), z) for x, z, h in tri]
        boolean(body, hull("channel_end_cut", pts))


def funnel(name, cx, cz, r_top, y_top, r_bot, y_bot, seg=128, a0=0.0, a1=360.0):
    """Ring surface from radius r_top at depth y_top to r_bot at y_bot (full ring or a sector), facing the viewer."""
    bm = bmesh.new()
    full = abs(a1 - a0) >= 360.0
    n = seg if full else max(2, int(seg * abs(a1 - a0) / 360.0))
    top, bot = [], []
    for i in range(n if full else n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        top.append(bm.verts.new(v3(cx + r_top * math.cos(a), y_top, cz + r_top * math.sin(a))))
        bot.append(bm.verts.new(v3(cx + r_bot * math.cos(a), y_bot, cz + r_bot * math.sin(a))))
    for i in range(len(top) if full else len(top) - 1):
        j = (i + 1) % len(top)
        bm.faces.new([top[i], bot[i], bot[j], top[j]])
    bm.normal_update()
    for f in bm.faces:
        if f.normal.y > 0:
            f.normal_flip()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(name, me)


def lathe(name, cx, cz, prof, y_ref, seg=96, ridged=()):
    """Revolve a profile [(radius, dy)] (dy < 0: towards the viewer) about the Y axis at (cx, cz)."""
    bm = bmesh.new()
    rings = []
    for k, (r, dy) in enumerate(prof):
        ring = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            rr = r - (0.22 if (k in ridged and i % 2) else 0.0)
            ring.append(bm.verts.new(v3(cx + rr * math.cos(a), y_ref + dy, cz + rr * math.sin(a))))
        rings.append(ring)
    for k in range(len(rings) - 1):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new([rings[k][i], rings[k + 1][i], rings[k + 1][j], rings[k][j]])
    bm.normal_update()
    for f in bm.faces:
        if f.normal.y > 0:
            f.normal_flip()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(name, me)


def cut(targets, make):
    for tname in targets:
        o = sc.objects.get(tname)
        if o:
            boolean(o, make())


lx, lz = LENS
bx, bz = BTN

# ------------------------------------------------------------------------------------------------
# lens: a bezel ring flush with the lens area in a round bore (the bore also cuts into the ramps),
# four dark notches, a black groove, the lens face and the glass a little deeper
# ------------------------------------------------------------------------------------------------

LG = F - 0.9                                     # floor of the gap around the bezel
cut(["body"], lambda: disc("lens_pocket_cut", 10.3, lx, lz, Yh(LG), Y0 - 12.0, seg=120))
cut(["body"], lambda: disc("lens_inner_cut", 7.3, lx, lz, Yh(F - 1.8), Y0 - 12.0, seg=96))
assign(annulus("lens_gap", lx, lz, 9.6, 10.3, Yh(LG) - 0.02, seg=120), M_HOLE)
assign(lathe("lens_ring", lx, lz, [(9.6, -LG), (9.6, -F), (8.4, -F), (7.1, -(F - 1.0)), (7.1, -(F - 1.6))], Y0, seg=120), M_BEZEL)
for a in (32, 148, 212, 328):
    r = math.radians(a)
    assign(box("lens_notch", 1.9, 1.2, 1.6, (lx + 8.45 * math.cos(r), Yh(F - 0.45), lz + 8.45 * math.sin(r)), rot=(0, -r, 0)), M_HOLE)
assign(annulus("lens_groove", lx, lz, 6.6, 7.1, Yh(F - 1.6) - 0.02), M_HOLE)
yl = Yh(F - 1.4)
assign(disc("lens_face", 6.6, lx, lz, yl + 0.4, yl, seg=96, chamfer=0.2, cseg=2), M_BEZEL)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=5.0 * MM)
for v in bm.verts:
    v.co.y *= 0.18
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 1e-7], context="VERTS")
glass = assign(finish(bm, "lens_glass"), M_GLASS)
glass.location = v3(lx, yl, lz)

# ------------------------------------------------------------------------------------------------
# button: rim flush with the button area (same level as the lens), dark gap around it, concave
# knurled face down to a smooth centre disc, raised logo, white light pipes and indicator dots
# ------------------------------------------------------------------------------------------------

BL = F                                           # rim level
DISH0, DISH1 = BL - 0.15, BL - 1.3               # concave face: outer and inner edge
cut(["body"], lambda: disc("button_seat_cut", 20.45, bx, bz, Yh(BL - 1.2), Y0 - 12.0, seg=128))
cut(["body"], lambda: disc("button_well_cut", 19.0, bx, bz, Yh(DISH1 - 0.4), Y0 - 12.0, seg=128))
assign(annulus("button_gap", bx, bz, 19.85, 20.45, Yh(BL - 1.2) - 0.02, seg=128), M_HOLE)
assign(lathe("button_rim", bx, bz, [(19.85, -(BL - 1.2)), (19.85, -BL), (19.35, -BL), (19.35, -(BL - 0.5)),
                                     (18.85, -(BL - 0.5)), (18.85, -DISH0)], Y0, seg=128), M_GLOSS)
assign(annulus("button_groove", bx, bz, 18.9, 19.3, Yh(BL - 0.5) - 0.02, seg=128), M_HOLE)
assign(funnel("button", bx, bz, 18.85, Yh(DISH0), 13.5, Yh(DISH1)), M_BUTTON)
ydisc = Yh(DISH1) - 0.01
assign(disc("button_disc", 13.5, bx, bz, ydisc + 0.3, ydisc, seg=96), M_DISC)


def dish_y(r):                                   # depth of the concave face at radius r
    return Yh(DISH0 - (DISH0 - DISH1) * (18.85 - r) / (18.85 - 13.5)) - 0.02


assign(funnel("lightpipe_top", bx, bz, 17.8, dish_y(17.8), 17.0, dish_y(17.0), seg=128, a0=76, a1=104), M_LIGHTPIPE)
assign(funnel("lightpipe_left", bx, bz, 17.8, dish_y(17.8), 17.0, dish_y(17.0), seg=128, a0=194, a1=226), M_LIGHTPIPE)
for i in range(7):                              # indicator dots on the right
    a = math.radians(314 + i * 32 / 6)
    yd = dish_y(17.3)
    assign(disc("dot_%d" % i, 0.42, bx + 17.3 * math.cos(a), bz + 17.3 * math.sin(a), yd + 0.1, yd - 0.04, seg=12), M_LIGHTPIPE)

# logo: Axon delta with a three-blade swirl (apex Z -3.0, base Z -16.35, 15.4 mm wide)
R = 8.9
lcx, lcz = bx, -11.9
tri = [(lcx + R * math.cos(math.radians(90 + 120 * i)), lcz + R * math.sin(math.radians(90 + 120 * i))) for i in range(3)]
r_in = R / 2                                    # inradius: edge midpoints


def polar(rad, deg):
    return (lcx + rad * math.cos(math.radians(deg)), lcz + rad * math.sin(math.radians(deg)))


def cut_curve(phi):
    """Swirl cut from the edge midpoint at angle phi into the centre (quadratic curve, 7 points)."""
    p0, p1, p2 = polar(r_in * 1.02, phi), polar(r_in * 0.6, phi + 42), (lcx, lcz)
    pts = []
    for i in range(7):
        t = i / 6
        pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                    (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
    return pts


for i in range(3):
    th = 90 + 120 * i
    a = cut_curve(th - 60)
    b = cut_curve(th + 60)
    poly = list(reversed(a)) + [polar(R, th)] + b[:-1]
    poly = [q for k, q in enumerate(poly) if k == 0 or (abs(q[0] - poly[k - 1][0]) + abs(q[1] - poly[k - 1][1])) > 1e-6]
    vx, vz = polar(R, th)
    poly = [(x + (vx - x) * 0.055, z + (vz - z) * 0.055) for x, z in poly]
    assign(prism("logo_%d" % i, poly, ydisc + 0.1, 0.7, chamfer=0.22), M_LOGO)

# ------------------------------------------------------------------------------------------------
# screws (Torx, in dark counterbores: top and bottom ones on the bevels, middle ones in the
# channels), holes, wordmark
# ------------------------------------------------------------------------------------------------

def screw(name, x, z, h_floor):
    yb = Yh(h_floor)
    cut(["body"], lambda: disc(name + "_bore_cut", 1.95, x, z, yb, Y0 - 12.0, seg=32))
    assign(annulus(name + "_bore", x, z, 1.45, 1.95, yb - 0.02, seg=32), M_HOLE)
    sc_ = disc(name, 1.45, x, z, yb + 0.2, yb - 0.55, seg=24, chamfer=0.3, cseg=2)
    for a in (0, 60, 120):
        boolean(sc_, box("torx", 1.5, 1.0, 0.42, (x, yb - 0.55, z), rot=(0, math.radians(a), 0)))
    assign(sc_, M_SCREW)


for i, (x, z) in enumerate([(-26.8, 36.9), (26.8, 36.9), (-26.8, 1.9), (26.8, 1.9), (-26.9, -38.4), (26.9, -38.4)]):
    h_floor = CH_FLOOR - 0.4 if abs(z - 1.9) < 0.01 else bevel_h(abs(x) + 1.95) - 0.4
    screw("screw_%d" % i, x, z, h_floor)


def surface_at(x, z):
    """Point and normal of the front surface at (x, z), found with a ray from in front of the camera."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, nor, _i, _o, _m = sc.ray_cast(dg, v3(x, Y0 - 30.0, z), Vector((0, 1, 0)))
    if not hit:
        return v3(x, Y0, z), Vector((0, -1, 0))
    return loc, nor


def facing(nor):
    return Vector((0, -1, 0)).rotation_difference(nor)


def hole(name, x, z, r):
    loc, nor = surface_at(x, z)
    o = assign(disc(name, r, 0, 0, 0.3, -0.04, seg=16), M_HOLE)
    o.location = loc
    o.rotation_euler = facing(nor).to_euler()


hole("hole_tl", -18.75, 36.4, 0.62)
hole("hole_tr", 18.75, 36.4, 0.62)
hole("hole_b0", 12.65, -36.3, 0.62)
hole("hole_b1", 15.85, -35.2, 0.62)
TXT_LOC, TXT_NOR = surface_at(0, -43.2)

cu = bpy.data.curves.new("axon_txt", "FONT")
cu.body = "AXON"
try:
    cu.font = bpy.data.fonts.load(r"C:\Windows\Fonts\GOTHIC.TTF", check_existing=True)
except RuntimeError:
    pass
cu.size = 4.4 * MM
cu.extrude = 0.08 * MM
cu.align_x = "CENTER"
cu.align_y = "CENTER"
cu.space_character = 1.08
txt = bpy.data.objects.new("axon_txt", cu)
col.objects.link(txt)
txt.rotation_euler = (math.radians(90), 0, 0)
txt.location = TXT_LOC
bpy.context.view_layer.update()
with bpy.context.temp_override(object=txt, active_object=txt, selected_objects=[txt], selected_editable_objects=[txt]):
    bpy.ops.object.convert(target="MESH")
txt = sc.objects["axon_txt"]
txt.rotation_euler = (facing(TXT_NOR) @ txt.rotation_euler.to_quaternion()).to_euler()   # lie on the chin slope
txt.location = TXT_LOC + TXT_NOR * (0.09 * MM)
w_now = txt.dimensions.x / MM
if w_now > 0:
    s = 12.3 / w_now
    txt.scale = (s, s, s)
assign(txt, M_TEXT)

# ------------------------------------------------------------------------------------------------
# sides, top, bottom, back
# ------------------------------------------------------------------------------------------------

# left side (second reference photo): a rubber strip of six chunky pads, top to bottom programmable 1
# and 2, volume up, select, volume down, power, each with a raised tactile mark
assign(box("side_strip_l", 1.4, 18.0, 82.0, (-hw - 0.3, 0.0, -0.5), bevel=0.6, seg=2), M_RUBBER)
SIDE_PADS = [(39.0, 27.6, "c1"), (27.0, 12.6, "c2"), (12.0, 4.6, ""), (4.0, -9.8, "bs"), (-10.4, -24.0, "lines"), (-24.6, -38.6, "fs")]
X_PAD = -hw - 1.0
for i, (z0, z1, icon) in enumerate(SIDE_PADS):
    zc = (z0 + z1) / 2
    assign(box("side_pad_%d" % i, 2.6, 16.5, z0 - z1, (X_PAD, 0.0, zc), bevel=1.0, seg=3), M_RUBBER)
    xf = X_PAD - 1.3                           # outer face of the pad
    marks = []
    if icon in ("c1", "c2"):                    # ")" marks: two short strokes forming a curve
        for dz in ((0.0,) if icon == "c1" else (2.3, -2.3)):
            marks += [(0.0, zc + dz + 0.7, 30), (0.0, zc + dz - 0.7, -30)]
    elif icon == "bs":
        marks = [(0.0, zc, 35)]
    elif icon == "fs":
        marks = [(0.0, zc, -35)]
    elif icon == "lines":
        for dz in (-1.6, 0.0, 1.6):
            marks.append((0.0, zc + dz, 90))
    for k, (y, z, ang) in enumerate(marks):
        length = 1.6 if icon in ("c1", "c2") else (4.0 if icon == "lines" else 4.2)
        assign(box("side_mark_%d_%d" % (i, k), 0.5, 0.7, length, (xf, y, z), bevel=0.2, seg=1,
                   rot=(math.radians(ang), 0, 0)), M_RUBBER)
# right side: POV connector port cover at lens height, dotted grip below
# right side (third reference photo): tall raised POV port cover at the top, dotted grip panel below
assign(box("pov_cover", 2.4, 9.5, 22.0, (hw + 0.5, -3.0, 28.0), bevel=1.0, seg=3), M_RUBBER)
assign(box("pov_seam", 0.4, 10.3, 22.8, (hw + 0.1, -3.0, 28.0), bevel=0.3, seg=1), M_HOLE)
assign(box("grip_right", 1.2, 20.0, 51.5, (hw + 0.2, 0.5, -14.25), bevel=0.5, seg=2), M_GRIP)
# top: status display in a rubber bezel, operation LED
assign(box("display_bezel", 28.0, 18.0, 2.2, (0.0, Y0 + 7.0, Z_TOP), bevel=1.0, seg=3), M_RUBBER)   # 1.1 mm proud of the top
assign(box("display", 22.0, 12.5, 2.2, (0.0, Y0 + 10.75, Z_TOP + 0.05), bevel=0.8, seg=3), M_DISPLAY)
led = assign(disc("led", 1.1, 0, 0, 0.0, -0.45, seg=20), material("zbc_led", (0.35, 0.03, 0.03), 0.2))
led.rotation_euler = (math.radians(-90), 0, 0)
led.location = v3(-24.0, -6.0, Z_TOP + 0.05)
# bottom: USB-C port in a rubber surround, drainage holes
assign(box("port_frame", 14.0, 6.5, 1.4, (0, -3.0, Z_BOT + 0.1), bevel=0.6, seg=2), M_RUBBER)
assign(box("port", 9.0, 3.2, 1.6, (0, -3.0, Z_BOT + 0.05), bevel=1.2, seg=3), M_HOLE)
assign(box("port_tongue", 6.6, 0.7, 1.7, (0, -3.0, Z_BOT + 0.05), bevel=0.2, seg=1), M_SCREW)
for i, x in enumerate((-16.0, 16.0)):
    assign(box("drain_bottom_%d" % i, 3.0, 1.4, 1.2, (x, 4.0, Z_BOT + 0.1), bevel=0.5, seg=2), M_HOLE)


def back_disc(name, r, x, z, h, mat, seg=48, chamfer=0.0):
    """Disc on the back face (normal +Y), standing h mm proud."""
    return assign(disc(name, r, x, z, D / 2 - 0.3, D / 2 + h, seg=seg, chamfer=chamfer, cseg=2), mat)


# back: RapidLock receiver, two mount magnets, vent, drainage holes, serial label
back_disc("rapidlock_rim", 12.5, 0, 2.0, 0.8, M_MOUNT, seg=64, chamfer=0.4)
back_disc("rapidlock_well", 10.6, 0, 2.0, 0.85, M_HOLE, seg=64)
back_disc("rapidlock_boss", 4.5, 0, 2.0, 1.2, M_MOUNT, seg=32, chamfer=0.3)
for i, a in enumerate((0, 180)):
    r = math.radians(a)
    assign(box("rapidlock_key_%d" % i, 3.0, 1.0, 2.0, (7.6 * math.cos(r), D / 2 + 0.9, 2.0 + 7.6 * math.sin(r)), bevel=0.3, seg=1), M_MOUNT)
for i, z in enumerate((28.0, -26.0)):
    back_disc("magnet_%d" % i, 5.5, 0, z, 0.15, M_MAGNET, seg=40, chamfer=0.2)
for i in range(6):
    assign(box("vent_%d" % i, 1.1, 0.8, 7.0, (-8.75 + i * 3.5, D / 2 + 0.05, 40.0), bevel=0.4, seg=2), M_HOLE)
for i, x in enumerate((-20.0, 20.0)):
    back_disc("drain_back_%d" % i, 0.9, x, -40.0, 0.05, M_HOLE, seg=12)
    back_disc("mic_back_%d" % i, 0.7, x, 38.0, 0.05, M_HOLE, seg=12)
assign(box("serial_label", 24.0, 0.3, 9.0, (0, D / 2 + 0.05, -38.0), bevel=0.8, seg=2), M_LABEL)

# the body: weld, flatten coplanar faces left by the cuts, then a small bevel on every hard edge so
# the facets of the front, the bumps and the rim catch light like a moulded part
bm = bmesh.new()
bm.from_mesh(body.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005 * MM)
bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts[:], edges=bm.edges[:])
bm.to_mesh(body.data)
bm.free()
bev = body.modifiers.new("edge_bevel", "BEVEL")
bev.limit_method = "ANGLE"
bev.angle_limit = math.radians(25)
bev.width = 0.35 * MM
bev.segments = 2
bev.profile = 0.6
bev.harden_normals = True
with bpy.context.temp_override(object=body, active_object=body):
    bpy.ops.object.modifier_apply(modifier="edge_bevel")

# shading: smooth with sharp edges above 30 degrees
meshes = [o for o in sc.objects if o.type == "MESH"]
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
with bpy.context.temp_override(selected_objects=meshes, selected_editable_objects=meshes,
                               active_object=meshes[0], object=meshes[0]):
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30))
# the body's facets meet at 13-20 degrees: keep them flat (smooth only the rounded edges)
with bpy.context.temp_override(selected_objects=[body], selected_editable_objects=[body], active_object=body, object=body):
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(8))
print("zbc_bodycam: %d parts" % len(meshes))
