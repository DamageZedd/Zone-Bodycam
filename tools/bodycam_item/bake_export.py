"""Zone Bodycam - textures, icon render and OGF export for the bodycam item. Run inside Blender after
build_model.py, with these globals set before exec():

    PHASE    = "bake"    copies and joins the parts and gives every material its own texture source in OUT:
                         flat materials get an exact colour (swatches.json), the materials whose detail is
                         a shader pattern (BAKED) get their own <mat>.png colour bake over their own full
                         UV square; also renders icon.png
             = "export"  after tools\\bodycam_item\\make_item_textures.py wrote the DDS files: one X-Ray
                         material per source material, rigs the joined mesh (one bone, box shape) and
                         exports the OGF into GAMEDATA
    OUT      = folder for the bakes, swatches.json and the icon render
    GAMEDATA = the component's gamedata folder (optional\\bodycam_item\\gamedata)

No single shared texture: the geometry carries the shape, so a flat material needs nothing but its colour.
Needs the io_scene_xray addon for the export phase.
"""
import json
import math
import os
import bpy
import bmesh
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

TEX_SIZE = 1024                 # per baked material
BAKED = ("zbc_grip", "zbc_button")   # base colour comes from a shader pattern
MESH = "zbc_bodycam_mesh"
RIG = "zbc_bodycam"
TEX_NAME = "item_zbc_bodycam"
OGF_REL = os.path.join("meshes", "dynamics", "devices", "zbc_bodycam", "zbc_bodycam.ogf")

sc = bpy.data.scenes["zbc_bodycam"]
bpy.context.window.scene = sc


def parts():
    return [o for o in sc.objects if o.type == "MESH" and o.name != MESH]


def aim(o, target):
    o.rotation_euler = (Vector(target) - o.location).to_track_quat("-Z", "Y").to_euler()


def studio():
    """Soft three-point light, neutral world, camera for the icon."""
    for name, loc, energy, size in (("key", (-0.25, -0.30, 0.25), 6, 0.25), ("fill", (0.30, -0.20, 0.05), 2.0, 0.3),
                                    ("rim", (0.15, 0.30, 0.25), 5, 0.2)):
        o = sc.objects.get(name)
        if not o:
            ld = bpy.data.lights.get(name) or bpy.data.lights.new(name, "AREA")
            o = bpy.data.objects.new(name, ld)
            sc.collection.objects.link(o)
        o.data.energy, o.data.size = energy, size
        o.location = loc
        aim(o, (0, 0, 0))
    w = bpy.data.worlds.get("zbc_world") or bpy.data.worlds.new("zbc_world")
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.18, 0.18, 0.19, 1)
    bg.inputs[1].default_value = 0.6
    sc.world = w
    cam = sc.objects.get("zbc_cam")
    if not cam:
        cd = bpy.data.cameras.get("zbc_cam") or bpy.data.cameras.new("zbc_cam")
        cam = bpy.data.objects.new("zbc_cam", cd)
        sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def tex_name(mat_name):
    return TEX_NAME + "_" + mat_name.replace("zbc_", "")


def base_color(m):
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    return bsdf.inputs["Base Color"].default_value


def srgb(c):
    return [round(255 * (12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055)) for v in c[:3]]


def with_only(o, fn):
    for x in sc.objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    with bpy.context.temp_override(active_object=o, object=o, selected_objects=[o], selected_editable_objects=[o]):
        return fn()


def bake_material(o, out):
    """Unwrap one single-material copy over the full UV square and bake its base colour to <mat>.png."""
    m = o.data.materials[0]

    def unwrap():
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=0.004, area_weight=0.0,
                                 correct_aspect=True, scale_to_bounds=False)
        bpy.ops.uv.pack_islands(margin=0.004, rotate=True)
        bpy.ops.object.mode_set(mode="OBJECT")
    with_only(o, unwrap)
    i = bpy.data.images.get("bake_" + m.name)
    if i:
        bpy.data.images.remove(i)
    img = bpy.data.images.new("bake_" + m.name, TEX_SIZE, TEX_SIZE, alpha=False)
    nt = m.node_tree
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = img
    for x in nt.nodes:
        x.select = False
    n.select = True
    nt.nodes.active = n
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 64
    sc.render.bake.margin = 8
    sc.render.bake.use_pass_direct = False
    sc.render.bake.use_pass_indirect = False
    sc.render.bake.use_pass_color = True
    with_only(o, lambda: bpy.ops.object.bake(type="DIFFUSE"))
    nt.nodes.remove(n)
    img.filepath_raw = os.path.join(out, m.name + ".png")
    img.file_format = "PNG"
    img.save()


