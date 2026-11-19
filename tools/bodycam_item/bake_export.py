"""Zone Bodycam - bake, icon render and OGF export for the bodycam item. Run inside Blender after
build_model.py, with these globals set before exec():

    PHASE    = "bake"    joins a copy of the parts, unwraps it, bakes albedo.png + ao.png and renders
                         icon.png into OUT
             = "export"  after tools\\bodycam_item\\make_item_textures.py wrote the DDS files: rigs the
                         joined mesh (one bone, box shape) and exports the OGF into GAMEDATA
    OUT      = folder for the bakes and the icon render
    GAMEDATA = the component's gamedata folder (optional\\bodycam_item\\gamedata)

Needs the io_scene_xray addon for the export phase.
"""
import math
import os
import bpy
import bmesh
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

TEX_SIZE = 1024
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


def join_copy():
    old = sc.objects.get(MESH)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    src = parts()
    dups = []
    for o in src:
        d = o.copy()
        d.data = o.data.copy()
        sc.collection.objects.link(d)
        dups.append(d)
    for o in sc.objects:
        o.select_set(False)
    for d in dups:
        d.select_set(True)
    with bpy.context.temp_override(selected_objects=dups, selected_editable_objects=dups,
                                   active_object=dups[0], object=dups[0]):
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.ops.object.join()
    j = dups[0]
    j.name = MESH
    j.data.name = MESH
    with bpy.context.temp_override(active_object=j, object=j, selected_objects=[j], selected_editable_objects=[j]):
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=0.006, area_weight=0.0,
                                 correct_aspect=True, scale_to_bounds=False)
        bpy.ops.uv.pack_islands(margin=0.006, rotate=True)
        bpy.ops.object.mode_set(mode="OBJECT")
    return j


def bake(j, out):
    def image(name, non_color=False):
        i = bpy.data.images.get(name)
        if i:
            bpy.data.images.remove(i)
        i = bpy.data.images.new(name, TEX_SIZE, TEX_SIZE, alpha=False)
        if non_color:
            i.colorspace_settings.name = "Non-Color"
        return i

    def target(img):
        for m in j.data.materials:
            nt = m.node_tree
            n = nt.nodes.get("BAKE_TARGET") or nt.nodes.new("ShaderNodeTexImage")
            n.name = "BAKE_TARGET"
            n.image = img
            for x in nt.nodes:
                x.select = False
            n.select = True
            nt.nodes.active = n

    sc.render.engine = "CYCLES"
    sc.cycles.samples = 128
    sc.render.bake.margin = 8
    for o in parts():
        o.hide_render = True                       # the originals overlap the copy: they would occlude it
    if sc.world:
        sc.world.light_settings.distance = 0.012   # occlusion reach: about half the body depth
    for o in sc.objects:
        o.select_set(False)
    j.hide_render = False
    j.select_set(True)
    bpy.context.view_layer.objects.active = j
    albedo, ao = image("bake_albedo"), image("bake_ao", True)
    target(albedo)
    sc.render.bake.use_pass_direct = False
    sc.render.bake.use_pass_indirect = False
    sc.render.bake.use_pass_color = True
    bpy.ops.object.bake(type="DIFFUSE")
    target(ao)
    bpy.ops.object.bake(type="AO")
    for img, name in ((albedo, "albedo.png"), (ao, "ao.png")):
        img.filepath_raw = os.path.join(out, name)
        img.file_format = "PNG"
        img.save()


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
    dds = os.path.join(gamedata, "textures", "item", TEX_NAME + ".dds")
    # one X-Ray material with the baked texture
    m = bpy.data.materials.get(TEX_NAME) or bpy.data.materials.new(TEX_NAME)
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
    j.data.materials.clear()
    j.data.materials.append(m)
    for p in j.data.polygons:
        p.material_index = 0
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
    with bpy.context.temp_override(active_object=rig, object=rig, selected_objects=[rig]):
        r = bpy.ops.xray_export.ogf_file(filepath=path)
    print("export", r, path)


if PHASE == "bake":  # noqa: F821 - set by the caller
    os.makedirs(OUT, exist_ok=True)  # noqa: F821
    join_copy()
    bake(sc.objects[MESH], OUT)  # noqa: F821
    render_icon(OUT)  # noqa: F821
elif PHASE == "export":  # noqa: F821
    export(GAMEDATA)  # noqa: F821
