"""Per-camera HUD export: writes the game files of one approved per-shell animation (per_shell.py --save).

Headless, on the blend per_shell.py saved for that camera:
    blender -b zbc_hud_<N>.blend --python tools/bodycam_item/hud/export_shell.py -- --cam <1..5> --out <scratch dir>

Uses the baked actions in the file as they are (never rebuilds: the grip fits and clipping fixes live only in
those keys). Writes into optional/bodycam_item/gamedata:
  Body 4  meshes\\anomaly_weapons\\hud_hands_animation\\zbc_bodycam_hud_animation.omf   zbc_bodycam_dead / _insert
          meshes\\dynamics\\devices\\zbc_bodycam\\zbc_bodycam_hud.ogf                     idle + *_item motions
          anims\\camera_effects\\zbc\\zbc_bodycam_<dead|insert>.anm                       view pitch
  Body N  meshes\\anomaly_weapons\\hud_hands_animation\\zbc_bodycam_<N>_hud_animation.omf zbc_bodycam_<N>_dead / _insert
          meshes\\dynamics\\devices\\zbc_bodycam\\zbc_bodycam_<N>_hud.ogf  (the exported model, its motions
          replaced; the battery submesh put back on Body 4's battery and seated per this shell)
The view pitch is shared: for Body N the .anm is exported to <out> and compared with Body 4's (reported).
Every file is checked by re-import; <out>/export_<N>.json holds the report. Raises on any failed check.
"""
import argparse
import json
import os
import re
import sys

import bpy
from mathutils import Matrix, Vector

HUD = os.path.dirname(os.path.abspath(__file__))
GD = os.path.normpath(os.path.join(HUD, "..", "..", "..", "optional", "bodycam_item", "gamedata"))
DEV = os.path.join(GD, "meshes", "dynamics", "devices", "zbc_bodycam")
SEQS = (("dead", 170), ("insert", 130))
SLOT_IN4 = Matrix.Translation(Vector((0.0, -0.0015, -0.0345)))   # where the item rig's battery rest pose sits
CAP_INSET = 0.0003          # a battery cap that would be coplanar with a solid shell's bottom sits this far inside
REPORT = {}

if HUD not in sys.path:
    sys.path.insert(0, HUD)
import set_stop_at_end  # noqa: E402


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--cam", type=int, required=True, choices=(1, 2, 3, 4, 5))
    p.add_argument("--out", required=True)
    return p.parse_args(a)


def bind(obj, action):
    ad = obj.animation_data or obj.animation_data_create()
    ad.action = action
    if action and action.slots:
        ad.action_slot = action.slots[0]
    return ad


def use_scene(sc):
    for w in bpy.context.window_manager.windows:
        w.scene = sc


def select_only(sc, ob):
    for o in sc.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def hand_names(cam):
    return {t: ("zbc_bodycam_%s" % t if cam == 4 else "zbc_bodycam_%d_%s" % (cam, t)) for t, _ in SEQS}


def battery_rel():
    """Battery pose relative to the camera per frame, from the baked prop keys (= hud_anim2.BATREL)."""
    sc = bpy.data.scenes["zbc_hud"]
    use_scene(sc)
    prop, bat = sc.objects["bc_prop"], sc.objects["bat_prop"]
    rels = {}
    for t, L in SEQS:
        bind(prop, bpy.data.actions["zbc_bodycam_%s_bc_prop" % t])
        bind(bat, bpy.data.actions["zbc_bodycam_%s_bat_prop" % t])
        rels[t] = {}
        for f in range(L + 1):
            sc.frame_set(f)
            rels[t][f] = prop.matrix_world.inverted() @ bat.matrix_world
    return rels


