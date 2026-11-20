r"""Zone Bodycam - build the bodycam item's game textures from the Blender output and icon render.

    py -I make_item_textures.py <bake dir> <component gamedata dir>

<bake dir> is OUT from bake_export.py (PHASE "bake"): swatches.json, one <mat>.png per baked material and
icon.png. Writes, one texture per model material (no shared atlas):
  textures\item\item_zbc_bodycam_<mat>.dds  flat materials: an 8x8 swatch of the exact colour; baked
                                             materials: their own colour bake. Uncompressed BGRA with a
                                             full mip chain (DXT1 tints near-black grey green)
  textures\ui\ui_icon_zbc_bodycam.dds       inventory icon: 2x2 cells (100x100 px at 50 px per cell) in
                                             the top-left of a 128x128 uncompressed RGBA texture
"""
import glob, json, os, struct, sys
from PIL import Image

SWATCH = 8               # flat-material texture size
PREFIX = "item_zbc_bodycam_"
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


def tex_file(item_dir, mat_name):
    return os.path.join(item_dir, PREFIX + mat_name.replace("zbc_", "") + ".dds")


def model_textures(bake_dir, item_dir):
    with open(os.path.join(bake_dir, "swatches.json"), encoding="utf-8") as f:
        swatches = json.load(f)
    written = []
    for mat, rgb in sorted(swatches.items()):
        save_bgra_mipmapped(Image.new("RGB", (SWATCH, SWATCH), tuple(rgb)), tex_file(item_dir, mat))
        written.append(mat)
    for png in sorted(glob.glob(os.path.join(bake_dir, "zbc_*.png"))):
        mat = os.path.splitext(os.path.basename(png))[0]
        save_bgra_mipmapped(Image.open(png).convert("RGB"), tex_file(item_dir, mat))
        written.append(mat)
    return written


def icon_texture(icon_png, out_dds):
    icon = Image.open(icon_png).convert("RGBA")
    w, h = ICON_CELLS[0] * CELL_PX, ICON_CELLS[1] * CELL_PX
    icon = icon.resize((w, h), Image.LANCZOS)
    tex = Image.new("RGBA", (ICON_TEX, ICON_TEX), (0, 0, 0, 0))
    tex.paste(icon, (0, 0))
    tex.save(out_dds, format="DDS")


if __name__ == "__main__":
    bake_dir, gamedata = sys.argv[1:3]
    item_dir = os.path.join(gamedata, "textures", "item")
    ui_dir = os.path.join(gamedata, "textures", "ui")
    os.makedirs(item_dir, exist_ok=True)
    os.makedirs(ui_dir, exist_ok=True)
    old = os.path.join(item_dir, "item_zbc_bodycam.dds")      # the former single shared texture
    if os.path.exists(old):
        os.remove(old)
    mats = model_textures(bake_dir, item_dir)
    print("model textures: %d (%s)" % (len(mats), ", ".join(mats)))
    icon_texture(os.path.join(bake_dir, "icon.png"), os.path.join(ui_dir, "ui_icon_zbc_bodycam.dds"))
    print("icon: %dx%d px in a %dx%d texture" % (ICON_CELLS[0] * CELL_PX, ICON_CELLS[1] * CELL_PX, ICON_TEX, ICON_TEX))
