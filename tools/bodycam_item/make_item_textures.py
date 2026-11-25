r"""Zone Bodycam - build the bodycam item's game textures from the Blender output and icon render.

    py -I make_item_textures.py <bake dir> <component gamedata dir>
    py -I make_item_textures.py --atlas [--ab1..--ab5 <icon png>] [--out <HD atlas dds>]
    py -I make_item_textures.py --atlas-1x1 [--src <HD atlas dds>] [--out <1x1 atlas dds>]

<bake dir> is OUT from bake_export.py (PHASE "bake"): swatches.json, one <mat>.png per baked material and
icon.png. Writes, one texture per model material (no shared atlas):
  textures\item\item_zbc_bodycam_<mat>.dds  flat materials: an 8x8 swatch of the exact colour; baked
                                             materials: their own colour bake. Uncompressed BGRA with a
                                             full mip chain (DXT1 tints near-black grey green)
Icons (source renders in icons\icon_ab<N>.png; refresh one by copying a new icon.png over it):
  --atlas      textures\ui\ui_icon_zbc_bodycam_hd.dds (optional/bodycam_item_hd_icons, FOMOD "HD icons"):
               512x128 RGBA, one 100x100 cell per camera = 2x2 cells at inv_grid_scale 2, i.e. one 1x1 slot
               in HD Inventory Icons Framework:
                 (0,0) Body 4 | (100,0) Gen 1 | (200,0) Body 2 | (300,0) Body 3 | (400,0) Body 5 Pro
  --atlas-1x1  textures\ui\ui_icon_zbc_bodycam.dds (optional/bodycam_item, the default 1x1 icons): cut from
               the HD atlas, 256x64, one 50x50 cell per camera
"""
import argparse, glob, json, os, struct, sys
from PIL import Image, ImageFilter

SWATCH = 8               # flat-material texture size
PREFIX = "item_zbc_bodycam_"
ICON_CELLS = (2, 2)      # HD icon: inv_grid_width / inv_grid_height in mod_system_zbc_bodycam_hd_icons.ltx
CELL_PX = 50             # vanilla inventory grid cell in texture pixels
ATLAS_TEX = (512, 128)   # 5 cameras x 100 px = 500x100 inside 512x128 power-of-two DDS

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
DEFAULT_GAMEDATA = os.path.join(REPO_ROOT, "optional", "bodycam_item", "gamedata")
DEFAULT_HD_GAMEDATA = os.path.join(REPO_ROOT, "optional", "bodycam_item_hd_icons", "gamedata")
HD_ICON_DDS = "ui_icon_zbc_bodycam_hd.dds"
ICON_1X1_DDS = "ui_icon_zbc_bodycam.dds"
# Icon renders (800x800 studio renders cropped to the camera): Body 4 from bake_export.py, the others from
# export_variant.py. Source art for both atlases.
ICON_SRC_DIR = os.path.join(SCRIPT_DIR, "icons")
HD_MARGIN = 4            # px left free on each side of a 100x100 HD cell

ATLAS_SLOTS = (
    ("ab4", 0),
    ("ab1", 100),
    ("ab2", 200),
    ("ab3", 300),
    ("ab5", 400),
)

# --atlas-1x1: the default 1x1 inventory icons (optional/bodycam_item, items_zbc_bodycam.ltx inv_grid_x 0..4).
# Same camera order as ATLAS_SLOTS, one 50x50 cell each, in a 256x64 power-of-two texture:
#   (0,0) Body 4 | (50,0) Gen 1 | (100,0) Body 2 | (150,0) Body 3 | (200,0) Body 5 Pro
ATLAS_1X1_TEX = (256, 64)
ATLAS_1X1_X = {"ab4": 0, "ab1": 50, "ab2": 100, "ab3": 150, "ab5": 200}
ATLAS_1X1_MARGIN = 2

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


def _alpha_bbox(img, threshold=8):
    return img.getchannel("A").point(lambda a: 255 if a > threshold else 0).getbbox()


