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
W, D = 64.5, 30.0
Z_TOP, Z_BOT = 47.0, -48.0    # body top and bottom (95 mm; the features are centred on Z = 0)
CUT_X, CUT_Z = 10.3, 7.7      # corner cuts of the outline
FRONT_CHAMFER = 3.4           # dark rim band around the front (rounded profile)
CORNER_R = 3.0                # rounding of the cut corners
Y0 = -D / 2                   # front plane
EMBED = 0.3                   # relief parts start this far inside the shell

# ---- front relief heights (mm in front of Y0)
H_SPINE = 1.6                 # central vertical spine and the chin
H_BLOCK = 4.0                 # lens block (highest plateau)
H_BTN = 2.6                   # button block: lower, the strip between the two ramps down to it
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
knurl(M_BUTTON, BTN[0], BTN[1], 13.3, 19.6, 0.85, (0.040, 0.041, 0.045), (0.050, 0.051, 0.056), (0.010, 0.010, 0.011))
dots(M_GRIP, 1, 2, 1.35, 0.42, (0.016, 0.016, 0.018), (0.034, 0.034, 0.037))

# ------------------------------------------------------------------------------------------------
# shell
# ------------------------------------------------------------------------------------------------

hw = W / 2
outline = [(-hw + CUT_X, Z_TOP), (hw - CUT_X, Z_TOP), (hw, Z_TOP - CUT_Z), (hw, Z_BOT + CUT_Z),
           (hw - CUT_X, Z_BOT), (-hw + CUT_X, Z_BOT), (-hw, Z_BOT + CUT_Z), (-hw, Z_TOP - CUT_Z)]
def shell(name):
    """Extruded outline; the cut corners rounded, then a rounded rim at the front and the back."""
    o = prism(name, outline, D / 2, D)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    ye = [e for e in bm.edges if abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-9 and abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-9]
    bmesh.ops.bevel(bm, geom=ye, offset=CORNER_R * MM, segments=4, profile=0.5, affect="EDGES", clamp_overlap=True)
    fe = [e for e in bm.edges if all(abs(v.co.y - Y0 * MM) < 1e-9 for v in e.verts)]
    bmesh.ops.bevel(bm, geom=fe, offset=FRONT_CHAMFER * MM, segments=3, profile=0.62, affect="EDGES", clamp_overlap=True)
    be = [e for e in bm.edges if all(abs(v.co.y - D / 2 * MM) < 1e-9 for v in e.verts)]
    bmesh.ops.bevel(bm, geom=be, offset=3.0 * MM, segments=3, profile=0.5, affect="EDGES", clamp_overlap=True)
    bm.to_mesh(o.data)
    bm.free()
    return o


def hull(name, pts):
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(v3(*p))
    bmesh.ops.convex_hull(bm, input=bm.verts[:])
    return finish(bm, name)


body = assign(shell("body"), M_BODY)
# notches in the front rim beside programmable button 1: the floor slopes back from Z 25.2 to Z 31
for s_ in (-1, 1):
    pts = [(-25.8, Y0, 25.2), (-40, Y0, 25.2), (-40, Y0 + 3.2, 31.0), (-30.0, Y0 + 3.2, 31.0),
           (-25.8, Y0 - 3, 25.2), (-40, Y0 - 3, 25.2), (-40, Y0 - 3, 31.0), (-30.0, Y0 - 3, 31.0)]
    boolean(body, hull("notch", [(s_ * x, y, z) for x, y, z in pts]))

# ------------------------------------------------------------------------------------------------
# front relief (measured outlines, mm)
# ------------------------------------------------------------------------------------------------

Z_END_T, Z_END_B = Z_TOP - FRONT_CHAMFER, Z_BOT + FRONT_CHAMFER   # the rim chamfer starts here
TOP_IN_T, TOP_IN_B = Z_END_T - 0.5, Z_END_B + 0.5                 # short end walls of the sunk spine
X_FRAME = 25.8                           # outer flat frame (with the screws) ends here

