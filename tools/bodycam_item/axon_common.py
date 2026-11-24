"""Zone Bodycam - shared geometry, material and finishing helpers for the Axon Body 1/2/3/5 item builders
(build_model_1.py, _2, _3, _5). Body 4's build_model.py is self-contained and does not use this file.

A builder runs it inside its own globals, after setting SCENE:

    exec(compile(open(COMMON, encoding="utf-8").read(), COMMON, "exec"), globals())
    setup_scene()

Units are metres in Blender; every helper takes millimetres. Front faces -Y, +Z is up, +X is right as seen
from the front. Helpers that place parts relative to the front need Y0 (front reference plane) defined.
"""
import math
import bpy
import bmesh
from mathutils import Vector

MM = 0.001


def setup_scene():
    """Create or empty the builder's scene and make sc / col / vl globals of the builder."""
    g = globals()
    # object names are global: another camera's scene would turn "body" into "body.001" here and the
    # name lookups (cut) would miss it, so only one camera scene lives in the file at a time
    for other in [s for s in bpy.data.scenes if s.name.startswith("zbc_bodycam") and s.name != SCENE]:  # noqa: F821
        for o in list(other.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        if len(bpy.data.scenes) > 1:
            bpy.data.scenes.remove(other)
    for coll in (bpy.data.meshes, bpy.data.curves):
        for d in [d for d in coll if d.users == 0]:
            coll.remove(d)
    sc = bpy.data.scenes.get(SCENE)  # noqa: F821 - set by the builder
    if sc is None:
        if bpy.context.window is None and len(bpy.data.scenes) == 1 and bpy.context.scene.name == "Scene":
            sc = bpy.context.scene
            sc.name = SCENE  # noqa: F821
        else:
            sc = bpy.data.scenes.new(SCENE)  # noqa: F821
    if bpy.context.window is not None:
        bpy.context.window.scene = sc
    for o in list(sc.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    g["sc"], g["col"], g["vl"] = sc, sc.collection, sc.view_layers[0]


def v3(x, y, z):
    return Vector((x * MM, y * MM, z * MM))


def Yh(h):
    """Y coordinate of a point standing h mm forward (-Y) of the Y0 reference plane."""
    return Y0 - h


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


def assign(o, m):
    o.data.materials.clear()
    o.data.materials.append(m)
    return o


def stadium_pts_2d(w, h, seg_half=12):
    """2D rounded-pill / stadium outline centered at (0, 0) with total spans (w, h)."""
    pts = []
    if w >= h:
        r = h / 2.0
        dx = (w - h) / 2.0
        for i in range(seg_half + 1):
            a = -math.pi / 2 + math.pi * i / seg_half
            pts.append((dx + r * math.cos(a), r * math.sin(a)))
        for i in range(seg_half + 1):
            a = math.pi / 2 + math.pi * i / seg_half
            pts.append((-dx + r * math.cos(a), r * math.sin(a)))
    else:
        r = w / 2.0
        dz = (h - w) / 2.0
        for i in range(seg_half + 1):
            a = math.pi * i / seg_half
            pts.append((r * math.cos(a), dz + r * math.sin(a)))
        for i in range(seg_half + 1):
            a = math.pi + math.pi * i / seg_half
            pts.append((r * math.cos(a), -dz + r * math.sin(a)))
    # deduplicate coinciding seam vertices if w == h
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    if len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) <= 1e-6:
        out.pop()
    return out


def prism_y(name, pts_xz, y_back, depth, chamfer=0.0, seg=1):
    """Extrude an XZ polygon from y_back towards -Y by depth (depth > 0 goes toward -Y; < 0 goes toward +Y)."""
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new(v3(x, y_back, z)) for x, z in pts_xz])
    bm.normal_update()
    if (depth > 0 and f.normal.y > 0) or (depth < 0 and f.normal.y < 0):
        f.normal_flip()
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]:
        v.co.y -= depth * MM
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    yf = (y_back - depth) * MM
    if chamfer > 0:
        fe = [e for e in bm.edges if all(abs(v.co.y - yf) < 1e-8 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=fe, offset=chamfer * MM, segments=seg, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return finish(bm, name)


def prism_z(name, pts_xy, z_base, height, chamfer=0.0, seg=2):
    """Extrude an XY polygon from z_base along Z by height (height > 0 goes +Z; < 0 goes -Z)."""
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new(v3(x, y, z_base)) for x, y in pts_xy])
    bm.normal_update()
    if (height > 0 and f.normal.z < 0) or (height < 0 and f.normal.z > 0):
        f.normal_flip()
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]:
        v.co.z += height * MM
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    zt = (z_base + height) * MM
    if chamfer > 0:
        fe = [e for e in bm.edges if all(abs(v.co.z - zt) < 1e-8 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=fe, offset=chamfer * MM, segments=seg, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return finish(bm, name)


def prism_x(name, pts_yz, x_base, dx, chamfer=0.0, seg=2):
    """Extrude a YZ polygon from x_base along X by dx (dx > 0 goes +X; dx < 0 goes -X)."""
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new(v3(x_base, y, z)) for y, z in pts_yz])
    bm.normal_update()
    if (dx > 0 and f.normal.x < 0) or (dx < 0 and f.normal.x > 0):
        f.normal_flip()
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]:
        v.co.x += dx * MM
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    xt = (x_base + dx) * MM
    if chamfer > 0:
        fe = [e for e in bm.edges if all(abs(v.co.x - xt) < 1e-8 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=fe, offset=chamfer * MM, segments=seg, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return finish(bm, name)


def disc(name, r, cx, cz, y_back, y_front, seg=64, chamfer=0.0, cseg=1, r_front=None):
    """Cylinder/frustum along Y from y_back to y_front."""
    bm = bmesh.new()
    pts = [(r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    f = bm.faces.new([bm.verts.new(v3(cx + x, y_back, cz + z)) for x, z in pts])
    bm.normal_update()
    if (y_front < y_back and f.normal.y > 0) or (y_front > y_back and f.normal.y < 0):
        f.normal_flip()
    rr = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [g for g in rr["geom"] if isinstance(g, bmesh.types.BMVert)]
    s = 1.0 if r_front is None else r_front / r
    c = v3(cx, 0, cz)
    for v in top:
        v.co.y = y_front * MM
        v.co.x = c.x + (v.co.x - c.x) * s
        v.co.z = c.z + (v.co.z - c.z) * s
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if chamfer > 0:
        fe = [e for e in bm.edges if all(abs(v.co.y - y_front * MM) < 1e-8 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=fe, offset=chamfer * MM, segments=cseg, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return finish(bm, name)


def annulus(name, cx, cz, r0, r1, y_front, y_back, a0=0.0, a1=360.0, seg=64, chamfer_front=0.0):
    """Solid hollow ring or arc sector along Y between y_front and y_back."""
    bm = bmesh.new()
    full = abs(a1 - a0) >= 360.0
    n = seg if full else max(4, int(seg * abs(a1 - a0) / 360.0))
    rows = []
    for yy in (y_front, y_back):
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
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if chamfer_front > 0:
        fe = [e for e in bm.edges if all(abs(v.co.y - y_front * MM) < 1e-8 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=fe, offset=chamfer_front * MM, segments=2, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return finish(bm, name)


def funnel(name, cx, cz, r_top, y_top, r_bot, y_bot, seg=128, a0=0.0, a1=360.0, thick=0.0):
    """Conical ring surface (or solid arc when thick > 0) from (r_top, y_top) to (r_bot, y_bot)."""
    bm = bmesh.new()
    full = abs(a1 - a0) >= 360.0
    n = seg if full else max(6, int(seg * abs(a1 - a0) / 360.0))
    top, bot = [], []
    for i in range(n if full else n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        top.append(bm.verts.new(v3(cx + r_top * math.cos(a), y_top, cz + r_top * math.sin(a))))
        bot.append(bm.verts.new(v3(cx + r_bot * math.cos(a), y_bot, cz + r_bot * math.sin(a))))
    faces = []
    for i in range(len(top) if full else len(top) - 1):
        j = (i + 1) % len(top)
        faces.append(bm.faces.new([top[i], bot[i], bot[j], top[j]]))
    bm.normal_update()
    for f in faces:
        if f.normal.y > 0:
            f.normal_flip()
    if thick > 0:
        r = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
        for v in [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]:
            v.co.y += thick * MM
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        return link(name, me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(name, me)


def lathe(name, cx, cz, prof, y_ref, seg=120):
    """Revolve a profile [(radius, dy)] (dy < 0: towards -Y viewer) about Y axis at (cx, cz)."""
    bm = bmesh.new()
    rings = []
    for r, dy in prof:
        ring = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            ring.append(bm.verts.new(v3(cx + r * math.cos(a), y_ref + dy, cz + r * math.sin(a))))
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


def box(name, sx, sy, sz, loc, bevel=0.0, seg=2, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts:
        v.co = Vector((v.co.x * sx * MM, v.co.y * sy * MM, v.co.z * sz * MM))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel * MM, segments=seg, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    o = finish(bm, name)
    o.location = v3(*loc)
    o.rotation_euler = rot
    return o


def hull(name, pts):
    bm = bmesh.new()
    for q in pts:
        bm.verts.new(v3(*q))
    bmesh.ops.convex_hull(bm, input=bm.verts[:])
    return finish(bm, name)


def boolean(target, cutter, op="DIFFERENCE"):
    vl.update()
    m = target.modifiers.new("b", "BOOLEAN")
    m.object = cutter
    m.operation = op
    m.solver = "EXACT"
    vl.objects.active = target
    with bpy.context.temp_override(scene=sc, view_layer=vl, object=target, active_object=target):
        bpy.ops.object.modifier_apply(modifier="b")
    bpy.data.objects.remove(cutter, do_unlink=True)
    for p in target.data.polygons:
        p.material_index = 0
    while len(target.data.materials) > 1:
        target.data.materials.pop()


def cut(targets, make):
    for tname in targets:
        o = sc.objects.get(tname)
        assert o is not None, "cut target %s is not in the scene" % tname
        boolean(o, make())


def _build_principled(m, color, rough, metal=0.0, spec=0.5, emission=None):
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


def shared_material(name, color, rough, metal=0.0, spec=0.5, noise=False):
    """Reuse existing Body 4 shared material if already loaded in live Blender, else create identically."""
    m = bpy.data.materials.get(name)
    if m is not None and m.use_nodes and any(n.type == "BSDF_PRINCIPLED" for n in m.node_tree.nodes):
        return m
    m = m or bpy.data.materials.new(name)
    _build_principled(m, color, rough, metal=metal, spec=spec)
    if noise:
        surface_noise(m)
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


def knurl(m, cx, cz, r_in, r_out, cell, base_a, base_b, groove):
    """Fine micro-knurl pattern on the concave Event button dish (world XZ, mm), for Cycles + UV bake."""
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
    bump.inputs["Strength"].default_value = 0.65
    bump.inputs["Distance"].default_value = 0.0002
    L.new(op("SUBTRACT", None, gr, va=1.0), bump.inputs["Height"])
    L.new(bump.outputs[0], b.inputs["Normal"])



def own_material(name, color, rough, metal=0.0, spec=0.5, noise=False, emission=None):
    """Create or refresh a material of this camera only (zbc_<n>_*): its own item_zbc_bodycam_<n>_* texture."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    _build_principled(m, color, rough, metal=metal, spec=spec, emission=emission)
    if noise:
        surface_noise(m)
    return m


def surface_at(x, z):
    """Raycast onto the front body surface from -Y."""
    vl.update()
    dg = sc.view_layers[0].depsgraph if hasattr(sc.view_layers[0], "depsgraph") else bpy.context.evaluated_depsgraph_get()
    if dg is None:
        dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, nor, _i, _o, _m = sc.ray_cast(dg, v3(x, Y0 - 30.0, z), Vector((0, 1, 0)))
    if not hit:
        return v3(x, Y0, z), Vector((0, -1, 0))
    return loc, nor


def facing(nor):
    return Vector((0, -1, 0)).rotation_difference(nor)


def front_mic(name, x, z, r=0.62):
    loc, nor = surface_at(x, z)
    o = assign(disc(name, r, 0, 0, 0.30, -0.04, seg=18), M_HOLE)
    o.location = loc
    o.rotation_euler = facing(nor).to_euler()




def make_text_mesh(name, text_str, size_mm, extrude_mm, space=1.08, res_u=3, font=r"C:\Windows\Fonts\GOTHIC.TTF"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text_str
    cu.resolution_u = res_u
    try:
        cu.font = bpy.data.fonts.load(font, check_existing=True)
    except RuntimeError:
        pass
    cu.size = size_mm * MM
    cu.extrude = extrude_mm * MM
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.space_character = space
    o = bpy.data.objects.new(name, cu)
    col.objects.link(o)
    vl.update()
    vl.objects.active = o
    for x_obj in sc.objects:
        x_obj.select_set(False)
    o.select_set(True)
    with bpy.context.temp_override(scene=sc, view_layer=vl, object=o, active_object=o,
                                   selected_objects=[o], selected_editable_objects=[o]):
        bpy.ops.object.convert(target="MESH")
    return vl.objects.active  # the converted mesh object


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



def std_materials():
    """The flat materials shared with Body 4 (same names, so they reuse its item_zbc_bodycam_* textures)."""
    g = globals()
    for var, args in (
        ("M_BODY", ("zbc_body", (0.034, 0.035, 0.038), 0.62, 0.0, 0.5, True)),
        ("M_RUBBER", ("zbc_rubber", (0.022, 0.022, 0.024), 0.75)),
        ("M_GLOSS", ("zbc_gloss", (0.020, 0.021, 0.023), 0.18)),
        ("M_BEZEL", ("zbc_bezel", (0.016, 0.016, 0.018), 0.45)),
        ("M_GLASS", ("zbc_glass", (0.004, 0.005, 0.008), 0.03, 0.0, 1.0)),
        ("M_HOLE", ("zbc_hole", (0.002, 0.002, 0.002), 0.90)),
        ("M_SCREW", ("zbc_screw", (0.035, 0.035, 0.038), 0.40, 1.0)),
        ("M_TEXT", ("zbc_text", (0.72, 0.72, 0.72), 0.45)),
        ("M_LOGO", ("zbc_logo", (0.006, 0.006, 0.007), 0.30)),
        ("M_LIGHTPIPE", ("zbc_lightpipe", (0.62, 0.63, 0.65), 0.25)),
        ("M_DISC", ("zbc_disc", (0.056, 0.057, 0.062), 0.50)),
        ("M_MOUNT", ("zbc_mount", (0.018, 0.018, 0.020), 0.50)),
        ("M_LABEL", ("zbc_label", (0.30, 0.30, 0.31), 0.60)),
        ("M_MAGNET", ("zbc_magnet", (0.05, 0.05, 0.055), 0.35, 1.0)),
        ("M_FACE", ("zbc_face", (0.038, 0.039, 0.042), 0.58)),
        ("M_GRIP", ("zbc_grip", (0.020, 0.020, 0.022), 0.80)),
    ):
        g[var] = shared_material(*args)


def stroke(pts, w, cap=True):
    """Outline polygon of a polyline drawn with width w (mm): a flat ribbon for raised logos."""
    n = len(pts)
    left, right = [], []
    for i in range(n):
        p = Vector(pts[i])
        a = Vector(pts[max(i - 1, 0)])
        b = Vector(pts[min(i + 1, n - 1)])
        t = (b - a).normalized()
        nrm = Vector((-t.y, t.x))
        if 0 < i < n - 1:                              # mitre joint, limited
            t0 = (p - a).normalized()
            t1 = (b - p).normalized()
            m = Vector((-(t0 + t1).y, (t0 + t1).x)).normalized()
            k = min(1.0 / max(m.dot(Vector((-t0.y, t0.x))), 0.35), 2.5)
            nrm = m * k
        left.append(tuple(p + nrm * (w / 2)))
        right.append(tuple(p - nrm * (w / 2)))
    return left + list(reversed(right))


def bezier(p0, p1, p2, p3=None, n=12):
    """Points along a quadratic (or cubic, with p3) Bezier in 2D."""
    out = []
    for i in range(n + 1):
        t = i / n
        if p3 is None:
            q = [(1 - t) ** 2 * p0[k] + 2 * (1 - t) * t * p1[k] + t * t * p2[k] for k in range(2)]
        else:
            q = [(1 - t) ** 3 * p0[k] + 3 * (1 - t) ** 2 * t * p1[k] + 3 * (1 - t) * t * t * p2[k] + t ** 3 * p3[k]
                 for k in range(2)]
        out.append(tuple(q))
    return out


def rounded_poly(pts, r, seg=4):
    """Round every corner of a convex-or-not 2D polygon by radius r (clamped to half the shorter edge)."""
    n = len(pts)
    out = []
    for i in range(n):
        p, a, b = Vector(pts[i]), Vector(pts[i - 1]), Vector(pts[(i + 1) % n])
        da, db = (a - p), (b - p)
        la, lb = da.length, db.length
        da.normalize()
        db.normalize()
        ang = math.acos(max(-1.0, min(1.0, da.dot(db))))
        if ang < 1e-3 or ang > math.pi - 1e-3:
            out.append(tuple(p))
            continue
        d = min(r / math.tan(ang / 2), la * 0.45, lb * 0.45)
        rr = d * math.tan(ang / 2)
        p1, p2 = p + da * d, p + db * d
        c = p + (da + db).normalized() * (rr / math.sin(ang / 2))
        a1 = math.atan2(p1.y - c.y, p1.x - c.x)
        a2 = math.atan2(p2.y - c.y, p2.x - c.x)
        da_ = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        for k in range(seg + 1):
            t = a1 + da_ * k / seg
            out.append((c.x + rr * math.cos(t), c.y + rr * math.sin(t)))
    return out


def place_on_front(o, x, z, lift=0.0):
    """Put o (built around the origin, facing -Y) on the front surface at (x, z), tilted with it."""
    loc, nor = surface_at(x, z)
    o.location = loc + nor * (lift * MM)
    o.rotation_euler = facing(nor).to_euler()
    return o


def front_text(name, text, x, z, width, mat, font=r"C:\Windows\Fonts\GOTHIC.TTF", extrude=0.08, lift=0.03,
               space=1.08):
    """Raised text on the front surface, centred at (x, z), scaled to the given width (mm)."""
    from mathutils import Matrix
    t = make_text_mesh(name, text, 4.0, extrude, space=space, res_u=4, font=font)
    vl.update()  # noqa: F821
    s = width / (t.dimensions.x / MM)
    # glyphs lie in XY and extrude along +Z: turn +90 deg about X so they read from -Y and stand out to -Y
    t.data.transform(Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Scale(s, 4))
    t.data.update()
    place_on_front(t, x, z, lift)
    return assign(t, mat)


def screw(name, x, z, y_floor, r_bore=1.85, r_head=1.40, targets=("body",)):
    """Torx screw sunk in a dark counterbore whose floor is at y_floor (mm, Y coordinate)."""
    cut(list(targets), lambda: disc(name + "_bore_cut", r_bore, x, z, y_floor, y_floor - 12.0, seg=32))
    assign(annulus(name + "_bore", x, z, r_head, r_bore, y_floor - 0.02, y_floor + 0.18, seg=32), M_HOLE)  # noqa: F821
    s = disc(name, r_head, x, z, y_floor + 0.20, y_floor - 0.52, seg=24, chamfer=0.28, cseg=2)
    for a in (0, 60, 120):
        boolean(s, box("torx", r_head * 1.0, 1.0, 0.40, (x, y_floor - 0.52, z), rot=(0, math.radians(a), 0)))
    return assign(s, M_SCREW)  # noqa: F821


def finish_shell(body, bevel=0.32, angle=25):
    """Weld, flatten coplanar faces and give every hard edge a small moulded bevel."""
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005 * MM)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts[:], edges=bm.edges[:])
    bm.to_mesh(body.data)
    bm.free()
    if bevel > 0:
        b = body.modifiers.new("edge_bevel", "BEVEL")
        b.limit_method = "ANGLE"
        b.angle_limit = math.radians(angle)
        b.width = bevel * MM
        b.segments = 2
        b.profile = 0.6
        b.harden_normals = True
        vl.objects.active = body  # noqa: F821
        with bpy.context.temp_override(scene=sc, view_layer=vl, object=body, active_object=body):  # noqa: F821
            bpy.ops.object.modifier_apply(modifier="edge_bevel")


def smooth_all(flat=(), angle=30, flat_angle=8):
    """Smooth by angle for every part; the faceted shells in `flat` keep crisp facets."""
    meshes = [o for o in sc.objects if o.type == "MESH"]  # noqa: F821
    for o in meshes:
        assert len(o.data.materials) == 1, "%s has %d materials" % (o.name, len(o.data.materials))

    def run(objs, a):
        for o in sc.objects:  # noqa: F821
            o.select_set(False)
        for o in objs:
            o.select_set(True)
        vl.objects.active = objs[0]  # noqa: F821
        with bpy.context.temp_override(scene=sc, view_layer=vl, selected_objects=objs,  # noqa: F821
                                       selected_editable_objects=objs, active_object=objs[0], object=objs[0]):
            bpy.ops.object.shade_smooth_by_angle(angle=math.radians(a))
    run(meshes, angle)
    if flat:
        run(list(flat), flat_angle)
    return meshes


def delta_polys(R, cx=0.0, cz=0.0):
    """The Axon delta: an apex-up triangle of circumradius R split into three blades by curved swirl cuts.
    Returns three XZ polygons (mm) around (cx, cz)."""
    def polar(rad, deg):
        return (cx + rad * math.cos(math.radians(deg)), cz + rad * math.sin(math.radians(deg)))

    r_in = R / 2.0

    def cut_curve(phi):
        return bezier(polar(r_in * 1.02, phi), polar(r_in * 0.60, phi + 42), (cx, cz), n=6)

    polys = []
    for i in range(3):
        th = 90 + 120 * i
        a, b = cut_curve(th - 60), cut_curve(th + 60)
        poly = list(reversed(a)) + [polar(R, th)] + b[:-1]
        poly = [q for k, q in enumerate(poly)
                if k == 0 or abs(q[0] - poly[k - 1][0]) + abs(q[1] - poly[k - 1][1]) > 1e-6]
        vx, vz = polar(R, th)
        polys.append([(x + (vx - x) * 0.055, z + (vz - z) * 0.055) for x, z in poly])
    return polys


def flat_logo(name, polys, depth, mat, chamfer=0.0):
    """A raised logo built flat around the origin (XZ, front at -Y): one prism per polygon, joined."""
    parts = [prism_y(name + "_%d" % i, p, 0.0, depth, chamfer=chamfer, seg=1) for i, p in enumerate(polys)]
    for p in parts[1:]:
        boolean(parts[0], p, op="UNION")
    parts[0].name = name
    return assign(parts[0], mat)


def knurl_patch(name, axis, plane, u_range, v_range, pitch, height, mat, sign=1):
    """Diamond knurl teeth (square pyramids turned 45 deg) on an axis-aligned side plane.
    axis 'x': teeth on the plane x = plane, u = Y, v = Z, pointing to sign * X."""
    bm = bmesh.new()
    u0, u1 = u_range
    v0, v1 = v_range
    h = pitch / 2.0
    nu = int((u1 - u0) / pitch)
    nv = int((v1 - v0) / pitch)
    uo = u0 + ((u1 - u0) - nu * pitch) / 2.0
    vo = v0 + ((v1 - v0) - nv * pitch) / 2.0
    for iu in range(nu + 1):
        for iv in range(nv + 1):
            cu, cv = uo + iu * pitch, vo + iv * pitch
            if (iu + iv) % 2:
                continue
            base = [(cu + h, cv), (cu, cv + h), (cu - h, cv), (cu, cv - h)]
            if any(not (u0 - 1e-6 <= q[0] <= u1 + 1e-6 and v0 - 1e-6 <= q[1] <= v1 + 1e-6) for q in base):
                continue
            if axis == "x":
                vs = [bm.verts.new(v3(plane, u, v)) for u, v in base]
                tip = bm.verts.new(v3(plane + sign * height, cu, cv))
            else:                                       # axis 'y': u = X, v = Z
                vs = [bm.verts.new(v3(u, plane, v)) for u, v in base]
                tip = bm.verts.new(v3(cu, plane + sign * height, cv))
            bm.faces.new(list(reversed(vs)))
            for k in range(4):
                bm.faces.new([vs[k], vs[(k + 1) % 4], tip])
    return assign(finish(bm, name), mat)
