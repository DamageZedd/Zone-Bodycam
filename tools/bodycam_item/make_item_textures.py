"""Zone Bodycam - build the bodycam item's game textures from the Blender bakes and icon render.

    py -I make_item_textures.py <albedo.png> <ao.png> <icon.png> <component gamedata dir>

Writes:
  textures\\item\\item_zbc_bodycam.dds   model texture: albedo x ambient occlusion, uncompressed BGRA with a
                                       full mip chain (DXT1 tints this near-black grey green)
  textures\\ui\\ui_icon_zbc_bodycam.dds  inventory icon: 2x2 cells (100x100 px at 50 px per cell) in the
                                       top-left of a 128x128 uncompressed RGBA texture
The bakes and the icon come from build_model.py + bake_export.py (run in Blender).
"""
import os, struct, sys
from PIL import Image, ImageChops

AO_FLOOR = 0.45          # darkest the occlusion may make a texel (keeps crevices from going pure black)
ICON_CELLS = (2, 2)      # inv_grid_width / inv_grid_height in items_zbc_bodycam.ltx
CELL_PX = 50             # vanilla inventory grid cell in texture pixels
ICON_TEX = 128

DDSD_CAPS, DDSD_HEIGHT, DDSD_WIDTH, DDSD_PITCH, DDSD_PIXELFORMAT, DDSD_MIPMAPCOUNT = 0x1, 0x2, 0x4, 0x8, 0x1000, 0x20000
DDSCAPS_COMPLEX, DDSCAPS_TEXTURE, DDSCAPS_MIPMAP = 0x8, 0x1000, 0x400000
DDPF_ALPHAPIXELS, DDPF_RGB = 0x1, 0x40


def save_bgra_mipmapped(img, path):
    img = img.convert("RGBA")
    w, h = img.size
    levels, lw, lh, level = [], w, h, img
    while True:
        levels.append(level.tobytes("raw", "BGRA"))
        if lw == 1 and lh == 1:
            break
        lw, lh = max(1, lw // 2), max(1, lh // 2)
        level = img.resize((lw, lh), Image.LANCZOS)
    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PITCH | DDSD_PIXELFORMAT | DDSD_MIPMAPCOUNT
    header = struct.pack("<4s7I44x", b"DDS ", 124, flags, h, w, w * 4, 0, len(levels))
    pixfmt = struct.pack("<2I4x5I", 32, DDPF_RGB | DDPF_ALPHAPIXELS, 32,
                         0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    caps = struct.pack("<4I4x", DDSCAPS_COMPLEX | DDSCAPS_TEXTURE | DDSCAPS_MIPMAP, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(header + pixfmt + caps)
        for lv in levels:
            f.write(lv)
    return len(levels)


def model_texture(albedo_png, ao_png, out_dds):
    albedo = Image.open(albedo_png).convert("RGB")
    ao = Image.open(ao_png).convert("L").resize(albedo.size, Image.LANCZOS)
    lo = int(AO_FLOOR * 255)
    ao = ao.point(lambda v: lo + (255 - lo) * v // 255)
    shaded = ImageChops.multiply(albedo, Image.merge("RGB", (ao, ao, ao)))
    return save_bgra_mipmapped(shaded, out_dds)


def icon_texture(icon_png, out_dds):
    icon = Image.open(icon_png).convert("RGBA")
    w, h = ICON_CELLS[0] * CELL_PX, ICON_CELLS[1] * CELL_PX
    icon = icon.resize((w, h), Image.LANCZOS)
    tex = Image.new("RGBA", (ICON_TEX, ICON_TEX), (0, 0, 0, 0))
    tex.paste(icon, (0, 0))
    tex.save(out_dds, format="DDS")


if __name__ == "__main__":
    albedo, ao, icon, gamedata = sys.argv[1:5]
    item_dir = os.path.join(gamedata, "textures", "item")
    ui_dir = os.path.join(gamedata, "textures", "ui")
    os.makedirs(item_dir, exist_ok=True)
    os.makedirs(ui_dir, exist_ok=True)
    n = model_texture(albedo, ao, os.path.join(item_dir, "item_zbc_bodycam.dds"))
    print("model texture: BGRA, %d mip levels" % n)
    icon_texture(icon, os.path.join(ui_dir, "ui_icon_zbc_bodycam.dds"))
    print("icon: %dx%d px in a %dx%d texture" % (ICON_CELLS[0] * CELL_PX, ICON_CELLS[1] * CELL_PX, ICON_TEX, ICON_TEX))
