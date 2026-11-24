r"""Zone Bodycam - build the bodycam item's game textures from the Blender output and icon render.

    py -I make_item_textures.py <bake dir> <component gamedata dir>
    py -I make_item_textures.py --atlas [<staging dir>] [<component gamedata dir>]

<bake dir> is OUT from bake_export.py (PHASE "bake"): swatches.json, one <mat>.png per baked material and
icon.png. Writes, one texture per model material (no shared atlas):
  textures\item\item_zbc_bodycam_<mat>.dds  flat materials: an 8x8 swatch of the exact colour; baked
                                             materials: their own colour bake. Uncompressed BGRA with a
                                             full mip chain (DXT1 tints near-black grey green)
  textures\ui\ui_icon_zbc_bodycam.dds       inventory icon: 2x2 cells (100x100 px at 50 px per cell) in
                                             the top-left of a 128x128 uncompressed RGBA texture, or
                                             512x128 RGBA 5-camera atlas in --atlas mode:
                                               (0,0) Body 4 | (100,0) Gen 1 | (200,0) Body 2
                                               (300,0) Body 3 | (400,0) Body 5 Pro
"""
import argparse, glob, json, os, struct, sys
from PIL import Image

SWATCH = 8               # flat-material texture size
PREFIX = "item_zbc_bodycam_"
ICON_CELLS = (2, 2)      # inv_grid_width / inv_grid_height in items_zbc_bodycam.ltx
CELL_PX = 50             # vanilla inventory grid cell in texture pixels
ICON_TEX = 128
ATLAS_TEX = (512, 128)   # 5 cameras x 100 px = 500x100 inside 512x128 power-of-two DDS

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
DEFAULT_GAMEDATA = os.path.join(REPO_ROOT, "optional", "bodycam_item", "gamedata")
DEFAULT_BACKUP_AB4 = os.path.join(SCRIPT_DIR, "icon_ab4.png")
DEFAULT_STAGING = r"C:\Users\hocke\.gemini\antigravity\brain\3c7d2180-ae6e-44e7-95c7-b88e6410200d\scratch"

ATLAS_SLOTS = (
    ("ab4", 0),
    ("ab1", 100),
    ("ab2", 200),
    ("ab3", 300),
    ("ab5", 400),
)

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


def _fit_cell_icon(img):
    img = img.convert("RGBA")
    w, h = ICON_CELLS[0] * CELL_PX, ICON_CELLS[1] * CELL_PX
    if img.size != (w, h):
        img = img.resize((w, h), Image.LANCZOS)
    return img


def icon_texture(icon_png, out_dds):
    icon = _fit_cell_icon(Image.open(icon_png))
    tex = Image.new("RGBA", (ICON_TEX, ICON_TEX), (0, 0, 0, 0))
    tex.paste(icon, (0, 0))
    tex.save(out_dds, format="DDS")


def load_or_backup_ab4_icon(out_dds, backup_png=DEFAULT_BACKUP_AB4, explicit_png=None):
    w, h = ICON_CELLS[0] * CELL_PX, ICON_CELLS[1] * CELL_PX
    if os.path.exists(out_dds) and not os.path.exists(backup_png):
        crop = Image.open(out_dds).convert("RGBA").crop((0, 0, w, h))
        os.makedirs(os.path.dirname(backup_png), exist_ok=True)
        crop.save(backup_png)
    if explicit_png:
        return _fit_cell_icon(Image.open(explicit_png))
    if os.path.exists(backup_png):
        return _fit_cell_icon(Image.open(backup_png))
    if os.path.exists(out_dds):
        return Image.open(out_dds).convert("RGBA").crop((0, 0, w, h))
    raise FileNotFoundError("Body 4 icon source not found (checked %s and %s)" % (backup_png, out_dds))


def atlas_texture(icon_paths, out_dds, backup_png=DEFAULT_BACKUP_AB4):
    ab4 = load_or_backup_ab4_icon(out_dds, backup_png=backup_png, explicit_png=icon_paths.get("ab4"))
    tex = Image.new("RGBA", ATLAS_TEX, (0, 0, 0, 0))
    for key, x0 in ATLAS_SLOTS:
        if key == "ab4":
            cell = ab4
        else:
            src = icon_paths.get(key)
            if not src or not os.path.exists(src):
                raise FileNotFoundError("Missing %s icon render: %s" % (key, src))
            cell = _fit_cell_icon(Image.open(src))
        tex.paste(cell, (x0, 0))
    os.makedirs(os.path.dirname(out_dds), exist_ok=True)
    tex.save(out_dds, format="DDS")
    return tex.size


def run_atlas_cli(argv):
    p = argparse.ArgumentParser(description="Build 512x128 5-camera UI icon DDS atlas.")
    p.add_argument("--atlas", action="store_true", help="Assemble 512x128 5-camera icon atlas")
    p.add_argument("positional", nargs="*", help="[staging_dir] [gamedata_dir]")
    p.add_argument("--staging", default=None, help="Root staging dir containing out_ab{1,2,3,5}/icon.png")
    p.add_argument("--gamedata", default=None, help="Component gamedata dir")
    p.add_argument("--out", default=None, help="Explicit output DDS path")
    p.add_argument("--backup-ab4", default=DEFAULT_BACKUP_AB4, help="Path to 100x100 Body 4 PNG backup")
    p.add_argument("--ab1", default=None, help="Explicit Gen 1 icon PNG")
    p.add_argument("--ab2", default=None, help="Explicit Body 2 icon PNG")
    p.add_argument("--ab3", default=None, help="Explicit Body 3 icon PNG")
    p.add_argument("--ab4", default=None, help="Explicit Body 4 icon PNG")
    p.add_argument("--ab5", default=None, help="Explicit Body 5 Pro icon PNG")
    args = p.parse_args(argv)

    staging = args.staging or (args.positional[0] if len(args.positional) >= 1 else DEFAULT_STAGING)
    gamedata = args.gamedata or (args.positional[1] if len(args.positional) >= 2 else DEFAULT_GAMEDATA)
    out_dds = args.out or os.path.join(gamedata, "textures", "ui", "ui_icon_zbc_bodycam.dds")

    icon_paths = {
        "ab1": args.ab1 or os.path.join(staging, "out_ab1", "icon.png"),
        "ab2": args.ab2 or os.path.join(staging, "out_ab2", "icon.png"),
        "ab3": args.ab3 or os.path.join(staging, "out_ab3", "icon.png"),
        "ab4": args.ab4,
        "ab5": args.ab5 or os.path.join(staging, "out_ab5", "icon.png"),
    }
    aw, ah = atlas_texture(icon_paths, out_dds, backup_png=args.backup_ab4)
    print("atlas: %dx%d RGBA DDS -> %s" % (aw, ah, out_dds))


if __name__ == "__main__":
    if "--atlas" in sys.argv[1:]:
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
        icon_texture(os.path.join(bake_dir, "icon.png"), os.path.join(ui_dir, "ui_icon_zbc_bodycam.dds"))
        print("icon: %dx%d px in a %dx%d texture" % (ICON_CELLS[0] * CELL_PX, ICON_CELLS[1] * CELL_PX, ICON_TEX, ICON_TEX))
