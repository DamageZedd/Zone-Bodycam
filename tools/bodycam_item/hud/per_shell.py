"""Per-camera HUD animations: fit the approved dead/insert animations to one Axon Body shell.

Headless (a COPY of the gitignored work file bodycam_hud.blend; it holds third-party GAMMA hands):
    blender -b work.blend --python tools/bodycam_item/hud/per_shell.py -- --cam <1|2|3|4|5> --out <dir> [--sheets] [--videos] [--save]

For the chosen camera:
  1. builds its shell (build_model_<N>.py; Body 4 keeps the prop already in the file) and puts it in bc_prop,
     in the same local frame (lens -Y, top +Z, mm-accurate);
  2. re-fits both right-hand grips (front: palm on the lens face, back: after the twirl) by contact
     (grip_fit.py: palm seated, fingers closed on their hinges, thumb pad touching at the spot that matches
     the Body 4 grip, scaled to this shell); the left key pinch on the battery stays (same battery);
  3. moves the battery slot (SLOT_IN) so the seated battery's bottom cap sits on the shell's bottom exactly as
     on Body 4 (the battery door), and the chest mount so the camera's back rests where Body 4's does;
  4. rebuilds both sequences (hud_anim2.build_smooth: same keys, timing and hand paths as the approved Body 4
     animation) and reports the closest hand-to-prop distance per frame (clipping) and the hand speed;
  5. --sheets renders key-pose contact sheets from the eye, --videos full playback mp4s (24 fps frames,
     30 fps file), --save writes <out>/zbc_hud_<N>.blend for the export.
"""
import argparse
import builtins
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

HUD = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HUD)
BUILDERS = {1: "build_model_1.py", 2: "build_model_2.py", 3: "build_model_3.py", 5: "build_model_5.py"}
LABEL = {1: "Axon Body 1", 2: "Axon Body 2", 3: "Axon Body 3", 4: "Axon Body 4", 5: "Axon Body 5"}
SLOT_Z4 = -0.0345           # Body 4's seated battery centre (hud_anim2.SLOT_IN): its bottom cap is flush with the
                            # camera's bottom like a battery door; every shell seats it the same way
KEYS = {"dead": [36, 44, 50, 56, 62, 65, 68, 71, 74, 82, 90, 106, 110, 130],   # where the hands are in view
        "insert": [22, 30, 44, 56, 60, 63, 66, 68, 70, 72, 74, 78, 84, 90]}
TEX_DIRS = [os.path.join(TOOLS, "..", "..", "optional", "bodycam_item", "gamedata", "textures", "item")]


def fix_textures():
    """Images saved with paths of another machine/worktree: look them up by name in the repo's item textures."""
    n = 0
    for im in bpy.data.images:
        if im.source != "FILE" or (im.filepath and os.path.exists(bpy.path.abspath(im.filepath))):
            continue
        base = os.path.basename(bpy.path.abspath(im.filepath)) or im.name
        for d in TEX_DIRS:
            p = os.path.abspath(os.path.join(d, base))
            if os.path.exists(p):
                im.filepath = p
                im.reload()
                n += 1
                break
    return n


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--cam", type=int, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--sheets", action="store_true")
    p.add_argument("--videos", action="store_true")
    p.add_argument("--closeups", action="store_true")
    p.add_argument("--save", action="store_true")
    return p.parse_args(a)


def run(name):
    path = os.path.join(HUD, name)
    g = {"__file__": path, "__name__": "__hud__"}
    exec(compile(open(path, encoding="utf-8").read(), path, "exec"), g)
    return g


def load_grips():
    d = json.load(open(os.path.join(HUD, "grips.json")))
    q = lambda v: Quaternion(v)
    builtins.GRIPS = {k: {"cam": Matrix(v["cam"]), "fingers": {n: q(r) for n, r in v["fingers"].items()}}
                      for k, v in d["grips"].items()}
    builtins.BATGRIP = Matrix(d["battery_grip_left"])
    builtins.LPINCH = {n: q(r) for n, r in d["left_pinch"].items()}
    builtins.OPEN_R = {n: q(r) for n, r in d["open_right"].items()}


def use_scene(sc):
    for w in bpy.context.window_manager.windows:
        w.scene = sc
    if bpy.context.scene != sc:
        raise RuntimeError("could not make %s the context scene (got %s)" % (sc.name, bpy.context.scene.name))