def prepare(out):
    """Copies of the parts with transforms applied and one UV map: baked materials over the full square,
    flat ones all at the centre of their swatch. Writes the bakes and swatches.json, then joins."""
    old = sc.objects.get(MESH)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    src = parts()
    for o in src:
        o.hide_render = True                       # the originals overlap the copies
    dups, swatches = [], {}
    for o in src:
        d = o.copy()
        d.data = o.data.copy()
        sc.collection.objects.link(d)
        d.hide_render = False
        with_only(d, lambda: bpy.ops.object.transform_apply(location=True, rotation=True, scale=True))
        while d.data.uv_layers:
            d.data.uv_layers.remove(d.data.uv_layers[0])
        uv = d.data.uv_layers.new(name="uv")
        names = {m.name for m in d.data.materials if m}
        if names & set(BAKED):
            assert len(d.data.materials) == 1, d.name
            bake_material(d, out)
        else:
            for lp in uv.data:
                lp.uv = (0.5, 0.5)
            for m in d.data.materials:
                swatches[m.name] = srgb(base_color(m))
        dups.append(d)
    with open(os.path.join(out, "swatches.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(swatches, f, indent=1, sort_keys=True)
    for x in sc.objects:
        x.select_set(False)
    for d in dups:
        d.select_set(True)
    with bpy.context.temp_override(selected_objects=dups, selected_editable_objects=dups,
                                   active_object=dups[0], object=dups[0]):
        bpy.ops.object.join()
    j = dups[0]
    j.name = MESH
    j.data.name = MESH
    j.hide_render = True
    for o in src:
        o.hide_render = False
    return j


def render_icon(out):
    cam = studio()
    j = sc.objects[MESH]
    j.hide_render = True
    src = parts()
    for o in src:
        o.hide_render = False
    cam.data.lens = 100
    cam.data.shift_x = cam.data.shift_y = 0
    cam.location = (-0.13, -0.30, 0.07)
    aim(cam, (0, 0.004, -0.002))
    sc.render.resolution_x = sc.render.resolution_y = 800
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.cycles.samples = 256
    sc.view_settings.exposure = -0.4
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"

    def bounds():
        xs, ys = [], []
        for o in src:
            for v in o.data.vertices:
                p = world_to_camera_view(sc, cam, o.matrix_world @ v.co)
                xs.append(p.x)
                ys.append(p.y)
        return min(xs), max(xs), min(ys), max(ys)

    bpy.context.view_layer.update()
    x0, x1, y0, y1 = bounds()
    cam.data.lens *= 0.94 / max(x1 - x0, y1 - y0)
    bpy.context.view_layer.update()
    x0, x1, y0, y1 = bounds()
    cam.data.shift_x = (x0 + x1) / 2 - 0.5
    cam.data.shift_y = (y0 + y1) / 2 - 0.5
    sc.render.filepath = os.path.join(out, "icon.png")
    bpy.ops.render.render(write_still=True)
    j.hide_render = False


def export(gamedata):
    j = sc.objects[MESH]
    # one X-Ray material per source material, each with its own texture (no shared atlas)
    for slot, src in enumerate(list(j.data.materials)):
        name = tex_name(src.name)
        dds = os.path.join(gamedata, "textures", "item", name + ".dds")
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        tex = nt.nodes.new("ShaderNodeTexImage")
        img = bpy.data.images.load(dds, check_existing=True)
        img.reload()
        tex.image = img
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        nt.links.new(bsdf.outputs[0], out.inputs[0])
        m.xray.eshader = "models\\model"
        m.xray.cshader = "default"
        m.xray.gamemtl = "objects\\small_box"
        j.data.materials[slot] = m
    # rig: one bone with a box shape around the mesh
    old = sc.objects.get(RIG)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    ad = bpy.data.armatures.new(RIG)
    rig = bpy.data.objects.new(RIG, ad)
    sc.collection.objects.link(rig)
    rig.xray.isroot = True
    rig.xray.flags_simple = "dy"
    bpy.context.view_layer.objects.active = rig
    with bpy.context.temp_override(active_object=rig, object=rig, selected_objects=[rig], selected_editable_objects=[rig]):
        bpy.ops.object.mode_set(mode="EDIT")
        b = ad.edit_bones.new("link")
        b.head = (0, 0, 0)
        b.tail = (0, 0, 0.02)
        bpy.ops.object.mode_set(mode="OBJECT")
    lo = Vector([min(v.co[i] for v in j.data.vertices) for i in range(3)])
    hi = Vector([max(v.co[i] for v in j.data.vertices) for i in range(3)])
    bx = ad.bones["link"].xray
    bx.shape.type = "1"
    bx.shape.box_trn = (hi + lo) / 2
    bx.shape.box_hsz = (hi - lo) / 2
    bx.shape.box_rot = (1, 0, 0, 0, 1, 0, 0, 0, 1)
    bx.mass.value = 0.3
    bx.gamemtl = "objects\\small_box"
    j.parent = rig
    j.vertex_groups.clear()
    vg = j.vertex_groups.new(name="link")
    vg.add(list(range(len(j.data.vertices))), 1.0, "REPLACE")
    for mod in list(j.modifiers):
        j.modifiers.remove(mod)
    am = j.modifiers.new("Armature", "ARMATURE")
    am.object = rig
    path = os.path.join(gamedata, OGF_REL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for o in sc.objects:
        o.select_set(False)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    # no temp_override here: the exporter splits the mesh by material in edit mode and switches back with
    # mode_set, which a pinned active_object would point at the rig and leave the split copy in edit mode
    r = bpy.ops.xray_export.ogf_file(filepath=path)
    for o in [o for o in sc.objects if o.name.startswith(MESH + ".")]:
        bpy.data.objects.remove(o, do_unlink=True)     # split copies the exporter can leave behind
    print("export", r, path)


if PHASE == "bake":  # noqa: F821 - set by the caller
    os.makedirs(OUT, exist_ok=True)  # noqa: F821
    prepare(OUT)  # noqa: F821
    render_icon(OUT)  # noqa: F821
elif PHASE == "export":  # noqa: F821
    export(GAMEDATA)  # noqa: F821
