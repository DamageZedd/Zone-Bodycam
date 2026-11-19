"""Zone Bodycam - builds the bodycam item model in Blender: a 1:1 Axon Body 4.

Run inside Blender (Scripting tab, or exec(open(path).read())). Creates the scene "zbc_bodycam" with
every part as its own object (materials included), ready for bake_export.py.

Proportions and feature positions were measured on Axon's orthographic front product render
(axon_2023_axonbody4-product-2, 15.65 px per mm) and checked against a 3/4 product photo:
64.5 x 96.5 mm front, 26 mm body + rear mount. Units are metres in Blender, millimetres below.
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

# ---- body dimensions (mm)
W, D = 64.5, 28.0
Z_TOP, Z_BOT = 47.0, -48.0    # body top and bottom (95 mm; the features are centred on Z = 0)
CUT_X, CUT_Z = 10.3, 7.7      # corner cuts of the outline
FRONT_CHAMFER = 3.4           # dark rim band around the front
Y0 = -D / 2                   # front plane
EMBED = 0.3                   # relief parts start this far inside the shell

# ---- front relief heights (mm in front of Y0)
H_SPINE = 1.6                 # central vertical spine and the chin
H_BLOCK = 4.0                 # lens block and button block
H_COLUMN = 3.0                # inner edge of the sloped side columns (just under the blocks)
LENS_TAPER = 1.0              # width of the lens block's sloped sides
X_COL_IN = 15.1 - LENS_TAPER * H_COLUMN / H_BLOCK   # columns end where the block side reaches their height

LENS = (0.0, 27.8)            # lens centre (X, Z)
BTN = (0.0, -11.2)            # button centre

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
    """Offset a convex XZ polygon inwards by t (mm): each edge moves in, corners re-intersect."""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    sgn = 1.0 if area > 0 else -1.0
    lines = []
    for i in range(n):
        (x0, z0), (x1, z1) = pts[i], pts[(i + 1) % n]
        dx, dz = x1 - x0, z1 - z0
        ln = math.hypot(dx, dz)
        nx, nz = -dz / ln * sgn, dx / ln * sgn          # inward normal
        lines.append(((x0 + nx * t, z0 + nz * t), (dx, dz)))
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
M_LIGHTPIPE = material("zbc_lightpipe", (0.42, 0.43, 0.45), 0.25)
M_BUTTON = material("zbc_button", (0.045, 0.046, 0.050), 0.70)
M_DISC = material("zbc_disc", (0.040, 0.041, 0.045), 0.55)
M_GRIP = material("zbc_grip", (0.020, 0.020, 0.022), 0.80)
M_MOUNT = material("zbc_mount", (0.018, 0.018, 0.020), 0.50)
for m in (M_BODY, M_FACE, M_DISC, M_MOUNT):
    surface_noise(m)
knurl(M_BUTTON, BTN[0], BTN[1], 13.3, 19.6, 1.0, (0.044, 0.045, 0.049), (0.060, 0.061, 0.066), (0.012, 0.012, 0.013))
dots(M_GRIP, 1, 2, 1.1, 0.33, (0.018, 0.018, 0.020), (0.032, 0.032, 0.035))

# ------------------------------------------------------------------------------------------------
# shell
# ------------------------------------------------------------------------------------------------

hw = W / 2
outline = [(-hw + CUT_X, Z_TOP), (hw - CUT_X, Z_TOP), (hw, Z_TOP - CUT_Z), (hw, Z_BOT + CUT_Z),
           (hw - CUT_X, Z_BOT), (-hw + CUT_X, Z_BOT), (-hw, Z_BOT + CUT_Z), (-hw, Z_TOP - CUT_Z)]
body = assign(prism("body", outline, D / 2, D, chamfer=FRONT_CHAMFER, seg=1, back_chamfer=3.0, back_seg=3), M_BODY)

# ------------------------------------------------------------------------------------------------
# front relief (measured outlines, mm)
# ------------------------------------------------------------------------------------------------

Z_END_T, Z_END_B = Z_TOP - FRONT_CHAMFER, Z_BOT + FRONT_CHAMFER   # the rim chamfer starts here
TOP_IN_T, TOP_IN_B = Z_END_T - H_SPINE, Z_END_B + H_SPINE         # the spine ramps down beyond these
X_FRAME = 25.8                           # outer flat frame (with the screws) ends here

# central spine, top to bottom, with the chin under the button block
spine = block("spine", [(-6.6, TOP_IN_T), (6.6, TOP_IN_T), (6.6, TOP_IN_B), (-6.6, TOP_IN_B)], H_SPINE, 0.4)
for nm, zi, ze in (("spine_ramp_top", TOP_IN_T, Z_END_T), ("spine_ramp_bottom", TOP_IN_B, Z_END_B)):
    assign(slab(nm, [(-6.2, zi, H_SPINE), (6.2, zi, H_SPINE), (6.6, ze, 0), (-6.6, ze, 0)]), M_FACE)
assign(spine, M_FACE)

# lens block: octagon whose lower corners run diagonally into the spine
lens_block = block("lens_block", mirror_x([(0, 36.4), (-13.5, 36.4), (-15.1, 34.8), (-15.1, 20.1), (-6.6, 14.4), (0, 14.4)]),
                   H_BLOCK, LENS_TAPER)
assign(lens_block, M_FACE)

# button block: square with cut top corners and a V-shaped skirt down into the chin
btn_block = block("button_block", mirror_x([(0, 6.9), (-18.3, 6.9), (-22.0, 3.9), (-22.0, -26.0), (-20.6, -28.2), (-6.6, -34.6), (0, -34.6)]),
                  H_BLOCK, 1.4)
assign(btn_block, M_FACE)

# sloped side columns and corner facets (front height varies linearly across X)
for s in (-1, 1):
    def P(x, z, h):
        return (s * x, z, h)

    def k(x, x0, x1, h1):        # linear height from h=0 at x0 to h1 at x1
        return h1 * (abs(x) - x0) / (x1 - x0)

    col_pts = [P(X_FRAME, 36.4, 0), P(X_COL_IN, 36.4, H_COLUMN), P(X_COL_IN, -28.2, H_COLUMN), P(X_FRAME, -28.2, 0)]
    top_pts = [P(X_FRAME, TOP_IN_T, 0), P(6.6, TOP_IN_T, H_SPINE), P(6.6, 36.4, H_SPINE), P(X_FRAME, 36.4, 0)]
    bot_pts = [P(X_FRAME, -28.2, 0), P(20.6, -28.2, k(20.6, X_FRAME, 6.6, H_SPINE)), P(6.6, -34.6, H_SPINE),
               P(6.6, TOP_IN_B, H_SPINE), P(X_FRAME, TOP_IN_B, 0)]
    if s > 0:
        col_pts, top_pts, bot_pts = col_pts[::-1], top_pts[::-1], bot_pts[::-1]
    # where the facets meet the rim chamfer, the step along the spine ramps down to the front plane
    for nm, zi, ze in (("top_end", TOP_IN_T, Z_END_T), ("bottom_end", TOP_IN_B, Z_END_B)):
        tri = [P(X_FRAME, zi, 0), P(6.6, zi, H_SPINE), P(6.6, ze, 0)]
        assign(slab("%s_%s" % (nm, "r" if s > 0 else "l"), tri), M_FACE)
    assign(slab("column_%s" % ("r" if s > 0 else "l"), col_pts), M_FACE)
    assign(slab("top_facet_%s" % ("r" if s > 0 else "l"), top_pts), M_FACE)
    assign(slab("bottom_facet_%s" % ("r" if s > 0 else "l"), bot_pts), M_FACE)

Y_BLOCK = Y0 - H_BLOCK

# ------------------------------------------------------------------------------------------------
# lens: knurled bezel, lugged ring, black groove, face, glass
# ------------------------------------------------------------------------------------------------

lx, lz = LENS
yb = Y_BLOCK - 3.6
assign(disc("lens_bezel", 10.2, lx, lz, Y_BLOCK + 0.3, yb, seg=120, chamfer=0.35, ridges=True, ridge_depth=0.22), M_BEZEL)
yl = yb - 0.5
lug = assign(disc("lens_lugring", 8.6, lx, lz, yb + 0.2, yl, seg=96, chamfer=0.35, cseg=2), M_LENSFACE)
for a in (45, 135, 225, 315):
    r = math.radians(a)
    cut = box("lug_cut", 2.2, 3.0, 1.1, (lx + 7.9 * math.cos(r), yl, lz + 7.9 * math.sin(r)), rot=(0, -r, 0))
    boolean(lug, cut)
assign(annulus("lens_groove", lx, lz, 6.75, 7.10, yl - 0.02), M_HOLE)
assign(disc("lens_face", 6.75, lx, lz, yl + 0.2, yl - 0.25, seg=96, chamfer=0.25, cseg=2), M_LENSFACE)
assign(disc("lens_step", 5.0, lx, lz, yl, yl - 0.75, seg=64, chamfer=0.3, cseg=2), M_BEZEL)
assign(annulus("lens_inner_ring", lx, lz, 3.6, 4.5, yl - 0.77), M_HOLE)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=3.7 * MM)
for v in bm.verts:
    v.co.y *= 0.42
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 1e-7], context="VERTS")
glass = assign(finish(bm, "lens_glass"), M_GLASS)
glass.location = v3(lx, yl - 0.7, lz)
glass.rotation_euler = (0, 0, 0)

# ------------------------------------------------------------------------------------------------
# button: glossy outer ring, groove, knurled face, smooth centre disc, logo, light pipes
# ------------------------------------------------------------------------------------------------

bx, bz = BTN
assign(disc("button_ring", 21.7, bx, bz, Y_BLOCK + 0.3, Y_BLOCK - 1.2, seg=128, chamfer=0.7, cseg=3), M_GLOSS)
assign(annulus("button_groove", bx, bz, 19.9, 20.5, Y_BLOCK - 1.22), M_HOLE)
yface = Y_BLOCK - 2.0
assign(disc("button", 19.9, bx, bz, Y_BLOCK - 0.5, yface, seg=128, chamfer=0.45, cseg=2), M_BUTTON)
ydisc = yface - 0.35
assign(disc("button_disc", 13.3, bx, bz, yface + 0.1, ydisc, seg=96, chamfer=0.3, cseg=2), M_DISC)
assign(annulus("lightpipe_top", bx, bz, 16.2, 17.1, yface - 0.03, 72, 110, seg=128), M_LIGHTPIPE)
assign(annulus("lightpipe_left", bx, bz, 16.2, 17.1, yface - 0.03, 203, 240, seg=128), M_LIGHTPIPE)
for i in range(9):                              # speaker/indicator ticks on the right
    a = 302 + i * 3.9
    assign(annulus("tick_%d" % i, bx, bz, 16.0, 18.4, yface - 0.03, a, a + 1.4, seg=360), M_HOLE)

# logo: Axon delta with a three-blade swirl
ylogo = ydisc - 0.45
R = 15.0 / math.sqrt(3)                         # 15 mm side
lcx, lcz = bx, bz - 0.8
tri = [(lcx + R * math.cos(math.radians(90 + 120 * i)), lcz + R * math.sin(math.radians(90 + 120 * i))) for i in range(3)]
r_in = R / 2                                    # inradius: edge midpoints


def polar(rad, deg):
    return (lcx + rad * math.cos(math.radians(deg)), lcz + rad * math.sin(math.radians(deg)))


def cut_curve(phi):
    """Swirl cut from the edge midpoint at angle phi into the centre (quadratic curve, 7 points)."""
    p0, p1, p2 = polar(r_in * 1.02, phi), polar(r_in * 0.62, phi + 55), (lcx, lcz)
    pts = []
    for i in range(7):
        t = i / 6
        pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                    (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
    return pts


for i in range(3):
    th = 90 + 120 * i
    a = cut_curve(th - 60)                      # midpoint -> centre
    b = cut_curve(th + 60)
    poly = list(reversed(a)) + [polar(R, th)] + b[:-1]    # centre -> midpoint, vertex, midpoint -> (centre)
    poly = [p for k, p in enumerate(poly) if k == 0 or (abs(p[0] - poly[k - 1][0]) + abs(p[1] - poly[k - 1][1])) > 1e-6]
    gx = sum(p[0] for p in poly) / len(poly)
    gz = sum(p[1] for p in poly) / len(poly)
    # open a gap along both cuts: push each point away from the cut lines towards the blade's vertex
    vx, vz = polar(R, th)
    poly = [(x + (vx - x) * 0.08, z + (vz - z) * 0.08) for x, z in poly]
    assign(prism("logo_%d" % i, poly, ydisc + 0.1, 0.55), M_LOGO)

# ------------------------------------------------------------------------------------------------
# screws (Torx, in dark counterbores), holes, wordmark
# ------------------------------------------------------------------------------------------------

def screw(name, x, z):
    assign(annulus(name + "_bore", x, z, 1.45, 1.95, Y0 - 0.02, seg=32), M_HOLE)
    s = disc(name, 1.45, x, z, Y0 + 0.2, Y0 - 0.55, seg=24, chamfer=0.3, cseg=2)
    for a in (0, 60, 120):
        cut = box("torx", 1.5, 1.0, 0.42, (x, Y0 - 0.55, z), rot=(0, math.radians(a), 0))
        boolean(s, cut)
    assign(s, M_SCREW)


for i, (x, z) in enumerate([(-27.1, 36.8), (27.1, 36.8), (-27.1, 1.6), (27.1, 1.6), (-27.1, -38.3), (27.1, -38.3)]):
    screw("screw_%d" % i, x, z)


def hole(name, x, z, r, h=0.0):
    assign(disc(name, r, x, z, Y0 - h + 0.3, Y0 - h - 0.03, seg=16), M_HOLE)


H_COL_AT_HOLE = H_COLUMN * (X_FRAME - 18.8) / (X_FRAME - X_COL_IN)   # the top holes sit on the side columns
hole("hole_tl", -18.8, 35.6, 0.65, H_COL_AT_HOLE)
hole("hole_tr", 18.8, 35.6, 0.65, H_COL_AT_HOLE)
for name, x, z in (("hole_b0", 12.6, -35.6), ("hole_b1", 15.4, -34.9)):
    hole(name, x, z, 0.62, H_SPINE * (X_FRAME - x) / (X_FRAME - 6.6))

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
txt.location = v3(0, Y0 - H_SPINE - 0.08, -43.1)
bpy.context.view_layer.update()
with bpy.context.temp_override(object=txt, active_object=txt, selected_objects=[txt], selected_editable_objects=[txt]):
    bpy.ops.object.convert(target="MESH")
txt = sc.objects["axon_txt"]
w_now = txt.dimensions.x / MM
if w_now > 0:
    s = 12.6 / w_now
    txt.scale = (s, s, s)
assign(txt, M_TEXT)

# ------------------------------------------------------------------------------------------------
# sides, top, bottom, back
# ------------------------------------------------------------------------------------------------

# left side: two buttons
assign(box("btn_left_0", 2.6, 10.0, 5.7, (-hw - 0.2, -2.0, 28.75), bevel=0.9, seg=3), M_RUBBER)
assign(box("btn_left_1", 2.6, 10.0, 14.1, (-hw - 0.2, -2.0, 13.75), bevel=0.9, seg=3), M_RUBBER)
# right side: rocker near the top and a dotted grip panel
assign(box("btn_right", 2.4, 9.0, 13.0, (hw + 0.1, -2.0, 30.0), bevel=0.9, seg=3), M_RUBBER)
assign(box("grip_right", 1.6, 16.0, 46.0, (hw - 0.3, 0.0, -14.0), bevel=0.6, seg=2), M_GRIP)
assign(box("grip_left", 1.6, 16.0, 30.0, (-hw + 0.3, 0.0, -22.0), bevel=0.6, seg=2), M_GRIP)
# top: program button and status LED
assign(box("btn_top", 16.0, 9.0, 2.2, (-6.0, 0.0, Z_TOP - 0.2), bevel=0.8, seg=3), M_RUBBER)
led = assign(disc("led", 1.3, 13.0, 0.0, 0.0, -0.5, seg=20), material("zbc_led", (0.35, 0.03, 0.03), 0.2))
led.rotation_euler = (math.radians(-90), 0, 0)
led.location = v3(0, -2.0, Z_TOP + 0.05)
# bottom: dock connector
assign(box("port", 14.0, 4.0, 1.2, (0, 0.5, Z_BOT + 0.25), bevel=0.4, seg=2), M_HOLE)
# back: RapidLock mount plate
assign(box("mount", 44.0, 4.0, 60.0, (0, D / 2 + 1.6, 0), bevel=1.5, seg=3), M_MOUNT)
assign(box("mount_lip", 36.0, 2.5, 8.0, (0, D / 2 + 4.6, 22.0), bevel=1.0, seg=3), M_MOUNT)

# shading: smooth with sharp edges above 30 degrees
meshes = [o for o in sc.objects if o.type == "MESH"]
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
with bpy.context.temp_override(selected_objects=meshes, selected_editable_objects=meshes,
                               active_object=meshes[0], object=meshes[0]):
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30))
print("zbc_bodycam: %d parts" % len(meshes))