def shell_mesh(cam):
    """Builds the shell and returns one joined mesh in the shell's local frame, with its materials."""
    import bmesh
    path = os.path.join(TOOLS, BUILDERS[cam])
    sys.path.insert(0, TOOLS)
    exec(compile(open(path, encoding="utf-8").read(), path, "exec"), {"__file__": path, "__name__": "__main__"})
    sc = bpy.data.scenes["zbc_bodycam_%d" % cam]
    dg = sc.view_layers[0].depsgraph
    dg.update()
    bm = bmesh.new()
    mats = []
    for o in sc.objects:
        if o.type != "MESH" or o.hide_render or not o.data.vertices:
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        me.transform(o.matrix_world)
        remap = []
        for m in me.materials:
            if m not in mats:
                mats.append(m)
            remap.append(mats.index(m))
        for p in me.polygons:
            p.material_index = remap[p.material_index] if remap else 0
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    out = bpy.data.meshes.new("zbc_shell_%d" % cam)
    bm.to_mesh(out)
    bm.free()
    for m in mats:
        out.materials.append(m)
    return out


def bottom_under_battery(me):
    """Lowest point of the shell's bottom surface under the battery's footprint (rays straight up): where the
    battery's bottom cap meets the camera, independent of feet, bumps or bevels elsewhere on the bottom."""
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [p.vertices[:] for p in me.polygons])
    zs = []
    for i in range(13):
        for j in range(7):
            x = -0.0176 + 0.0352 * i / 12
            y = -0.0015 - 0.0055 + 0.011 * j / 6
            hit = bvh.ray_cast(Vector((x, y, -0.2)), Vector((0, 0, 1)))
            if hit[0] is not None:
                zs.append(hit[0].z)
    return min(zs)


def bounds(me):
    vs = [v.co for v in me.vertices]
    return Vector([min(v[i] for v in vs) for i in range(3)]), Vector([max(v[i] for v in vs) for i in range(3)])


def thumb_target(gf, gname, lo4, hi4, lo, hi):
    """Where the thumb pad rests on Body 4 under this grip (camera-local), mapped onto the new shell by its
    extents: the same relative spot on the surface. Must run while bc_prop is still Body 4."""
    G = builtins.GRIPS[gname]
    for n, q in G["fingers"].items():
        R.bone(n).rotation_mode = "QUATERNION"
        R.bone(n).rotation_quaternion = q
    bpy.context.view_layer.update()
    p = gf["skinned"]()
    tipm = gf["seg_verts"](gf["THUMB"][2])
    ci = np.array(G["cam"].inverted())
    t = (np.c_[p[tipm], np.ones(tipm.sum())] @ ci.T)[:, :3].mean(0)
    rel = [(t[i] - (lo4[i] + hi4[i]) / 2) / ((hi4[i] - lo4[i]) / 2) for i in range(3)]
    return [(lo[i] + hi[i]) / 2 + rel[i] * (hi[i] - lo[i]) / 2 for i in range(3)]