def export_hands(cam):
    sc = bpy.data.scenes["zbc_hud"]
    use_scene(sc)
    arm = R.arm  # noqa: F821
    names = hand_names(cam)
    for t, _ in SEQS:
        a = bpy.data.actions["zbc_bodycam_" + t]
        a.name = names[t]                     # the motion name in the OMF is the action name
        a.xray.flags_stopatend = True         # else the engine loops it and get_motion_length returns 0
        a.xray.fps = 30
        bind(arm, a)
    bind(arm, None)
    d = os.path.join(GD, "meshes", "anomaly_weapons", "hud_hands_animation")
    out = os.path.join(d, "zbc_bodycam_hud_animation.omf" if cam == 4 else "zbc_bodycam_%d_hud_animation.omf" % cam)
    arm.xray.motions_collection.clear()
    for t, _ in SEQS:
        arm.xray.motions_collection.add().name = names[t]
    R.reset()  # noqa: F821
    select_only(sc, arm)
    bpy.ops.xray_export.omf_file(filepath=out, fmt_ver="cscop", export_mode="OVERWRITE", export_motions=True,
                                 export_bone_parts=True, high_quality=True)
    patched = set_stop_at_end.patch(out, list(names.values()))
    before = set(bpy.data.actions)
    bpy.ops.xray_import.omf(directory=d, files=[{"name": os.path.basename(out)}], import_motions=True,
                            import_bone_parts=False, add_to_motion_list=False)
    new = [a for a in bpy.data.actions if a not in before]
    rep = {"file": out, "bytes": os.path.getsize(out), "stop_at_end_patched": sorted(patched)}
    for t, L in SEQS:
        n = names[t]
        imp = next((a for a in new if a.name.startswith(n + ".")), None)
        if imp is None:
            raise RuntimeError("motion %s missing from %s" % (n, out))
        worst = 0.0
        for f in range(L + 1):
            rows = []
            for a in (bpy.data.actions[n], imp):
                bind(arm, a)
                sc.frame_set(f)
                rows.append({b.name: b.matrix.translation.copy() for b in arm.pose.bones})
            worst = max(worst, max((rows[0][b] - rows[1][b]).length for b in rows[0]))
        rep[n] = {"frames": list(imp.frame_range), "max_bone_error_mm": round(worst * 1000, 3),
                  "stop_at_end": bool(imp.xray.flags_stopatend)}
        if worst > 0.0005:
            raise RuntimeError("%s re-import differs by %.2f mm" % (n, worst * 1000))
    for a in new:
        bpy.data.actions.remove(a)
    bind(arm, None)
    REPORT["hands"] = rep


def export_anm(cam, outdir):
    sc = bpy.data.scenes["zbc_hud"]
    use_scene(sc)
    shared = os.path.join(GD, "anims", "camera_effects", "zbc")
    rep = {}
    for t, _ in SEQS:
        n = "zbc_bodycam_" + t
        o = bpy.data.objects.new(n + "_anm", None)
        sc.collection.objects.link(o)
        a = bpy.data.actions[n + "_cam"]
        a.xray.fps = 30
        bind(o, a)
        select_only(sc, o)
        p = os.path.join(shared if cam == 4 else outdir, n + ".anm")
        bpy.ops.xray_export.anm_file(filepath=p, format_version="5")
        bpy.data.objects.remove(o, do_unlink=True)
        ref = os.path.join(shared, n + ".anm")
        rep[t] = {"file": p, "same_as_body4": open(p, "rb").read() == open(ref, "rb").read()}
    REPORT["anm"] = rep


def make_motions(rig, rels, seat):
    """idle (seated) + one item motion per sequence: the battery bone follows the battery, the body stays."""
    pbat, pbody = rig.pose.bones["battery"], rig.pose.bones["wpn_body"]
    restb = rig.data.bones["battery"].matrix_local
    names = ["idle"] + ["zbc_bodycam_%s_item" % t for t, _ in SEQS]
    for n in names:
        old = bpy.data.actions.get(n)
        if old:
            bpy.data.actions.remove(old)
    for n, rel, L in [("idle", {0: seat, 1: seat}, 1)] + [("zbc_bodycam_%s_item" % t, rels[t], L) for t, L in SEQS]:
        a = bpy.data.actions.new(n)
        a.xray.fps = 30
        a.xray.flags_stopatend = n != "idle"
        bind(rig, a)
        for f in range(L + 1):
            pbody.matrix_basis = Matrix()
            bpy.context.view_layer.update()
            pbat.matrix = rel[f] @ SLOT_IN4.inverted() @ restb
            bpy.context.view_layer.update()
            for p in (pbody, pbat):
                p.keyframe_insert("location", frame=f, group=p.name)
                p.keyframe_insert("rotation_quaternion", frame=f, group=p.name)
    bind(rig, None)
    rig.xray.isroot = True
    rig.xray.motions_collection.clear()
    for n in names:
        rig.xray.motions_collection.add().name = n
    return names


def import_ogf(sc, path, motions):
    before = set(sc.objects)
    bpy.ops.xray_import.ogf(directory=os.path.dirname(path), files=[{"name": os.path.basename(path)}],
                            import_motions=motions)
    objs = [o for o in sc.objects if o not in before]
    return next(o for o in objs if o.type == "ARMATURE"), [o for o in objs if o.type == "MESH"]


def is_battery(o):
    return "battery" in {g.name for g in o.vertex_groups}


def min_z(objs):
    return min(v.co.z for o in objs for v in o.data.vertices)


def shell_bottom_under_battery(body):
    """Lowest shell surface under the battery's footprint (rays straight up), like per_shell.bottom_under_battery."""
    from mathutils.bvhtree import BVHTree
    verts, polys = [], []
    for o in body:
        k = len(verts)
        verts += [v.co.copy() for v in o.data.vertices]
        polys += [[k + i for i in p.vertices] for p in o.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys)
    zs = []
    for i in range(13):
        for j in range(7):
            hit = bvh.ray_cast(Vector((-0.0176 + 0.0352 * i / 12, -0.007 + 0.011 * j / 6, -0.2)), Vector((0, 0, 1)))
            if hit[0] is not None:
                zs.append(hit[0].z)
    return min(zs)