# Front relief (corrected by the author against the photos): the lens area and the main button area
# are flat and on the same level; raised bumps with ramps on both sides run between them, above the
# lens and under the button; the side columns slope from the screw frame up to that level.
H_FLOOR = 3.0                    # lens area and button area (same level)
H_BUMP = 4.5                     # flat tops of the three bumps
FRONT = []                       # every relief solid, for the pocket cuts further down


def add(o):
    FRONT.append(o.name)
    return assign(o, M_FACE)


def facets(name, pts, tris):
    """A surface patch given as triangles over points (x, z, h), each triangle its own solid slab."""
    for k, (a, b, c) in enumerate(tris):
        add(slab("%s_%d" % (name, k), [pts[a], pts[b], pts[c]]))


def quads(name, quad_list):
    """Each quad (four (x, z, h) points) split into two triangle slabs."""
    for k, (a, b, c, d) in enumerate(quad_list):
        facets("%s_%d" % (name, k), [a, b, c, d], [(0, 1, 2), (0, 2, 3)])


F, HB = H_FLOOR, H_BUMP
LENS_OUT = mirror_x([(0, 36.4), (-13.5, 36.4), (-15.1, 34.8), (-15.1, 20.1), (-6.6, 14.4), (0, 14.4)])
BTN_OUT = mirror_x([(0, 6.9), (-18.3, 6.9), (-22.0, 3.9), (-22.0, -26.0), (-20.6, -28.2), (-6.6, -34.6), (0, -34.6)])