def main():
    a = args()
    a.out = os.path.abspath(a.out)                # Blender's render paths are not relative to the cwd
    os.makedirs(a.out, exist_ok=True)
    report = {"cam": a.cam}
    hud = bpy.data.scenes["zbc_hud"]
    use_scene(hud)
    print("[per_shell] textures relinked:", fix_textures())
    prop = hud.objects["bc_prop"]
    lo4, hi4 = bounds(prop.data)

    run("hud_rig.py")
    load_grips()
    run("clear.py")
    gf = run("grip_fit.py")
    targets = {g: thumb_target(gf, g, lo4, hi4, lo4, hi4) for g in ("front", "back")}

    if a.cam != 4:
        me = shell_mesh(a.cam)
        use_scene(hud)
        prop.data = me
        hud.objects["bc_hud"].data = me
        lo, hi = bounds(me)
        for g in targets:
            t = targets[g]
            rel = [(t[i] - (lo4[i] + hi4[i]) / 2) / ((hi4[i] - lo4[i]) / 2) for i in range(3)]
            targets[g] = [(lo[i] + hi[i]) / 2 + rel[i] * (hi[i] - lo[i]) / 2 for i in range(3)]
        run("clear.py")                       # clearance against the new shell
        gf = run("grip_fit.py")
    else:
        lo, hi = lo4, hi4
    report["shell_mm"] = [round(x * 1000, 1) for x in (*lo, *hi)]

    # grips: palm seated and fingers closed on this shell, thumb pad on the matching spot
    report["grips"] = {}
    for gname in ("front", "back"):
        fit = gf["fit"](builtins.GRIPS[gname]["cam"])
        th = gf["fit_thumb"](fit["cam"], targets[gname])
        names = list(builtins.GRIPS[gname]["fingers"])
        fingers = {n: R.bone(n).rotation_quaternion.copy() for n in names}
        d = gf["sdf"](gf["skinned"](), np.array(fit["cam"].inverted()))
        builtins.GRIPS[gname] = {"cam": fit["cam"], "fingers": fingers}
        report["grips"][gname] = {"min_mm": round(float(d.min()) * 1000, 2), "thumb_score": round(th[0], 4),
                                  "contact_mm": fit["contact_mm"]}
        print("[per_shell] grip", gname, report["grips"][gname]["min_mm"], "mm, thumb", report["grips"][gname]["thumb_score"])

    # battery slot and chest mount for this shell
    ha = run("hud_anim2.py")
    seq_insert0 = ha["seq_insert"]

    def seq_insert():
        S = seq_insert0()
        if ha.get("SOFT_PUSH"):
            S["contact"] = {c for c in S["contact"] if c[1] != "l"}
        return S
    seq_insert.__name__ = "seq_insert"
    ha["seq_insert"] = seq_insert
    # Body 4's battery sits in a real slot (its bottom cap flush with the outer bottom); the other shells are
    # solid, so the cap is placed against their bottom surface under the battery the same way
    z_seat = SLOT_Z4 if a.cam == 4 else bottom_under_battery(prop.data) + (SLOT_Z4 - lo4.z)
    ha["SLOT_IN"] = Matrix.Translation(Vector((0.0, -0.0015, z_seat)))
    ha["CHEST"] = ha["CHEST"] + Vector((0.0, hi.y - hi4.y, 0.0))
    report["slot_z_mm"] = round(z_seat * 1000, 2)

    report["frames"] = {}
    report["adjust"] = {}
    for sname, seqf in (("dead", ha["seq_dead"]), ("insert", ha["seq_insert"])):
        for attempt in range(4):
            L = ha["build_smooth"](seqf, key=True)
            pre = [f for f in range(L + 1) if (hud.frame_set(f) or True) and in_view(hud)
                   and min(hand_clear(hud, prop, s) for s in ("r", "l")) < -0.0005]
            left = declip(hud, prop, L, pre) if pre else []
            print("[per_shell]", sname, "pass %d declip: %d frames clipped, %d left" % (attempt, len(pre), len(left)))
            if not left or not adjust(hud, prop, ha, sname, left, report):
                break
        worst, speed, prev = [], 0.0, None
        for f in range(L + 1):
            hud.frame_set(f)
            P = hud.objects["cam_pivot"].matrix_world.inverted()
            row = [1.0]
            if in_view(hud):
                for side in ("r", "l"):
                    for pname, ob in (("cam", prop), ("bat", hud.objects["bat_prop"])):
                        row.append(CLEAR(side, pname, P @ ob.matrix_world))
            worst.append(min(row))
            w = (hud.objects["cam_pivot"].matrix_world @ R.world("r_hand")).to_translation()
            if prev is not None:
                speed = max(speed, (w - prev).length * 24)
            prev = w
        for suffix in ("", "_cam", "_bc_prop", "_bat_prop"):
            act = bpy.data.actions.get("zbc_bodycam_" + sname + suffix)
            if act:
                act.use_fake_user = True              # unassigned by the next sequence: keep it in the saved file
        bad = [(f, round(v * 1000, 2)) for f, v in enumerate(worst) if v < -0.0005]
        culprits = {}
        for f, _ in bad:
            hud.frame_set(f)
            culprits[f] = who_clips(hud, prop)
        report.setdefault("culprits", {})[sname] = culprits
        report["frames"][sname] = {"length": L, "min_mm": round(min(worst) * 1000, 2), "inside_frames": bad[:20],
                                   "n_inside": len(bad), "max_hand_speed_mps": round(speed, 2)}
        print("[per_shell]", sname, report["frames"][sname])
        if a.sheets:
            sheet(hud, sname, KEYS[sname], a)
        if a.closeups:
            closeups(hud, sname, a)
        if a.videos:
            video(hud, sname, L, a)

    json.dump(report, open(os.path.join(a.out, "report_%d.json" % a.cam), "w"), indent=1)
    grips_out = {k: {"cam": [list(r) for r in v["cam"]], "fingers": {n: list(q) for n, q in v["fingers"].items()}}
                 for k, v in builtins.GRIPS.items()}
    json.dump(grips_out, open(os.path.join(a.out, "grips_%d.json" % a.cam), "w"), indent=1)
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(a.out, "zbc_hud_%d.blend" % a.cam), copy=True)