def export_item(cam, rels):
    sc = bpy.data.scenes["zbc_item_hud"]
    use_scene(sc)
    seat = rels["insert"][max(rels["insert"])]          # where the battery ends up (the shell's seat)
    rep = {"seat_mm": [round(x * 1000, 2) for x in seat.to_translation()]}
    if cam == 4:
        rig = sc.objects["zbc_bodycam_hud"]
        out = os.path.join(DEV, "zbc_bodycam_hud.ogf")
        temp = []
    else:
        # the shipped model of this camera (body + battery submeshes); its battery was shifted up by the old
        # exporter: put it back on Body 4's battery (same part), then seat it the way this shell's animation does
        out = os.path.join(DEV, "zbc_bodycam_%d_hud.ogf" % cam)
        rig4, m4 = import_ogf(sc, os.path.join(DEV, "zbc_bodycam_hud.ogf"), False)
        bat4_z = min_z([o for o in m4 if is_battery(o)])
        for o in m4 + [rig4]:
            bpy.data.objects.remove(o, do_unlink=True)
        rig, meshes = import_ogf(sc, out, False)
        bats = [o for o in meshes if is_battery(o)]
        body = [o for o in meshes if not is_battery(o)]
        old_dz = min_z(bats) - bat4_z
        cap = bat4_z + (seat.translation.z - SLOT_IN4.translation.z)     # seated cap height, Body 4 battery
        floor = shell_bottom_under_battery(body)
        # as on Body 4 the cap stands proud of the bottom (a battery door); only a cap that would be coplanar with
        # the shell's bottom (z-fighting) is moved inside
        inset = (floor + CAP_INSET - cap) if abs(cap - floor) < CAP_INSET else 0.0
        for o in bats:
            for v in o.data.vertices:
                v.co.z += inset - old_dz
            o.data.update()
        rep.update({"old_battery_shift_mm": round(old_dz * 1000, 2), "shell_floor_mm": round(floor * 1000, 2),
                    "cap_mm": round((cap + inset) * 1000, 2), "cap_inset_mm": round(inset * 1000, 2)})
        rig.xray.flags_simple = "dy"
        temp = meshes + [rig]
    names = make_motions(rig, rels, seat)
    select_only(sc, rig)
    bpy.ops.xray_export.ogf_file(filepath=out, fmt_version="cscop", export_motions=True, hq_export=True)
    patched = set_stop_at_end.patch(out, names[1:])
    for o in [o for o in sc.objects if re.match(r".*\.\d{3}$", o.name)]:
        bpy.data.objects.remove(o, do_unlink=True)
    for o in temp:
        bpy.data.objects.remove(o, do_unlink=True)
    rep.update({"file": out, "bytes": os.path.getsize(out), "stop_at_end_patched": sorted(patched)})

    # re-import: every motion there, battery bone where the animation puts it
    keep = {n: bpy.data.actions[n] for n in names}
    for n, a in keep.items():
        a.name = n + "__src"
    rig2, m2 = import_ogf(sc, out, True)
    pb = rig2.pose.bones["battery"]
    restb = rig2.data.bones["battery"].matrix_local
    worst = 0.0
    for n in names[1:]:
        imp = bpy.data.actions.get(n)
        if imp is None:
            raise RuntimeError("item motion %s missing from %s" % (n, out))
        t = n.split("_")[2]
        bind(rig2, imp)
        for f in range(0, max(rels[t]) + 1, 5):
            sc.frame_set(f)
            want = rels[t][f] @ SLOT_IN4.inverted() @ restb
            worst = max(worst, (pb.matrix.translation - want.translation).length)
    rep["battery_reimport_error_mm"] = round(worst * 1000, 3)
    if worst > 0.0005:
        raise RuntimeError("item battery re-import differs by %.2f mm" % (worst * 1000))
    for o in m2 + [rig2]:
        bpy.data.objects.remove(o, do_unlink=True)
    for n, a in keep.items():
        if bpy.data.actions.get(n):
            bpy.data.actions.remove(bpy.data.actions[n])
        a.name = n
    REPORT["item"] = rep


def main():
    a = args()
    a.out = os.path.abspath(a.out)
    os.makedirs(a.out, exist_ok=True)
    REPORT["cam"] = a.cam
    exec(compile(open(os.path.join(HUD, "hud_rig.py"), encoding="utf-8").read(), "hud_rig.py", "exec"),
         {"__name__": "__hud__"})
    rels = battery_rel()
    export_anm(a.cam, a.out)
    export_hands(a.cam)
    export_item(a.cam, rels)
    p = os.path.join(a.out, "export_%d.json" % a.cam)
    json.dump(REPORT, open(p, "w"), indent=1)
    print("[export_shell] OK", json.dumps(REPORT))


main()
