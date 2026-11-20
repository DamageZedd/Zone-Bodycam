"""Bodycam HUD animations: rebuild both sequences and export every game file, each checked by re-import.

exec() in Blender (scene zbc_hud set up, hud_rig.py, clear.py, grip fits in builtins). Globals: GD = the
component's gamedata folder, SCR_DIR = folder holding hud_anim2.py. Writes:
  meshes\\anomaly_weapons\\hud_hands_animation\\zbc_bodycam_hud_animation.omf   hand motions (all hand models load it)
  meshes\\dynamics\\devices\\zbc_bodycam\\zbc_bodycam_hud.ogf                     in-hand item: body + battery bone, motions
  anims\\camera_effects\\zbc\\zbc_bodycam_dead.anm, zbc_bodycam_insert.anm         view pitch (camera effectors)
Blender 5 note: an action only exports when the object's last action slot matches it, so each export binds
the slot first; a re-import drops animation_data, so it is recreated before use.
"""
import os
import re
import bpy
from mathutils import Matrix, Vector

SEQS = (("dead", 170), ("insert", 130))
REPORT = []


def say(*a):
    REPORT.append(" ".join(str(x) for x in a))


def bind(obj, action):
    ad = obj.animation_data or obj.animation_data_create()
    ad.action = action
    if action and action.slots:
        ad.action_slot = action.slots[0]
    return ad


def rebuild():
    exec(open(os.path.join(SCR_DIR, "hud_anim2.py"), encoding="utf-8").read(), {"__name__": "ha2"})  # noqa: F821
    rels = {}
    for tag, _ in SEQS:
        HA2["build_smooth"](HA2["seq_" + tag], key=True)  # noqa: F821
        rels[tag] = {k: v.copy() for k, v in HA2["BATREL"].items()}  # noqa: F821
    return rels


def export_hands():
    sc = bpy.data.scenes["zbc_hud"]
    bpy.context.window.scene = sc
    arm = R.arm  # noqa: F821
    d = os.path.join(GD, "meshes", "anomaly_weapons", "hud_hands_animation")  # noqa: F821
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, "zbc_bodycam_hud_animation.omf")
    names = ["zbc_bodycam_" + t for t, _ in SEQS]
    for n in names:
        # stop at end: without it the engine treats the motion as a loop, never ends the script
        # animation and returns length 0 to game.get_motion_length
        bpy.data.actions[n].xray.flags_stopatend = True
        bpy.data.actions[n].xray.fps = 30
        bind(arm, bpy.data.actions[n])
    bind(arm, None)
    saved = [m.name for m in arm.xray.motions_collection]
    arm.xray.motions_collection.clear()
    for n in names:
        arm.xray.motions_collection.add().name = n
    R.reset()  # noqa: F821
    for o in sc.objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.xray_export.omf_file(filepath=out, fmt_ver="cscop", export_mode="OVERWRITE", export_motions=True,
                                 export_bone_parts=True, high_quality=True)
    arm.xray.motions_collection.clear()
    for n in saved:
        arm.xray.motions_collection.add().name = n
    before = set(bpy.data.actions)
    bpy.ops.xray_import.omf(directory=d, files=[{"name": os.path.basename(out)}], import_motions=True,
                            import_bone_parts=False, add_to_motion_list=False)
    new = [a for a in bpy.data.actions if a not in before]
    for (t, L), n in zip(SEQS, names):
        imp = next(a for a in new if a.name.startswith(n + "."))
        worst = 0.0
        for f in range(L + 1):
            rows = []
            for a in (bpy.data.actions[n], imp):
                bind(arm, a)
                sc.frame_set(f)
                rows.append({b.name: b.matrix.translation.copy() for b in arm.pose.bones})
            for b in rows[0]:
                worst = max(worst, (rows[0][b] - rows[1][b]).length)
        say("hands", n, "frames", tuple(imp.frame_range), "max bone error mm", round(worst * 1000, 3),
            "stop at end", imp.xray.flags_stopatend)
    for a in new:
        bpy.data.actions.remove(a)
    bind(arm, None)
    say("hands file", out, os.path.getsize(out))


def export_item(rels):
    sc = bpy.data.scenes["zbc_item_hud"]
    bpy.context.window.scene = sc
    rig = sc.objects["zbc_bodycam_hud"]
    slot_in = Matrix.Translation(Vector((0.0, -0.0015, -0.0345)))
    pbat, pbody = rig.pose.bones["battery"], rig.pose.bones["wpn_body"]
    restb = rig.data.bones["battery"].matrix_local

    def make(name, rel, L):
        a = bpy.data.actions.get(name)
        if a:
            bpy.data.actions.remove(a)
        a = bpy.data.actions.new(name)
        a.xray.fps = 30
        a.xray.flags_stopatend = name != "idle"
        bind(rig, a)
        for f in range(L + 1):
            pbody.matrix_basis = Matrix()
            bpy.context.view_layer.update()
            pbat.matrix = rel[f] @ slot_in.inverted() @ restb
            bpy.context.view_layer.update()
            for p in (pbody, pbat):
                p.keyframe_insert("location", frame=f, group=p.name)
                p.keyframe_insert("rotation_quaternion", frame=f, group=p.name)
    make("idle", {0: slot_in.copy(), 1: slot_in.copy()}, 1)
    for t, L in SEQS:
        make("zbc_bodycam_%s_item" % t, rels[t], L)
    bind(rig, bpy.data.actions["idle"])
    bind(rig, None)
    rig.xray.isroot = True
    rig.xray.motions_collection.clear()
    for n in ["idle"] + ["zbc_bodycam_%s_item" % t for t, _ in SEQS]:
        rig.xray.motions_collection.add().name = n
    for o in sc.objects:
        o.select_set(False)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    out = os.path.join(GD, "meshes", "dynamics", "devices", "zbc_bodycam", "zbc_bodycam_hud.ogf")  # noqa: F821
    bpy.ops.xray_export.ogf_file(filepath=out, fmt_version="cscop", export_motions=True, hq_export=True)
    for o in [o for o in sc.objects if re.match(r".*\.\d{3}$", o.name)]:
        bpy.data.objects.remove(o, do_unlink=True)
    data = open(out, "rb").read()
    say("item file", out, len(data), "motions",
        [n.decode() for n in (b"idle", b"zbc_bodycam_dead_item", b"zbc_bodycam_insert_item") if n in data])


def export_anm():
    sc = bpy.data.scenes["zbc_hud"]
    bpy.context.window.scene = sc
    outd = os.path.join(GD, "anims", "camera_effects", "zbc")  # noqa: F821
    os.makedirs(outd, exist_ok=True)
    for t, _ in SEQS:
        n = "zbc_bodycam_" + t
        old = bpy.data.objects.get(n)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        o = bpy.data.objects.new(n, None)
        sc.collection.objects.link(o)
        a = bpy.data.actions[n + "_cam"]
        a.xray.fps = 30
        bind(o, a)
        for x in sc.objects:
            x.select_set(False)
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        p = os.path.join(outd, n + ".anm")
        bpy.ops.xray_export.anm_file(filepath=p, format_version="5")
        bpy.data.objects.remove(o, do_unlink=True)
        say("anm", p, os.path.getsize(p))


def run():
    del REPORT[:]
    rels = rebuild()
    export_hands()
    export_item(rels)
    export_anm()
    bpy.context.window.scene = bpy.data.scenes["zbc_hud"]
    return REPORT