CHAINS = {"r": [["bip01_r_finger%d%s" % (i, k) for k in ("", "1", "2")] for i in (1, 2, 3, 4)]
                + [["r_finger0", "r_finger01", "r_finger02"]],
          "l": [["bip01_l_finger%d%s" % (i, k) for k in ("", "1", "2")] for i in (1, 2, 3, 4)]
                + [["l_finger0", "l_finger01", "l_finger02"]]}


def hand_clear(hud, prop, side):
    P = hud.objects["cam_pivot"].matrix_world.inverted()
    return min(CLEAR(side, n, P @ ob.matrix_world) for n, ob in (("cam", prop), ("bat", hud.objects["bat_prop"])))


_MASKS = {}


def chain_clear(hud, prop, side, chain):
    """Closest signed distance (m) from one finger chain's own skin to either prop."""
    cl = builtins.CLEAR.__globals__
    key = (side, tuple(chain))
    if key not in _MASKS:
        sel, w, _ = cl["SIDE"][side]
        ids = [cl["idx"][n] for n in chain]
        _MASKS[key] = np.isin(w.argmax(1), ids)
    m = _MASKS[key]
    p = cl["skin"](side)[m]
    P = hud.objects["cam_pivot"].matrix_world.inverted()
    best = 1.0
    for pname, ob in (("cam", prop), ("bat", hud.objects["bat_prop"])):
        M = P @ ob.matrix_world
        q = (np.c_[p, np.ones(len(p))] @ np.array(M.inverted()).T)[:, :3]
        best = min(best, float(cl["signed"](pname, q).min()))
    return best


def declip(hud, prop, L, frames, sigma=2.0, rounds=3):
    """Fingers that go into a prop on these frames: each clipping finger chain is turned toward a pose that is
    clear (its fitted grip pose, or open) by the least amount that clears it; the amounts are smoothed over
    time (a dilated gaussian, so nothing pops) and the frames re-keyed. Returns the frames still clipping."""
    arm = R.arm
    gr = builtins.GRIPS
    targets = {"r": [dict(gr["front"]["fingers"]), dict(gr["back"]["fingers"]), dict(builtins.OPEN_R)],
               "l": [dict(builtins.LPINCH), {}]}
    for _ in range(rounds):
        need = {}                                     # (side, chain index, target index) -> {frame: amount}
        for f in frames:
            hud.frame_set(f)
            for side in ("r", "l"):
                if hand_clear(hud, prop, side) >= -0.0003:
                    continue
                for ci, chain in enumerate(CHAINS[side]):
                    if chain_clear(hud, prop, side, chain) >= -0.0003:
                        continue
                    base = {n: arm.pose.bones[n].rotation_quaternion.copy() for n in chain}
                    # the first target that clears this finger wins (its fitted grip before opening the hand),
                    # so neighbouring frames agree on a direction and the smoothing never mixes two of them
                    best = None
                    for ti, tgt in enumerate(targets[side]):
                        for k in range(1, 21):
                            u = k / 20.0
                            for n in chain:
                                arm.pose.bones[n].rotation_quaternion = base[n].slerp(tgt.get(n, Quaternion()), u)
                            bpy.context.view_layer.update()
                            if chain_clear(hud, prop, side, chain) >= 0.0002:
                                best = (u, ti)
                                break
                        if best:
                            break
                    for n in chain:
                        arm.pose.bones[n].rotation_quaternion = base[n]
                    bpy.context.view_layer.update()
                    if best:
                        need.setdefault((side, ci, best[1]), {})[f] = best[0]
        if not need:
            break
        for (side, ci, ti), amt in need.items():
            raw = [amt.get(f, 0.0) for f in range(L + 1)]
            dil = [max(raw[max(0, f - 2):f + 3]) for f in range(L + 1)]
            span = int(3 * sigma)
            sm = []
            for f in range(L + 1):
                acc = ws = 0.0
                for k in range(max(0, f - span), min(L, f + span) + 1):
                    wk = math.exp(-((k - f) ** 2) / (2 * sigma * sigma))
                    acc += dil[k] * wk
                    ws += wk
                sm.append(min(1.0, max(dil[f], acc / ws)))
            tgt = targets[side][ti]
            for f in range(L + 1):
                if sm[f] <= 1e-4:
                    continue
                hud.frame_set(f)
                for n in CHAINS[side][ci]:
                    pbn = arm.pose.bones[n]
                    pbn.rotation_quaternion = pbn.rotation_quaternion.slerp(tgt.get(n, Quaternion()), sm[f])
                    pbn.keyframe_insert("rotation_quaternion", frame=f)
        frames = [f for f in frames if (hud.frame_set(f) or True) and min(hand_clear(hud, prop, s) for s in ("r", "l")) < -0.0005]
        if not frames:
            break
    return frames


