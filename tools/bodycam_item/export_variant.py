"""Zone Bodycam - end-to-end headless Blender exporter for Axon Body variants 1, 2, 3, and 5.

Usage:
    blender.exe --background --python tools\\bodycam_item\\export_variant.py -- --cam <1|2|3|5> --out <scratch_out_dir>

Pipeline steps:
1. Enables `io_scene_xray` and configures `textures_folder` to `<gamedata>/textures`.
2. Executes `tools/bodycam_item/build_model_<N>.py` (`{"__file__": path, "__name__": "__main__"}`),
   creating scene `zbc_bodycam_<N>`.
3. Renders `<out_dir>/icon.png` (800x800 RGBA transparent Cycles studio icon using the exact camera
   angle, auto-framing, -0.4 exposure, and 3-point area lighting of `bake_export.py`).
4. Detects `zbc_<N>_*` materials:
   - Procedural colour materials (linked `Base Color` / `Emission Color`, `ShaderNodeTexCoord` /
     `knurl` / `dots` / bump-to-color, or listed in `BAKED`) are smart-UV-unwrapped and Cycles
     `DIFFUSE`-color-baked at 1024x1024 to `<out_dir>/zbc_<N>_*.png`.
   - Flat `zbc_<N>_*` materials get `(0.5, 0.5)` UVs and sRGB entries in `<out_dir>/swatches.json`.
   - Writes ONLY `item_zbc_bodycam_<N>_*.dds` via `save_bgra_mipmapped` (never overwriting shared
     Body 4 `item_zbc_bodycam_{body,bezel,button,disc,display,glass,gloss,grip,hole,label,led,
     lightpipe,logo,magnet,mount,rubber,screw,text}.dds`), and ensures `item_zbc_bodycam_face.dds`
     exists as an 8x8 BGRA mipmapped swatch if missing.
5. Exports World OGF `meshes/dynamics/devices/zbc_bodycam/zbc_bodycam_<N>.ogf` (1-bone `link`
   armature, `dy`, bounds box collision shape, per-camera mass `{1:0.20, 2:0.24, 3:0.30, 5:0.33}`,
   `gamemtl = "objects\\small_box"`, X-Ray `models\\model` materials).
6. Exports HUD OGF `meshes/dynamics/devices/zbc_bodycam/zbc_bodycam_<N>_hud.ogf` by importing
   `zbc_bodycam_hud.ogf` (`import_motions=True`), swapping body submeshes for `zbc_bodycam_<N>`
   weighted 1.0 to `wpn_body`, shifting `battery` submesh vertices in `+Z` if needed so at `SLOT_IN`
   (`Z = -34.5 mm`) the battery bottom stays `>= Z_BOT + 1.2 mm` inside the closed shell, binding
   Blender 5 action slots (`idle`, `zbc_bodycam_dead_item`, `zbc_bodycam_insert_item`), exporting
   (`fmt_version="cscop"`, `export_motions=True`, `hq_export=True`), patching `flags_stopatend` via
   `hud/set_stop_at_end.py`, and re-importing in an isolated headless Blender subprocess to assert
   all 3 motions, `flags_stopatend`, mass, and battery clearance pass.
"""
import argparse
import glob
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys

import addon_utils
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
DEFAULT_GAMEDATA = os.path.join(REPO_ROOT, "optional", "bodycam_item", "gamedata")
HUD_DIR = os.path.join(SCRIPT_DIR, "hud")

TEX_SIZE = 1024
SWATCH_SIZE = 8
TEX_PREFIX = "item_zbc_bodycam_"
MASS_BY_CAM = {1: 0.20, 2: 0.24, 3: 0.30, 5: 0.33}
FACE_LINEAR_RGB = (0.038, 0.039, 0.042)  # M_FACE ("zbc_face") in axon_common.py

PROTECTED_BODY4_MATS = frozenset({
    "zbc_body",
    "zbc_bezel",
    "zbc_button",
    "zbc_disc",
    "zbc_display",
    "zbc_glass",
    "zbc_gloss",
    "zbc_grip",
    "zbc_hole",
    "zbc_label",
    "zbc_led",
    "zbc_lightpipe",
    "zbc_logo",
    "zbc_magnet",
    "zbc_mount",
    "zbc_rubber",
    "zbc_screw",
    "zbc_text",
})
ALLOWED_SHARED_MATS = PROTECTED_BODY4_MATS | frozenset({"zbc_face"})

# DDS header constants matching make_item_textures.py bit-for-bit
DDSD_CAPS = 0x1
DDSD_HEIGHT = 0x2
DDSD_WIDTH = 0x4
DDSD_PITCH = 0x8
DDSD_PIXELFORMAT = 0x1000
DDSD_MIPMAPCOUNT = 0x20000
DDSCAPS_COMPLEX = 0x8
DDSCAPS_TEXTURE = 0x1000
DDSCAPS_MIPMAP = 0x400000
DDPF_ALPHAPIXELS = 0x1
DDPF_RGB = 0x40


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser(description="End-to-end Blender exporter for Axon Body camera variants.")
    p.add_argument("--cam", type=int, required=True, choices=(1, 2, 3, 5),
                   help="Camera variant number (1, 2, 3, or 5)")
    p.add_argument("--out", required=True,
                   help="Scratch output directory for icon.png, swatches.json, and baked PNGs")
    p.add_argument("--gamedata", default=DEFAULT_GAMEDATA,
                   help="Target component gamedata directory (default: optional/bodycam_item/gamedata)")
    p.add_argument("--builder", default=None,
                   help="Optional override path to build_model_<cam>.py")
    p.add_argument("--no-verify", action="store_true",
                   help="Skip isolated headless Blender re-import verification")
    return p.parse_args(argv)


def linear_to_srgb_u8(c):
    return [
        max(0, min(255, round(255.0 * (12.92 * v if v <= 0.0031308 else 1.055 * (v ** (1.0 / 2.4)) - 0.055))))
        for v in c[:3]
    ]