def fit_icon(img, cell, margin, sharpen=False):
    """One camera in a cell x cell RGBA square: cropped to its visible pixels, fitted (aspect kept) into the
    cell less `margin` on each side, optionally lightly sharpened (alpha untouched) and centred."""
    img = img.convert("RGBA")
    bbox = _alpha_bbox(img)
    if not bbox:
        raise ValueError("icon has no visible pixels")
    img = img.crop(bbox)
    s = (cell - 2 * margin) / max(img.size)
    img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    if sharpen:
        alpha = img.getchannel("A")
        img = img.filter(ImageFilter.UnsharpMask(1, 50, 2))
        img.putalpha(alpha)
    out = Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
    out.paste(img, ((cell - img.width) // 2, (cell - img.height) // 2))
    return out


def atlas_texture(icon_paths, out_dds, margin=HD_MARGIN):
    """HD atlas: each camera's render fitted into its own 100x100 cell (ATLAS_SLOTS)."""
    tex = Image.new("RGBA", ATLAS_TEX, (0, 0, 0, 0))
    cell = ICON_CELLS[0] * CELL_PX
    for key, x0 in ATLAS_SLOTS:
        src = icon_paths.get(key)
        if not src or not os.path.exists(src):
            raise FileNotFoundError("Missing %s icon render: %s" % (key, src))
        tex.paste(fit_icon(Image.open(src), cell, margin), (x0, 0))
    os.makedirs(os.path.dirname(out_dds), exist_ok=True)
    tex.save(out_dds, format="DDS")
    return tex.size


def atlas_1x1_texture(src_atlas_dds, out_dds, margin=ATLAS_1X1_MARGIN):
    """The default 1x1 icons, cut from the HD atlas so they show exactly the same art: each 100x100 slot
    fitted into a 50x50 cell less `margin` on each side, lightly sharpened."""
    src = Image.open(src_atlas_dds).convert("RGBA")
    tex = Image.new("RGBA", ATLAS_1X1_TEX, (0, 0, 0, 0))
    for key, x0 in ATLAS_SLOTS:
        slot = src.crop((x0, 0, x0 + ICON_CELLS[0] * CELL_PX, ICON_CELLS[1] * CELL_PX))
        if not _alpha_bbox(slot):
            raise ValueError("%s slot at x=%d of %s is empty" % (key, x0, src_atlas_dds))
        tex.paste(fit_icon(slot, CELL_PX, margin, sharpen=True), (ATLAS_1X1_X[key], 0))
    os.makedirs(os.path.dirname(out_dds), exist_ok=True)
    tex.save(out_dds, format="DDS")
    return tex.size


def run_atlas_1x1_cli(argv):
    p = argparse.ArgumentParser(description="Build the 256x64 1x1 icon atlas from the HD 2x2-cell atlas.")
    p.add_argument("--atlas-1x1", action="store_true")
    p.add_argument("--src", default=os.path.join(DEFAULT_HD_GAMEDATA, "textures", "ui", HD_ICON_DDS))
    p.add_argument("--out", default=os.path.join(DEFAULT_GAMEDATA, "textures", "ui", ICON_1X1_DDS))
    args = p.parse_args(argv)
    aw, ah = atlas_1x1_texture(args.src, args.out)
    print("1x1 atlas: %dx%d RGBA DDS -> %s" % (aw, ah, args.out))


def run_atlas_cli(argv):
    p = argparse.ArgumentParser(description="Build the 512x128 5-camera HD icon atlas.")
    p.add_argument("--atlas", action="store_true", help="Assemble the 512x128 5-camera HD icon atlas")
    p.add_argument("--out", default=os.path.join(DEFAULT_HD_GAMEDATA, "textures", "ui", HD_ICON_DDS),
                   help="Output DDS path")
    for key, label in (("ab1", "Gen 1"), ("ab2", "Body 2"), ("ab3", "Body 3"), ("ab4", "Body 4"), ("ab5", "Body 5 Pro")):
        p.add_argument("--" + key, default=os.path.join(ICON_SRC_DIR, "icon_%s.png" % key),
                       help="%s icon render (default: icons\\icon_%s.png)" % (label, key))
    args = p.parse_args(argv)
    icon_paths = {key: getattr(args, key) for key, _ in ATLAS_SLOTS}
    aw, ah = atlas_texture(icon_paths, args.out)
    print("atlas: %dx%d RGBA DDS -> %s" % (aw, ah, args.out))


if __name__ == "__main__":
    if "--atlas-1x1" in sys.argv[1:]:
        run_atlas_1x1_cli(sys.argv[1:])
    elif "--atlas" in sys.argv[1:]:
        run_atlas_cli(sys.argv[1:])
    else:
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
        print("icon: not written here; copy %s over icons\\icon_<cam>.png, then run --atlas and --atlas-1x1"
              % os.path.join(bake_dir, "icon.png"))