def in_view(hud):
    """True when the camera or the battery shows on screen this frame (clipping off screen cannot be seen)."""
    from bpy_extras.object_utils import world_to_camera_view
    cam = hud.objects["hud_cam"]
    for name in ("bc_prop", "bat_prop"):
        ob = hud.objects[name]
        for c in ob.bound_box:
            v = world_to_camera_view(hud, cam, ob.matrix_world @ Vector(c))
            if 0 <= v.x <= 1 and 0 <= v.y <= 1 and v.z > 0:
                return True
    return False


def adjust(hud, prop, ha, sname, frames, report):
    """Clipping the finger fix cannot reach. Held frames: the thenar skin follows the animated arm, so the grip
    fitted at rest can sit in the camera; the camera is moved off that spot in the hand by the depth + 0.4 mm.
    Insert, left hand: the battery is let go a little further out so the pinch clears the camera's bottom.
    Returns True when something changed (rebuild)."""
    cl = builtins.CLEAR.__globals__
    changed = False
    gr = builtins.GRIPS
    hold_frames = {"dead": {"front": range(42, 63), "back": range(74, 151)}, "insert": {"front": range(0, 100)}}[sname]
    for g, fr in hold_frames.items():
        deep, nrm = 0.0, None
        for f in frames:
            if f not in fr:
                continue
            hud.frame_set(f)
            P = hud.objects["cam_pivot"].matrix_world.inverted()
            M = P @ prop.matrix_world
            p = cl["skin"]("r")
            q = (np.c_[p, np.ones(len(p))] @ np.array(M.inverted()).T)[:, :3]
            d = cl["signed"]("cam", q)
            i = int(d.argmin())
            if d[i] < deep:
                loc, n, _, _ = cl["PROPS"]["cam"][0].find_nearest(Vector(q[i]))
                hand_inv = (M.inverted() @ R.world("r_hand")).inverted()
                deep, nrm = float(d[i]), (hand_inv.to_3x3() @ n).normalized()
        if nrm is not None and deep < -0.0005:
            gr[g]["cam"] = Matrix.Translation(-nrm * (-deep + 0.0004)) @ gr[g]["cam"]
            report["adjust"].setdefault(sname, []).append("%s grip off the thumb by %.1f mm" % (g, -deep * 1000 + 0.4))
            changed = True
    if sname == "insert" and any(62 < f <= 70 for f in frames) and not ha.get("SOFT_PUSH"):
        # the fingertip push lands on a shell whose bottom curves below the battery cap: push on the camera's
        # bottom instead of forcing contact with the cap (the hand stops where the skin meets the camera)
        ha["SOFT_PUSH"] = True
        report["adjust"].setdefault(sname, []).append("fingertips push on the camera's bottom")
        changed = True
    if sname == "insert":
        deep = 0.0
        for f in frames:
            if 40 <= f <= 62:
                hud.frame_set(f)
                P = hud.objects["cam_pivot"].matrix_world.inverted()
                deep = min(deep, CLEAR("l", "cam", P @ prop.matrix_world))
        if deep < -0.0005 and ha["INS_HOLD"] < 0.03:
            ha["INS_HOLD"] = ha["INS_HOLD"] + (-deep) + 0.001
            report["adjust"].setdefault(sname, []).append("battery let go %.1f mm out" % (ha["INS_HOLD"] * 1000))
            changed = True
    return changed


def who_clips(hud, prop):
    """For the current frame: the hand bones whose skin is inside the camera, with the deepest point (mm)."""
    cl = builtins.CLEAR.__globals__
    P = hud.objects["cam_pivot"].matrix_world.inverted()
    out = {}
    for side in ("r", "l"):
        for pname, ob in (("cam", prop), ("bat", hud.objects["bat_prop"])):
            sel, w, _ = cl["SIDE"][side]
            bone_of = [cl["names"][i] for i in w.argmax(1)]
            p = cl["skin"](side)
            M = P @ ob.matrix_world
            q = (np.c_[p, np.ones(len(p))] @ np.array(M.inverted()).T)[:, :3]
            d = cl["signed"](pname, q)
            for i in np.where(d < -0.0005)[0]:
                k = "%s/%s" % (bone_of[i], pname)
                out[k] = min(out.get(k, 0.0), round(float(d[i]) * 1000, 1))
    return out