def save_swatch_bgra_mipmapped_pure(rgb, path, size=SWATCH_SIZE):
    """Write an uncompressed BGRA8 mipmapped flat-colour DDS identical to make_item_textures.save_bgra_mipmapped."""
    r, g, b = (int(rgb[0]) & 0xFF, int(rgb[1]) & 0xFF, int(rgb[2]) & 0xFF)
    px = bytes((b, g, r, 255))
    levels = []
    lw, lh = size, size
    while True:
        levels.append(px * (lw * lh))
        if lw == 1 and lh == 1:
            break
        lw, lh = max(1, lw // 2), max(1, lh // 2)
    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PITCH | DDSD_PIXELFORMAT | DDSD_MIPMAPCOUNT
    header = struct.pack("<4s7I44x", b"DDS ", 124, flags, size, size, size * 4, 0, len(levels))
    pixfmt = struct.pack("<2I4x5I", 32, DDPF_RGB | DDPF_ALPHAPIXELS, 32,
                         0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    caps = struct.pack("<4I4x", DDSCAPS_COMPLEX | DDSCAPS_TEXTURE | DDSCAPS_MIPMAP, 0, 0, 0)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(header + pixfmt + caps)
        for lv in levels:
            f.write(lv)
    return len(levels)


def save_png_bgra_mipmapped_fallback(png_path, dds_path):
    """Fallback BGRA8 mipmapped DDS writer using Blender's image buffer if external Python+PIL is unavailable."""
    img = bpy.data.images.load(png_path, check_existing=False)
    try:
        w, h = img.size
        levels = []
        lw, lh = w, h
        work = img.copy()
        try:
            while True:
                # Blender stores pixels bottom-to-top as linear/float RGBA depending on colorspace; set Non-Color/sRGB
                raw_f = list(work.pixels)
                buf = bytearray(lw * lh * 4)
                # Flip rows vertically (Blender row 0 is bottom; DDS row 0 is top)
                # Note: loaded PNG with default sRGB colorspace linearizes floats in `work.pixels`,
                # so convert back to sRGB u8.
                for row in range(lh):
                    src_row = lh - 1 - row
                    src_base = src_row * lw * 4
                    dst_base = row * lw * 4
                    for col_i in range(lw):
                        si = src_base + col_i * 4
                        di = dst_base + col_i * 4
                        rv, gv, bv = raw_f[si], raw_f[si + 1], raw_f[si + 2]
                        sr, sg, sb = linear_to_srgb_u8((max(0.0, rv), max(0.0, gv), max(0.0, bv)))
                        buf[di] = sb
                        buf[di + 1] = sg
                        buf[di + 2] = sr
                        buf[di + 3] = 255
                levels.append(bytes(buf))
                if lw == 1 and lh == 1:
                    break
                lw, lh = max(1, lw // 2), max(1, lh // 2)
                bpy.data.images.remove(work)
                work = img.copy()
                work.scale(lw, lh)
        finally:
            if work and work.name in bpy.data.images:
                bpy.data.images.remove(work)
    finally:
        if img and img.name in bpy.data.images:
            bpy.data.images.remove(img)

    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PITCH | DDSD_PIXELFORMAT | DDSD_MIPMAPCOUNT
    header = struct.pack("<4s7I44x", b"DDS ", 124, flags, h, w, w * 4, 0, len(levels))
    pixfmt = struct.pack("<2I4x5I", 32, DDPF_RGB | DDPF_ALPHAPIXELS, 32,
                         0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    caps = struct.pack("<4I4x", DDSCAPS_COMPLEX | DDSCAPS_TEXTURE | DDSCAPS_MIPMAP, 0, 0, 0)
    os.makedirs(os.path.dirname(dds_path), exist_ok=True)
    with open(dds_path, "wb") as f:
        f.write(header + pixfmt + caps)
        for lv in levels:
            f.write(lv)
    return len(levels)


def find_external_python_with_pil():
    for cand in ("python", "py"):
        exe = shutil.which(cand)
        if not exe:
            continue
        try:
            r = subprocess.run([exe, "-c", "import PIL"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return exe
        except Exception:
            continue
    return None


def configure_cycles_gpu(sc):
    sc.render.engine = "CYCLES"
    try:
        cprefs = bpy.context.preferences.addons["cycles"].preferences
        for dev_type in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
            try:
                cprefs.compute_device_type = dev_type
                cprefs.get_devices()
                gpus = [d for d in cprefs.devices if d.type != "CPU"]
                if gpus:
                    for d in cprefs.devices:
                        d.use = (d.type != "CPU")
                    sc.cycles.device = "GPU"
                    print(f"[export_variant] Cycles GPU enabled ({dev_type}): {[d.name for d in gpus]}")
                    return
            except Exception:
                continue
    except Exception as exc:
        print(f"[export_variant] Cycles GPU fallback to CPU: {exc}")
    sc.cycles.device = "CPU"


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def setup_studio(sc):
    """Exact 3-point studio lighting, neutral world, and camera matching bake_export.py:studio()."""
    light_specs = (
        ("key", (-0.25, -0.30, 0.25), 6.0, 0.25),
        ("fill", (0.30, -0.20, 0.05), 2.0, 0.30),
        ("rim", (0.15, 0.30, 0.25), 5.0, 0.20),
    )
    for name, loc, energy, size in light_specs:
        o = sc.objects.get(name)
        if not o:
            ld = bpy.data.lights.get(name) or bpy.data.lights.new(name, "AREA")
            o = bpy.data.objects.new(name, ld)
            sc.collection.objects.link(o)
        o.data.energy = energy
        o.data.size = size
        o.location = loc
        o.hide_render = False
        aim(o, (0.0, 0.0, 0.0))

    w = bpy.data.worlds.get("zbc_world") or bpy.data.worlds.new("zbc_world")
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.18, 0.18, 0.19, 1.0)
    bg.inputs[1].default_value = 0.6
    sc.world = w

    cam = sc.objects.get("zbc_cam")
    if not cam:
        cd = bpy.data.cameras.get("zbc_cam") or bpy.data.cameras.new("zbc_cam")
        cam = bpy.data.objects.new("zbc_cam", cd)
        sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def render_icon(sc, vl, src_parts, out_dir):
    """Render 800x800 RGBA transparent studio icon matching bake_export.py:render_icon()."""
    cam = setup_studio(sc)
    for o in src_parts:
        o.hide_render = False

    cam.data.type = "PERSP"
    cam.data.lens = 100.0
    cam.data.shift_x = 0.0
    cam.data.shift_y = 0.0
    cam.location = Vector((-0.13, -0.30, 0.07))
    aim(cam, (0.0, 0.004, -0.002))

    def bounds():
        xs, ys = [], []
        for o in src_parts:
            mw = o.matrix_world
            for v in o.data.vertices:
                p = world_to_camera_view(sc, cam, mw @ v.co)
                xs.append(p.x)
                ys.append(p.y)
        return min(xs), max(xs), min(ys), max(ys)

    vl.update()
    x0, x1, y0, y1 = bounds()
    cam.data.lens *= 0.94 / max(x1 - x0, y1 - y0)
    vl.update()
    x0, x1, y0, y1 = bounds()
    cam.data.shift_x = (x0 + x1) / 2.0 - 0.5
    cam.data.shift_y = (y0 + y1) / 2.0 - 0.5
    vl.update()

    sc.render.resolution_x = 800
    sc.render.resolution_y = 800
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.cycles.samples = 256
    sc.view_settings.exposure = -0.4
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    icon_path = os.path.join(out_dir, "icon.png")
    sc.render.filepath = icon_path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    print(f"[export_variant] Rendered studio icon: {icon_path} ({os.path.getsize(icon_path)} bytes)")
    return icon_path


def base_color(mat):
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    return bsdf.inputs["Base Color"].default_value


def is_baked_material(mat, explicit_baked):
    """Detect whether a zbc_<N>_* material has procedural colour / texture nodes or is in BAKED."""
    if mat.name in explicit_baked or bool(mat.get("baked", False)):
        return True
    if not mat.use_nodes or mat.node_tree is None:
        return False
    nodes = mat.node_tree.nodes
    bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return True
    if bsdf.inputs["Base Color"].is_linked:
        return True
    if "Emission Color" in bsdf.inputs and bsdf.inputs["Emission Color"].is_linked:
        return True
    # Catch ShaderNodeTexCoord or explicit knurl/dots labelled nodes if present
    for n in nodes:
        lbl = (n.name + " " + n.label).lower()
        if n.type == "TEX_COORD" or "knurl" in lbl or "dots" in lbl:
            return True
    return False


def with_only(sc, vl, obj, fn):
    for x in sc.objects:
        x.select_set(False)
    obj.select_set(True)
    vl.objects.active = obj
    with bpy.context.temp_override(scene=sc, view_layer=vl, active_object=obj, object=obj,
                                   selected_objects=[obj], selected_editable_objects=[obj]):
        return fn()


def join_objects(sc, vl, objs):
    if len(objs) == 1:
        return objs[0]
    for x in sc.objects:
        x.select_set(False)
    for o in objs:
        o.select_set(True)
    vl.objects.active = objs[0]
    with bpy.context.temp_override(scene=sc, view_layer=vl, active_object=objs[0], object=objs[0],
                                   selected_objects=objs, selected_editable_objects=objs):
        bpy.ops.object.join()
    return objs[0]


def bake_material_mesh(sc, vl, obj, out_dir):
    """Smart-UV-unwrap a single-material mesh over [0,1]^2 and bake 1024x1024 Cycles DIFFUSE color PNG."""
    mat = obj.data.materials[0]

    def unwrap():
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(
            angle_limit=math.radians(50),
            island_margin=0.004,
            area_weight=0.0,
            correct_aspect=True,
            scale_to_bounds=False,
        )
        bpy.ops.uv.pack_islands(margin=0.004, rotate=True)
        bpy.ops.object.mode_set(mode="OBJECT")

    with_only(sc, vl, obj, unwrap)

    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)

    # If explicitly listed in BAKED with only surface_noise bump (unlinked Base Color),
    # wire temporary subtle micro-stipple variation from the existing Noise node into Base Color
    # so Cycles DIFFUSE color pass captures the stipple rather than a flat solid fill.
    temp_nodes = []
    if bsdf is not None and not bsdf.inputs["Base Color"].is_linked:
        noise_node = next((n for n in nt.nodes if n.type == "TEX_NOISE"), None)
        if noise_node is not None:
            bc = tuple(bsdf.inputs["Base Color"].default_value[:3])
            mix_n = nt.nodes.new("ShaderNodeMix")
            mix_n.data_type = "RGBA"
            mix_n.inputs["A"].default_value = (*(max(0.0, v * 0.86) for v in bc), 1.0)
            mix_n.inputs["B"].default_value = (*(min(1.0, v * 1.14 + 0.003) for v in bc), 1.0)
            nt.links.new(noise_node.outputs["Fac"], mix_n.inputs["Factor"])
            nt.links.new(mix_n.outputs["Result"], bsdf.inputs["Base Color"])
            temp_nodes.append(mix_n)

    old_img = bpy.data.images.get("bake_" + mat.name)
    if old_img:
        bpy.data.images.remove(old_img)
    img = bpy.data.images.new("bake_" + mat.name, TEX_SIZE, TEX_SIZE, alpha=False)
    tex_node = nt.nodes.new("ShaderNodeTexImage")
    tex_node.image = img
    for x in nt.nodes:
        x.select = False
    tex_node.select = True
    nt.nodes.active = tex_node

    sc.render.engine = "CYCLES"
    sc.cycles.samples = 64
    sc.render.bake.margin = 8
    sc.render.bake.use_pass_direct = False
    sc.render.bake.use_pass_indirect = False
    sc.render.bake.use_pass_color = True

    with_only(sc, vl, obj, lambda: bpy.ops.object.bake(type="DIFFUSE"))

    nt.nodes.remove(tex_node)
    for tn in temp_nodes:
        nt.nodes.remove(tn)

    png_path = os.path.join(out_dir, mat.name + ".png")
    img.filepath_raw = png_path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    print(f"[export_variant] Baked 1024x1024 DIFFUSE PNG: {png_path} ({os.path.getsize(png_path)} bytes)")
    return png_path


def prepare_bakes_swatches_and_join(sc, vl, cam, src_parts, explicit_baked, out_dir, mesh_name):
    """Duplicate parts, bake procedural zbc_<N>_* materials, write swatches.json for flat zbc_<N>_*, and join."""
    own_prefix = f"zbc_{cam}_"
    old_joined = sc.objects.get(mesh_name)
    if old_joined:
        bpy.data.objects.remove(old_joined, do_unlink=True)

    # Remove stale zbc_<cam>_*.png files in out_dir from previous runs so retired bakes never linger
    for stale_png in glob.glob(os.path.join(out_dir, f"{own_prefix}*.png")):
        os.remove(stale_png)

    # Hide originals during baking so they do not overlap copies in Cycles
    for o in src_parts:
        o.hide_render = True

    baked_groups = {}   # mat_name -> list of duplicate single-material objects
    flat_dups = []
    swatches = {}
    used_face = False

    for o in src_parts:
        mats = [m for m in o.data.materials if m is not None]
        assert len(mats) == 1, f"Object {o.name!r} must have exactly 1 material, got {[m.name for m in mats]}"
        m = mats[0]
        if m.name == "zbc_face":
            used_face = True
        if not m.name.startswith(own_prefix) and m.name not in ALLOWED_SHARED_MATS:
            raise ValueError(
                f"Material {m.name!r} on object {o.name!r} is neither camera-scoped ({own_prefix}*) "
                f"nor an allowed shared material ({sorted(ALLOWED_SHARED_MATS)})."
            )

        d = o.copy()
        d.data = o.data.copy()
        sc.collection.objects.link(d)
        d.hide_render = False
        with_only(sc, vl, d, lambda: bpy.ops.object.transform_apply(location=True, rotation=True, scale=True))
        while d.data.uv_layers:
            d.data.uv_layers.remove(d.data.uv_layers[0])
        uv = d.data.uv_layers.new(name="uv")

        if m.name.startswith(own_prefix) and is_baked_material(m, explicit_baked):
            baked_groups.setdefault(m.name, []).append(d)
        else:
            for lp in uv.data:
                lp.uv = (0.5, 0.5)
            if m.name.startswith(own_prefix):
                swatches[m.name] = linear_to_srgb_u8(base_color(m))
            flat_dups.append(d)

    baked_dups = []
    baked_pngs = []
    for mat_name in sorted(baked_groups):
        grp_obj = join_objects(sc, vl, baked_groups[mat_name])
        grp_obj.hide_render = False
        png_path = bake_material_mesh(sc, vl, grp_obj, out_dir)
        baked_pngs.append(png_path)
        baked_dups.append(grp_obj)

    swatches_path = os.path.join(out_dir, "swatches.json")
    with open(swatches_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(swatches, f, indent=1, sort_keys=True)
    print(f"[export_variant] Wrote {swatches_path}: {len(swatches)} flat swatch(es), {len(baked_pngs)} baked PNG(s)")

    all_dups = flat_dups + baked_dups
    joined = join_objects(sc, vl, all_dups)
    joined.name = mesh_name
    joined.data.name = mesh_name
    joined.hide_render = True

    for o in src_parts:
        o.hide_render = False

    return joined, swatches, baked_pngs, used_face


def write_variant_dds_textures(cam, out_dir, swatches, baked_pngs, gamedata, ensure_face):
    """Write ONLY item_zbc_bodycam_<N>_*.dds (plus item_zbc_bodycam_face.dds if missing), never Body 4 DDS."""
    own_prefix = f"zbc_{cam}_"
    own_tex_prefix = f"{TEX_PREFIX}{cam}_"
    item_tex_dir = os.path.join(gamedata, "textures", "item")
    os.makedirs(item_tex_dir, exist_ok=True)

    # Ensure item_zbc_bodycam_face.dds exists if missing (M_FACE / zbc_face in axon_common.py)
    face_dds = os.path.join(item_tex_dir, TEX_PREFIX + "face.dds")
    if (ensure_face or not os.path.exists(face_dds)) and not os.path.exists(face_dds):
        face_mat = bpy.data.materials.get("zbc_face")
        face_rgb = linear_to_srgb_u8(base_color(face_mat)) if face_mat else linear_to_srgb_u8(FACE_LINEAR_RGB)
        save_swatch_bgra_mipmapped_pure(face_rgb, face_dds)
        print(f"[export_variant] Generated missing shared swatch: {face_dds} ({os.path.getsize(face_dds)} bytes)")

    written = []
    # 1. Flat 8x8 swatches (pure-Python exact BGRA8 mipchain — bit-for-bit identical to save_bgra_mipmapped)
    for mat_name, rgb in sorted(swatches.items()):
        assert mat_name.startswith(own_prefix), f"Refusing non-{own_prefix} swatch: {mat_name}"
        assert mat_name not in PROTECTED_BODY4_MATS, f"Refusing protected Body 4 material: {mat_name}"
        dds_name = TEX_PREFIX + mat_name.replace("zbc_", "", 1) + ".dds"
        assert dds_name.startswith(own_tex_prefix), dds_name
        dds_path = os.path.join(item_tex_dir, dds_name)
        save_swatch_bgra_mipmapped_pure(rgb, dds_path)
        written.append((dds_name, os.path.getsize(dds_path)))

    # 2. Baked 1024x1024 PNGs -> save_bgra_mipmapped (Lanczos via PIL if available, else Blender fallback)
    if baked_pngs:
        py_exe = find_external_python_with_pil()
        if py_exe:
            helper_code = (
                "import os, sys\n"
                "from PIL import Image\n"
                "sys.path.insert(0, sys.argv[1])\n"
                "from make_item_textures import save_bgra_mipmapped\n"
                "for png_p, dds_p in zip(sys.argv[2::2], sys.argv[3::2]):\n"
                "    save_bgra_mipmapped(Image.open(png_p).convert('RGB'), dds_p)\n"
            )
            pairs = []
            for png_path in baked_pngs:
                mat_name = os.path.splitext(os.path.basename(png_path))[0]
                assert mat_name.startswith(own_prefix), f"Refusing non-{own_prefix} bake: {mat_name}"
                assert mat_name not in PROTECTED_BODY4_MATS, f"Refusing protected Body 4 material: {mat_name}"
                dds_name = TEX_PREFIX + mat_name.replace("zbc_", "", 1) + ".dds"
                assert dds_name.startswith(own_tex_prefix), dds_name
                dds_path = os.path.join(item_tex_dir, dds_name)
                pairs.extend([png_path, dds_path])
                written.append((dds_name, None))
            subprocess.check_call([py_exe, "-c", helper_code, SCRIPT_DIR] + pairs)
            written = [
                (n, os.path.getsize(os.path.join(item_tex_dir, n)) if sz is None else sz)
                for n, sz in written
            ]
        else:
            for png_path in baked_pngs:
                mat_name = os.path.splitext(os.path.basename(png_path))[0]
                assert mat_name.startswith(own_prefix), f"Refusing non-{own_prefix} bake: {mat_name}"
                assert mat_name not in PROTECTED_BODY4_MATS, f"Refusing protected Body 4 material: {mat_name}"
                dds_name = TEX_PREFIX + mat_name.replace("zbc_", "", 1) + ".dds"
                assert dds_name.startswith(own_tex_prefix), dds_name
                dds_path = os.path.join(item_tex_dir, dds_name)
                save_png_bgra_mipmapped_fallback(png_path, dds_path)
                written.append((dds_name, os.path.getsize(dds_path)))

    print(f"[export_variant] Wrote {len(written)} camera-{cam} DDS texture(s): {written}")
    return written


def assign_xray_materials(mesh_obj, gamedata):
    for slot, src in enumerate(list(mesh_obj.data.materials)):
        tname = TEX_PREFIX + src.name.replace("zbc_", "", 1)
        dds_path = os.path.join(gamedata, "textures", "item", tname + ".dds")
        if not os.path.exists(dds_path):
            raise FileNotFoundError(f"Missing DDS texture required by material {src.name!r}: {dds_path}")
        m = bpy.data.materials.get(tname) or bpy.data.materials.new(tname)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        tex = nt.nodes.new("ShaderNodeTexImage")
        img = bpy.data.images.load(dds_path, check_existing=True)
        img.reload()
        tex.image = img
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        nt.links.new(bsdf.outputs[0], out.inputs[0])
        m.xray.eshader = "models\\model"
        m.xray.cshader = "default"
        m.xray.gamemtl = "objects\\small_box"
        mesh_obj.data.materials[slot] = m


def export_world_ogf(sc, vl, cam, joined_mesh, world_ogf_path):
    """Export 1-bone `link` dynamic World OGF and return an unparented copy for HUD export."""
    hud_copy = joined_mesh.copy()
    hud_copy.data = joined_mesh.data.copy()
    hud_copy.name = f"zbc_bodycam_{cam}_for_hud"

    rig_name = f"zbc_bodycam_{cam}"
    old_rig = sc.objects.get(rig_name)
    if old_rig:
        bpy.data.objects.remove(old_rig, do_unlink=True)
    ad = bpy.data.armatures.new(rig_name)
    rig = bpy.data.objects.new(rig_name, ad)
    sc.collection.objects.link(rig)
    rig.xray.isroot = True
    rig.xray.flags_simple = "dy"

    for o in sc.objects:
        o.select_set(False)
    rig.select_set(True)
    vl.objects.active = rig
    with bpy.context.temp_override(scene=sc, view_layer=vl, active_object=rig, object=rig,
                                   selected_objects=[rig], selected_editable_objects=[rig]):
        bpy.ops.object.mode_set(mode="EDIT")
        b = ad.edit_bones.new("link")
        b.head = (0.0, 0.0, 0.0)
        b.tail = (0.0, 0.0, 0.02)
        bpy.ops.object.mode_set(mode="OBJECT")

    lo = Vector([min(v.co[i] for v in joined_mesh.data.vertices) for i in range(3)])
    hi = Vector([max(v.co[i] for v in joined_mesh.data.vertices) for i in range(3)])
    bx = ad.bones["link"].xray
    bx.shape.type = "1"
    bx.shape.box_trn = (hi + lo) / 2.0
    bx.shape.box_hsz = (hi - lo) / 2.0
    bx.shape.box_rot = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    bx.mass.value = MASS_BY_CAM[cam]
    bx.gamemtl = "objects\\small_box"

    joined_mesh.hide_render = False
    joined_mesh.parent = rig
    joined_mesh.vertex_groups.clear()
    vg = joined_mesh.vertex_groups.new(name="link")
    vg.add(list(range(len(joined_mesh.data.vertices))), 1.0, "REPLACE")
    for mod in list(joined_mesh.modifiers):
        joined_mesh.modifiers.remove(mod)
    am = joined_mesh.modifiers.new("Armature", "ARMATURE")
    am.object = rig

    os.makedirs(os.path.dirname(world_ogf_path), exist_ok=True)
    for o in sc.objects:
        o.select_set(False)
    rig.select_set(True)
    vl.objects.active = rig
    # Do not pin active_object via temp_override here: io_scene_xray splits meshes in edit mode internally
    res = bpy.ops.xray_export.ogf_file(filepath=world_ogf_path)
    for o in [o for o in list(sc.objects) if o.name.startswith(joined_mesh.name + ".")]:
        bpy.data.objects.remove(o, do_unlink=True)
    print(f"[export_variant] Exported World OGF: {res} {world_ogf_path} ({os.path.getsize(world_ogf_path)} bytes)")

    bpy.data.objects.remove(joined_mesh, do_unlink=True)
    bpy.data.objects.remove(rig, do_unlink=True)
    return hud_copy


def eval_meshes_z_range_m(sc, vl, rig, act, frame, mesh_objs):
    ad = rig.animation_data or rig.animation_data_create()
    ad.action = act
    if act.slots:
        ad.action_slot = act.slots[0]
    sc.frame_set(frame)
    vl.update()
    dg = bpy.context.evaluated_depsgraph_get()
    zs = []
    for obj in mesh_objs:
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        for v in me.vertices:
            zs.append((mw @ v.co).z)
        ev.to_mesh_clear()
    return min(zs), max(zs)


def export_hud_ogf(sc, vl, cam, hud_body_mesh, build_globals, template_hud_ogf, hud_ogf_path):
    """Import zbc_bodycam_hud.ogf, swap body mesh, shift battery +Z if needed, export & patch stop_at_end."""
    if not os.path.exists(template_hud_ogf):
        raise FileNotFoundError(f"Template HUD OGF not found: {template_hud_ogf}")

    # Remove any pre-existing HUD motion actions so imported actions receive exact canonical names
    motion_names = ["idle", "zbc_bodycam_dead_item", "zbc_bodycam_insert_item"]
    for mname in motion_names:
        old_act = bpy.data.actions.get(mname)
        if old_act:
            bpy.data.actions.remove(old_act)

    before_objs = set(sc.objects)
    bpy.ops.xray_import.ogf(
        directory=os.path.dirname(template_hud_ogf),
        files=[{"name": os.path.basename(template_hud_ogf)}],
        import_motions=True,
    )
    imp_objs = [o for o in sc.objects if o not in before_objs]
    hud_rig = next(o for o in imp_objs if o.type == "ARMATURE")
    hud_rig.name = f"zbc_bodycam_{cam}_hud"
    hud_rig.data.name = f"zbc_bodycam_{cam}_hud"

    bat_meshes = []
    for o in imp_objs:
        if o.type != "MESH":
            continue
        vg_names = {vg.name for vg in o.vertex_groups}
        if "battery" in vg_names:
            bat_meshes.append(o)
        else:
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if me.users == 0:
                bpy.data.meshes.remove(me)

    if not bat_meshes:
        raise RuntimeError(f"No `battery` submeshes found in {template_hud_ogf}")

    # Compute closed shell Z_BOT (m) and shift battery submeshes in +Z if needed so seated at SLOT_IN
    # (idle f=0, Z = -34.5 mm) battery bottom stays >= Z_BOT + 1.2 mm
    mesh_z_min_m = min(v.co.z for v in hud_body_mesh.data.vertices)
    if "Z_BOT" in build_globals and isinstance(build_globals["Z_BOT"], (int, float)):
        z_bot_m = max(mesh_z_min_m, float(build_globals["Z_BOT"]) * 0.001)
    else:
        z_bot_m = mesh_z_min_m

    idle_act = bpy.data.actions["idle"]
    bat_z_min_m, bat_z_max_m = eval_meshes_z_range_m(sc, vl, hud_rig, idle_act, 0, bat_meshes)
    req_bat_z_min_m = z_bot_m + 0.0012
    dz_m = 0.0
    if bat_z_min_m < req_bat_z_min_m:
        # Add 0.05 mm safety margin above Z_BOT + 1.2 mm so float quantization never dips below threshold
        dz_m = (req_bat_z_min_m - bat_z_min_m) + 0.00005
        for o in bat_meshes:
            for v in o.data.vertices:
                v.co.z += dz_m
            o.data.update()
        new_min_m, new_max_m = eval_meshes_z_range_m(sc, vl, hud_rig, idle_act, 0, bat_meshes)
        print(
            f"[export_variant] Shifted battery submeshes +{dz_m * 1000.0:.2f} mm in +Z "
            f"(Z_BOT={z_bot_m * 1000.0:.2f} mm -> seated battery Z=[{new_min_m * 1000.0:.2f}, {new_max_m * 1000.0:.2f}] mm)"
        )
    else:
        print(
            f"[export_variant] Battery seated Z=[{bat_z_min_m * 1000.0:.2f}, {bat_z_max_m * 1000.0:.2f}] mm "
            f"already >= Z_BOT + 1.2 mm ({req_bat_z_min_m * 1000.0:.2f} mm)"
        )

    # Link & skin camera body mesh weighted 1.0 to wpn_body
    sc.collection.objects.link(hud_body_mesh)
    hud_body_mesh.name = f"zbc_bodycam_{cam}_hud_body"
    hud_body_mesh.hide_render = False
    hud_body_mesh.parent = hud_rig
    hud_body_mesh.vertex_groups.clear()
    vg_body = hud_body_mesh.vertex_groups.new(name="wpn_body")
    vg_body.add(list(range(len(hud_body_mesh.data.vertices))), 1.0, "REPLACE")
    for mod in list(hud_body_mesh.modifiers):
        hud_body_mesh.modifiers.remove(mod)
    am = hud_body_mesh.modifiers.new("Armature", "ARMATURE")
    am.object = hud_rig

    # Bind Blender 5 action slots & set X-Ray motion metadata
    ad = hud_rig.animation_data or hud_rig.animation_data_create()
    for mname in motion_names:
        act = bpy.data.actions[mname]
        act.xray.fps = 30.0
        act.xray.flags_stopatend = (mname != "idle")
        ad.action = act
        if act.slots:
            ad.action_slot = act.slots[0]
    ad.action = None
    sc.frame_set(0)
    vl.update()

    hud_rig.xray.isroot = True
    hud_rig.xray.flags_simple = "dy"
    hud_rig.xray.motions_collection.clear()
    for mname in motion_names:
        hud_rig.xray.motions_collection.add().name = mname

    os.makedirs(os.path.dirname(hud_ogf_path), exist_ok=True)
    for o in sc.objects:
        o.select_set(False)
    hud_rig.select_set(True)
    vl.objects.active = hud_rig

    res = bpy.ops.xray_export.ogf_file(
        filepath=hud_ogf_path,
        fmt_version="cscop",
        export_motions=True,
        hq_export=True,
    )
    for o in [o for o in list(sc.objects) if re.match(r".*\.\d{3}$", o.name)]:
        bpy.data.objects.remove(o, do_unlink=True)

    # Patch flags_stopatend directly via tools/bodycam_item/hud/set_stop_at_end.py
    if HUD_DIR not in sys.path:
        sys.path.insert(0, HUD_DIR)
    import set_stop_at_end
    patched = set_stop_at_end.patch(hud_ogf_path, ["zbc_bodycam_dead_item", "zbc_bodycam_insert_item"])
    for req_m in ("zbc_bodycam_dead_item", "zbc_bodycam_insert_item"):
        if req_m not in patched:
            raise RuntimeError(f"set_stop_at_end failed to locate motion {req_m!r} in {hud_ogf_path}")
    print(
        f"[export_variant] Exported HUD OGF: {res} {hud_ogf_path} "
        f"({os.path.getsize(hud_ogf_path)} bytes), stop_at_end patched: {patched}"
    )

    # Clean up HUD rig and meshes from scene
    for o in bat_meshes + [hud_body_mesh, hud_rig]:
        if o and o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)

    return z_bot_m


def verify_exported_ogfs(cam, gamedata, world_ogf_path, hud_ogf_path, z_bot_m, out_dir):
    """Re-import World & HUD OGFs in an isolated headless Blender subprocess and assert all invariants."""
    verify_py = os.path.join(out_dir, f"_verify_ab{cam}_ogfs.py")
    expected_mass = MASS_BY_CAM[cam]
    z_bot_mm = z_bot_m * 1000.0
    code = f"""import os, sys, addon_utils, bpy

GAMEDATA = {gamedata!r}
WORLD_OGF = {world_ogf_path!r}
HUD_OGF = {hud_ogf_path!r}
EXPECTED_MASS = {expected_mass!r}
Z_BOT_MM = {z_bot_mm!r}

addon_utils.enable("io_scene_xray", default_set=False)
bpy.context.preferences.addons["io_scene_xray"].preferences.textures_folder = os.path.join(GAMEDATA, "textures")

sc = bpy.context.scene
for o in list(sc.objects):
    bpy.data.objects.remove(o, do_unlink=True)

# 1. Verify World OGF
bpy.ops.xray_import.ogf(
    directory=os.path.dirname(WORLD_OGF),
    files=[{{"name": os.path.basename(WORLD_OGF)}}],
    import_motions=False,
)
w_rig = next(o for o in sc.objects if o.type == "ARMATURE")
w_meshes = [o for o in sc.objects if o.type == "MESH"]
w_verts = sum(len(o.data.vertices) for o in w_meshes)
w_tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in w_meshes)
bx = w_rig.data.bones["link"].xray
print("[verify] WORLD_OGF:", {{
    "submeshes": len(w_meshes),
    "verts": w_verts,
    "tris": w_tris,
    "mass": round(bx.mass.value, 4),
    "box_hsz_mm": [round(x * 1000.0, 2) for x in bx.shape.box_hsz],
    "gamemtl": bx.gamemtl,
}})
assert len(w_meshes) >= 1 and w_verts > 0, "Empty world OGF"
assert abs(bx.mass.value - EXPECTED_MASS) < 1e-4, f"Mass mismatch: {{bx.mass.value}} != {{EXPECTED_MASS}}"
assert bx.gamemtl == "objects\\\\small_box", bx.gamemtl

# 2. Verify HUD OGF & Motions
for o in list(sc.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for a in list(bpy.data.actions):
    bpy.data.actions.remove(a)

bpy.ops.xray_import.ogf(
    directory=os.path.dirname(HUD_OGF),
    files=[{{"name": os.path.basename(HUD_OGF)}}],
    import_motions=True,
)
h_rig = next(o for o in sc.objects if o.type == "ARMATURE")
h_meshes = [o for o in sc.objects if o.type == "MESH"]
bat_meshes = [o for o in h_meshes if any(vg.name == "battery" for vg in o.vertex_groups)]
body_meshes = [o for o in h_meshes if any(vg.name == "wpn_body" for vg in o.vertex_groups)]
assert len(bat_meshes) >= 1 and len(body_meshes) >= 1, (len(bat_meshes), len(body_meshes))

acts = {{a.name: a for a in bpy.data.actions}}
for req in ("idle", "zbc_bodycam_dead_item", "zbc_bodycam_insert_item"):
    assert req in acts, f"Missing HUD motion {{req!r}} in {{list(acts)}}"

print("[verify] HUD_MOTIONS:", [
    (n, tuple(acts[n].frame_range), acts[n].xray.fps, acts[n].xray.flags_stopatend)
    for n in ("idle", "zbc_bodycam_dead_item", "zbc_bodycam_insert_item")
])
assert acts["idle"].xray.flags_stopatend is False, "idle must loop (flags_stopatend=False)"
assert acts["zbc_bodycam_dead_item"].xray.flags_stopatend is True, "dead_item must have flags_stopatend=True"
assert acts["zbc_bodycam_insert_item"].xray.flags_stopatend is True, "insert_item must have flags_stopatend=True"
assert tuple(acts["zbc_bodycam_insert_item"].frame_range) == (0.0, 130.0), tuple(acts["zbc_bodycam_insert_item"].frame_range)

ad = h_rig.animation_data or h_rig.animation_data_create()
def bat_z_mm(act_name, frame):
    act = acts[act_name]
    ad.action = act
    if act.slots:
        ad.action_slot = act.slots[0]
    sc.frame_set(frame)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    zs = []
    for bm_obj in bat_meshes:
        ev = bm_obj.evaluated_get(dg)
        me = ev.to_mesh()
        for v in me.vertices:
            zs.append((ev.matrix_world @ v.co).z * 1000.0)
        ev.to_mesh_clear()
    return round(min(zs), 2), round(max(zs), 2)

z_idle = bat_z_mm("idle", 0)
z_dead = bat_z_mm("zbc_bodycam_dead_item", 0)
z_ins30 = bat_z_mm("zbc_bodycam_insert_item", 30)
z_ins130 = bat_z_mm("zbc_bodycam_insert_item", 130)
body_zs = [v.co.z * 1000.0 for o in body_meshes for v in o.data.vertices]
body_z_min, body_z_max = round(min(body_zs), 2), round(max(body_zs), 2)

print("[verify] HUD_BATTERY_Z_MM:", {{
    "z_bot_mm": round(Z_BOT_MM, 2),
    "body_z_span": (body_z_min, body_z_max),
    "idle": z_idle,
    "dead": z_dead,
    "insert_f30": z_ins30,
    "insert_f130": z_ins130,
}})
assert z_idle[0] >= Z_BOT_MM + 1.2 - 0.05, f"Battery protrudes at idle: {{z_idle[0]}} < {{Z_BOT_MM + 1.2}}"
assert z_idle[1] < body_z_max - 1.0, f"Battery top exceeds shell top: {{z_idle[1]}} >= {{body_z_max - 1.0}}"
assert z_ins130[0] >= Z_BOT_MM + 1.2 - 0.05, f"Battery protrudes at insert f=130: {{z_ins130[0]}}"
assert z_ins30[0] < body_z_min - 10.0, f"Battery did not withdraw at insert f=30: {{z_ins30}}"
print("[verify] ALL WORLD & HUD OGF ASSERTIONS PASSED!")
"""
    with open(verify_py, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)
    try:
        subprocess.check_call([bpy.app.binary_path, "--background", "--python", verify_py])
    finally:
        if os.path.exists(verify_py):
            os.remove(verify_py)


def main():
    args = parse_args()
    cam = args.cam
    out_dir = os.path.abspath(args.out)
    gamedata = os.path.abspath(args.gamedata)
    build_path = os.path.abspath(args.builder or os.path.join(SCRIPT_DIR, f"build_model_{cam}.py"))

    if not os.path.exists(build_path):
        raise FileNotFoundError(f"Builder script not found: {build_path}")

    os.makedirs(out_dir, exist_ok=True)

    # 1. Enable io_scene_xray and configure textures_folder
    addon_utils.enable("io_scene_xray", default_set=False)
    prefs = bpy.context.preferences.addons["io_scene_xray"].preferences
    prefs.textures_folder = os.path.join(gamedata, "textures")

    # 2. Execute build_model_<cam>.py creating scene zbc_bodycam_<cam>
    scene_name = f"zbc_bodycam_{cam}"
    print(f"[export_variant] Executing builder: {build_path}")
    build_globals = {"__file__": build_path, "__name__": "__main__"}
    with open(build_path, encoding="utf-8") as bf:
        src_code = bf.read()
    exec(compile(src_code, build_path, "exec"), build_globals)

    if scene_name not in bpy.data.scenes:
        raise RuntimeError(f"Builder did not create expected scene {scene_name!r}")
    sc = bpy.data.scenes[scene_name]
    if bpy.context.window is not None:
        bpy.context.window.scene = sc
    vl = sc.view_layers[0]

    configure_cycles_gpu(sc)

    mesh_name = f"zbc_bodycam_{cam}_mesh"
    src_parts = [
        o for o in sc.objects
        if o.type == "MESH" and o.name != mesh_name and not o.hide_render and len(o.data.vertices) > 0
    ]
    if not src_parts:
        raise RuntimeError(f"No visible mesh parts found in scene {scene_name!r}")

    explicit_baked = set(build_globals.get("BAKED", ()))

    # 3. Render 800x800 RGBA transparent studio icon BEFORE modifying materials
    render_icon(sc, vl, src_parts, out_dir)

    # 4. Bake procedural zbc_<cam>_* materials, write swatches.json, join parts, and write DDS files
    joined, swatches, baked_pngs, used_face = prepare_bakes_swatches_and_join(
        sc, vl, cam, src_parts, explicit_baked, out_dir, mesh_name
    )
    write_variant_dds_textures(cam, out_dir, swatches, baked_pngs, gamedata, ensure_face=used_face)

    # 5. Assign X-Ray materials and export World OGF + HUD OGF
    assign_xray_materials(joined, gamedata)
    ogf_dir = os.path.join(gamedata, "meshes", "dynamics", "devices", "zbc_bodycam")
    world_ogf_path = os.path.join(ogf_dir, f"zbc_bodycam_{cam}.ogf")
    hud_ogf_path = os.path.join(ogf_dir, f"zbc_bodycam_{cam}_hud.ogf")
    template_hud_ogf = os.path.join(ogf_dir, "zbc_bodycam_hud.ogf")

    hud_copy = export_world_ogf(sc, vl, cam, joined, world_ogf_path)
    z_bot_m = export_hud_ogf(sc, vl, cam, hud_copy, build_globals, template_hud_ogf, hud_ogf_path)

    # 6. Isolated re-import verification
    if not args.no_verify:
        verify_exported_ogfs(cam, gamedata, world_ogf_path, hud_ogf_path, z_bot_m, out_dir)

    print(f"[export_variant] DONE cam={cam} -> icon={os.path.join(out_dir, 'icon.png')}, world={world_ogf_path}, hud={hud_ogf_path}")


if __name__ == "__main__":
    main()