def frustum(name, base, base_h, h_top, insets, chamfer=0.2):
    """Flat-top pyramid: base outline with a height per vertex (mm in front of the front plane), a flat
    top at h_top over the outline inset by `insets` (one value per edge, edge i = base[i] -> base[i+1])."""
    top = inset_convex(base, insets)
    bm = bmesh.new()
    back = [bm.verts.new(v3(x, Y0 + EMBED, z)) for x, z in base]
    ring = [bm.verts.new(v3(x, Y0 - bh, z)) for (x, z), bh in zip(base, base_h)]
    front = [bm.verts.new(v3(x, Y0 - h_top, z)) for x, z in top]
    n = len(base)
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([back[i], back[j], ring[j], ring[i]])
        bm.faces.new([ring[i], ring[j], front[j], front[i]])
    bm.normal_update()
    if chamfer > 0:
        fe = [e for e in bm.edges if all(abs(v.co.y - (Y0 - h_top) * MM) < 1e-9 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=fe, offset=chamfer * MM, segments=2, profile=0.5, affect="EDGES", clamp_overlap=True)
    return add(finish(bm, name))


# Base (agreed diagram): one flat-top pyramid over the whole front inside the screw strips. Its top is
# the lens/button level; its left and right sides are the big side bevels (S) rising from the screw
# strips; its top and bottom sides run down into the rim. Pieces never share a flat face (that breaks
# the union): every base ring sits a little inside the surface it rises from.
SINK = 0.05                                      # base rings this far below the surface under them
CORE = [(-25.8, 40.5), (-20.6, Z_END_T), (20.6, Z_END_T), (25.8, 40.5),
        (25.8, -41.5), (20.6, Z_END_B), (-20.6, Z_END_B), (-25.8, -41.5)]
frustum("core", CORE, [-SINK] * 8, F, [6.0, 2.0, 6.0, 10.7, 6.0, 2.0, 6.0, 10.7], chamfer=0.0)
# button area (B): the same level, wider than the core's flat top; only the two side wings are added,
# standing up from the side bevels with a small sloped wall (their inner edge meets the core's top edge)
for s_ in (-1, 1):
    wing = [(15.1, 6.9), (18.3, 6.9), (22.0, 3.9), (22.0, -26.0), (20.6, -28.2), (15.1, -30.71)]
    wing = [(s_ * x, z) for x, z in wing]
    walls = [0.8, 0.8, 0.8, 0.8, 0.8, 0.0]       # last edge = the inner edge (x = 15.1): vertical, flush with the core
    frustum("button_wing_%s" % ("r" if s_ > 0 else "l"), wing, [-SINK] * 6, F, walls, chamfer=0.0)
# three flat-top pyramids rising from that level: T above the lens (trapezoid to the top edge),
# M between lens and button, Bo below the button (trapezoid to the bottom edge, carries AXON)
FB = F - 0.4                                     # bump bases start just inside the lens/button level
frustum("bump_top", [(-13.5, 36.4), (13.5, 36.4), (20.0, Z_END_T - 0.05), (-20.0, Z_END_T - 0.05)],
        [FB, FB, -0.3, -0.3], HB, [1.5, 1.8, 2.0, 1.8])
frustum("bump_mid", [(-6.6, 14.4), (6.6, 14.4), (6.6, 6.9), (-6.6, 6.9)], [FB] * 4, HB, [1.5, 1.2, 1.5, 1.2])
frustum("bump_bottom", [(-6.6, -34.6), (6.6, -34.6), (20.0, Z_END_B + 0.05), (-20.0, Z_END_B + 0.05)],
        [FB, FB, -0.3, -0.3], HB, [1.5, 1.8, 2.0, 1.8])

# one flush piece: the bumps are merged into the shell, so their sloped sides run straight into the
# front plane and the rim instead of sitting on it as separate blocks
for tname in list(FRONT):
    o = sc.objects.get(tname)
    if o:
        boolean(body, o, op="UNION")
FRONT.clear()

# pockets around the two middle screws (left and right edge, at the button block's top)
for s_ in (-1, 1):
    for tname in ["body"] + FRONT:
        o = sc.objects.get(tname)
        if o:
            boolean(o, box("screw_pocket_cut", 5.8, 6.5, 6.4, (s_ * 27.3, Y0 - 1.75, 1.6), bevel=0.6, seg=2))

Y_LENS = Y0 - H_FLOOR                            # lens area
Y_BTN = Y0 - H_FLOOR                             # button area


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
# lens: sunk into the lens block (second reference photo): a dark round pocket, a ring with four
# dark notches at the diagonals, a black groove and the glass deep inside
# ------------------------------------------------------------------------------------------------

Y_LENS_FLOOR = Y_LENS + 3.0
cut(FRONT + ["body"],
    lambda: disc("lens_pocket_cut", 10.2, lx, lz, Y_LENS_FLOOR, Y0 - 12.0, seg=120))
assign(funnel("lens_wall", lx, lz, 10.2, Y_LENS - 0.01, 9.5, Y_LENS_FLOOR - 0.01, seg=120), M_GLOSS)
yl = Y_LENS_FLOOR - 0.7
assign(disc("lens_ring", 9.5, lx, lz, Y_LENS_FLOOR + 0.2, yl, seg=120, chamfer=0.25, cseg=2), M_TAB)
for a in (45, 135, 225, 315):
    r = math.radians(a)
    assign(box("lens_notch", 2.2, 0.3, 1.3, (lx + 8.3 * math.cos(r), yl - 0.05, lz + 8.3 * math.sin(r)), rot=(0, -r, 0)), M_HOLE)
assign(annulus("lens_groove", lx, lz, 6.6, 7.1, yl - 0.02), M_HOLE)
assign(disc("lens_face", 6.6, lx, lz, yl + 0.2, yl - 0.2, seg=96, chamfer=0.2, cseg=2), M_BEZEL)
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=5.0 * MM)
for v in bm.verts:
    v.co.y *= 0.25
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 1e-7], context="VERTS")
glass = assign(finish(bm, "lens_glass"), M_GLASS)
glass.location = v3(lx, yl - 0.2, lz)

# ------------------------------------------------------------------------------------------------
# button: sunk in a well in the button block: dark glossy wall, groove, knurled face, smooth centre
# disc, raised beveled logo; white light pipes top and left, a row of white dots on the right
# ------------------------------------------------------------------------------------------------