def setup_render(sc, w, h):
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    try:
        sc.eevee.taa_render_samples = 16
    except AttributeError:
        pass
    sc.render.image_settings.file_format = "PNG"


def sheet(sc, sname, frames, a):
    """Renders the key frames, then tiles them with the system Python (Blender's has no PIL)."""
    import subprocess
    setup_render(sc, 640, 360)
    tiles = []
    for f in frames:
        sc.frame_set(f)
        p = os.path.join(a.out, "tmp_%d_%s_%03d.png" % (a.cam, sname, f))
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True, scene=sc.name)
        tiles.append((f, p))
    spec = {"title": "%s - %s (frame numbers at 24 fps)" % (LABEL[a.cam], sname), "tiles": tiles,
            "out": os.path.join(a.out, "sheet_%d_%s.png" % (a.cam, sname))}
    subprocess.run(["python", "-I", os.path.join(HUD, "tile_sheet.py"), json.dumps(spec)], check=True)


CLOSE_FRAMES = {"dead": [50, 110], "insert": [44, 68]}     # front grip, back grip / battery hold, push
CLOSE_VIEWS = (("lens side", (0.0, -1.0, 0.25)), ("back", (0.0, 1.0, 0.25)),
               ("right", (1.0, 0.0, 0.2)), ("top", (0.3, -0.5, 1.0)), ("below", (0.3, -0.4, -1.0)))
# (no left view: the forearm fills it)


def closeups(sc, sname, a):
    """Grip close-ups: the held frames rendered from several sides of the camera (directions in the camera's
    own frame: lens -Y, top +Z), each 0.28 m out, aimed at the camera's centre."""
    import subprocess
    setup_render(sc, 480, 480)
    prop = sc.objects["bc_prop"]
    cd = bpy.data.cameras.new("zbc_close")
    cd.lens, cd.clip_start = 50.0, 0.01
    cob = bpy.data.objects.new("zbc_close", cd)
    sc.collection.objects.link(cob)
    old = sc.camera
    sc.camera = cob
    tiles = []
    for f in CLOSE_FRAMES[sname]:
        sc.frame_set(f)
        M = prop.matrix_world
        c = M @ Vector([sum(v[i] for v in prop.bound_box) / 8 for i in range(3)])
        for vname, d in CLOSE_VIEWS:
            dw = (M.to_3x3() @ Vector(d)).normalized()
            cob.location = c + dw * 0.28
            up = (M.to_3x3() @ Vector((0, 0, 1))).normalized()
            if abs(dw.dot(up)) > 0.9:
                up = (M.to_3x3() @ Vector((0, -1, 0))).normalized()
            z = -dw                                   # camera looks down its -Z, image up = y
            x = z.cross(up).normalized()
            y = x.cross(z)
            cob.rotation_euler = Matrix((x, y, -z)).transposed().to_euler()
            bpy.context.view_layer.update()
            p = os.path.join(a.out, "tmpc_%d_%s_%03d_%s.png" % (a.cam, sname, f, vname.replace(" ", "")))
            sc.render.filepath = p
            bpy.ops.render.render(write_still=True, scene=sc.name)
            tiles.append(("%d %s" % (f, vname), p))
    sc.camera = old
    bpy.data.objects.remove(cob)
    spec = {"title": "%s - %s grip close-ups (frame, view)" % (LABEL[a.cam], sname), "tiles": tiles,
            "cols": len(CLOSE_VIEWS), "out": os.path.join(a.out, "close_%d_%s.png" % (a.cam, sname))}
    subprocess.run(["python", "-I", os.path.join(HUD, "tile_sheet.py"), json.dumps(spec)], check=True)


def video(sc, sname, L, a):
    import subprocess
    setup_render(sc, 960, 540)
    d = os.path.join(a.out, "frames_%d_%s" % (a.cam, sname))
    os.makedirs(d, exist_ok=True)
    for f in range(L + 1):
        sc.frame_set(f)
        sc.render.filepath = os.path.join(d, "%04d.png" % f)
        bpy.ops.render.render(write_still=True, scene=sc.name)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i", os.path.join(d, "%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
                    os.path.join(a.out, "%s_%d.mp4" % (sname, a.cam))], check=True)


main()