DISH = 1.6                                       # the button face is concave: this deep at the centre
cut(FRONT + ["body"], lambda: disc("button_seat_cut", 21.7, bx, bz, Y_BTN - 0.01, Y0 - 12.0, seg=128))   # not coplanar with the front
cut(FRONT + ["body"], lambda: disc("button_dish_cut", 13.3, bx, bz, Y_BTN + DISH, Y_BTN - 0.01, seg=128, r_front=19.95))
assign(annulus("button_ring", bx, bz, 20.5, 21.7, Y_BTN - 0.03, seg=128), M_GLOSS)
assign(annulus("button_groove", bx, bz, 19.9, 20.5, Y_BTN - 0.02, seg=128), M_HOLE)
assign(funnel("button", bx, bz, 19.95, Y_BTN - 0.02, 13.3, Y_BTN + DISH - 0.02), M_BUTTON)
ydisc = Y_BTN + DISH - 0.03
assign(disc("button_disc", 13.3, bx, bz, ydisc + 0.1, ydisc, seg=96), M_DISC)


def dish_y(r):                                   # depth of the concave face at radius r
    return Y_BTN - 0.04 + DISH * (19.95 - r) / (19.95 - 13.3)


assign(funnel("lightpipe_top", bx, bz, 17.2, dish_y(17.2), 16.6, dish_y(16.6), seg=128, a0=80, a1=100), M_LIGHTPIPE)
assign(funnel("lightpipe_left", bx, bz, 17.2, dish_y(17.2), 16.6, dish_y(16.6), seg=128, a0=196, a1=232), M_LIGHTPIPE)
for i in range(9):                              # indicator dots on the right
    a = math.radians(298 + i * 4.6)
    yd = dish_y(17.6)
    assign(disc("dot_%d" % i, 0.38, bx + 17.6 * math.cos(a), bz + 17.6 * math.sin(a), yd + 0.1, yd - 0.04, seg=12), M_LIGHTPIPE)

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
    p0, p1, p2 = polar(r_in * 1.02, phi), polar(r_in * 0.6, phi + 42), (lcx, lcz)
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
    poly = [(x + (vx - x) * 0.055, z + (vz - z) * 0.055) for x, z in poly]
    assign(prism("logo_%d" % i, poly, ydisc + 0.1, 1.2, chamfer=0.22), M_LOGO)

# ------------------------------------------------------------------------------------------------
# screws (Torx, in dark counterbores), holes, wordmark
# ------------------------------------------------------------------------------------------------

def screw(name, x, z, yb=Y0):
    assign(annulus(name + "_bore", x, z, 1.45, 1.95, yb - 0.02, seg=32), M_HOLE)
    s = disc(name, 1.45, x, z, yb + 0.2, yb - 0.55, seg=24, chamfer=0.3, cseg=2)
    for a in (0, 60, 120):
        cut = box("torx", 1.5, 1.0, 0.42, (x, yb - 0.55, z), rot=(0, math.radians(a), 0))
        boolean(s, cut)
    assign(s, M_SCREW)


for i, (x, z) in enumerate([(-27.1, 36.8), (27.1, 36.8), (-27.1, 1.6), (27.1, 1.6), (-27.1, -38.3), (27.1, -38.3)]):
    screw("screw_%d" % i, x, z, Y0 + 1.5 if abs(z - 1.6) < 0.01 else Y0)


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


hole("hole_tl", -18.8, 36.2, 0.65)
hole("hole_tr", 18.8, 36.2, 0.65)
hole("hole_b0", 12.6, -35.6, 0.62)
hole("hole_b1", 15.4, -34.9, 0.62)
TXT_LOC, TXT_NOR = surface_at(0, -41.8)

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
txt.rotation_euler = (facing(TXT_NOR) @ txt.rotation_euler.to_quaternion()).to_euler()   # lie on the bottom slope
txt.location = TXT_LOC + TXT_NOR * (0.09 * MM)
w_now = txt.dimensions.x / MM
if w_now > 0:
    s = 12.6 / w_now
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
assign(box("grip_right", 1.2, 20.0, 56.0, (hw + 0.2, 0.5, -16.5), bevel=0.5, seg=2), M_GRIP)
# top: status display in a rubber bezel, operation LED
assign(box("display_bezel", 40.0, 16.0, 1.6, (1.5, -2.5, Z_TOP + 0.2), bevel=1.2, seg=3), M_RUBBER)
assign(box("display", 34.0, 11.5, 1.6, (1.5, -2.5, Z_TOP + 0.35), bevel=0.8, seg=3), M_DISPLAY)
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
print("zbc_bodycam: %d parts" % len(meshes))
