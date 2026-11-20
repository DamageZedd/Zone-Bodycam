"""Fit the right-hand grip on the bodycam by contact (exec in Blender after hud_rig.py; uses builtins.R).

The camera is a rounded box (its real outer bounds). Everything is computed in the r_hand bone's space with
the arm at rest. Skinned positions are evaluated with linear blend skinning from the pose matrices, so only
the finger vertices are moved per step. Result: builtins.LGRIP_FIT = {"cam": Matrix (hand-local camera),
"fingers": {bone: Quaternion}} and a report of the closest distance per segment (mm, negative = inside).
"""
import builtins
import math
import numpy as np
import bpy
from mathutils import Matrix, Vector, Quaternion

SC = bpy.data.scenes["zbc_hud"]
HM = SC.objects["wpn_hand_loner_novice.ogf 00"]
LO = np.array([-0.0188, -0.0063, -0.0150])
HI = np.array([0.0188, 0.0063, 0.0150])
RAD = 0.003                                   # body corner radius
GAP = 0.0006                                  # skin rests this far off the surface (no z-fight, no float)
FINGERS = [["bip01_l_finger%d%s" % (i, s) for s in ("", "1", "2")] for i in (1, 2, 3, 4)]
THUMB = ["l_finger0", "l_finger01", "l_finger02"]
LIMITS = [math.radians(a) for a in (90, 100)]     # knuckle, middle joint (tip is coupled)
THUMB_LIMITS = [math.radians(a) for a in (45, 60, 70)]

arm = R.arm
pb = arm.pose.bones
names = [b.name for b in arm.data.bones]
idx = {n: i for i, n in enumerate(names)}

vg = {g.index: g.name for g in HM.vertex_groups}
rest_co = np.array([v.co[:] for v in HM.data.vertices])
W = np.zeros((len(HM.data.vertices), len(names)))
for v in HM.data.vertices:
    for g in v.groups:
        n = vg.get(g.group)
        if n in idx:
            W[v.index, idx[n]] = g.weight
W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
right = [idx[n] for n in sum(FINGERS, []) + THUMB + ["l_hand"]]
sel = np.where(W[:, right].sum(1) > 0.5)[0]
Wsel = W[sel]
rest_h = np.c_[rest_co[sel], np.ones(len(sel))]
rest_inv = [np.array(arm.data.bones[n].matrix_local.inverted()) for n in names]


def skinned():
    """Selected vertex positions in r_hand bone space for the current pose."""
    acc = np.zeros((len(sel), 4))
    used = np.where(Wsel.sum(0) > 0)[0]
    for j in used:
        m = np.array(pb[names[j]].matrix) @ rest_inv[j]
        acc += Wsel[:, j:j + 1] * (rest_h @ m.T)
    hi = np.array(pb["l_hand"].matrix.inverted())
    return (acc @ hi.T)[:, :3]


from mathutils.bvhtree import BVHTree
_cm = SC.objects["bat_prop"].data
BVH = BVHTree.FromPolygons([v.co.copy() for v in _cm.vertices], [p.vertices[:] for p in _cm.polygons])


def sdf(p, cam_inv):
    """Signed distance to the prop (solid convex-hull inside test from clear.py); p in hand space."""
    q = (np.c_[p, np.ones(len(p))] @ cam_inv.T)[:, :3]
    return builtins.PROP_SIGNED("bat", q)


def seg_verts(bone):
    return Wsel[:, idx[bone]] > 0.5


def chain_mask(chain, k):
    m = np.zeros(len(sel), bool)
    for b in chain[k:]:
        m |= seg_verts(b)
    return m


HINGE = {}


def compute_hinges():
    """Anatomical hinge per joint, from the rest pose's own bend plane (segment k x segment k+1), as a
    bone-basis axis. Positive angles always flex (curl towards the palm side the rest pose bends to).
    Call with every finger at identity."""
    pts = skinned()
    hi = pb["l_hand"].matrix.inverted()
    for ch in FINGERS + [THUMB]:
        heads = [hi @ pb[b].head for b in ch]
        tip = Vector(pts[seg_verts(ch[-1])].mean(0))
        far = heads[-1] + (tip - heads[-1]) * 2.0
        segs = [heads[1] - heads[0], heads[2] - heads[1], far - heads[2]]
        n = Vector((0, 0, 0))
        for k in range(2):
            n += segs[k].cross(segs[k + 1])
        n.normalize()                                # one hinge direction for the whole finger (planar curl)
        for k, b in enumerate(ch):
            m = (hi @ pb[b].matrix).to_3x3()
            HINGE[b] = (m.inverted() @ n).normalized()


PIP_DIP = 0.67           # tendon coupling: tip joint follows the middle joint
DIP_MAX = math.radians(65)
PIP_OPEN = math.radians(35)      # the rest pose is curled ~40 deg: opening this far is straight, not bent back
DIP_OPEN = math.radians(20)
MCP_OPEN = math.radians(20)


def set_finger(ch, mcp, pip):
    pb[ch[0]].rotation_quaternion = Quaternion(HINGE[ch[0]], mcp)
    pb[ch[1]].rotation_quaternion = Quaternion(HINGE[ch[1]], pip)
    pb[ch[2]].rotation_quaternion = Quaternion(HINGE[ch[2]], max(-DIP_OPEN, min(DIP_MAX, PIP_DIP * pip)))
    bpy.context.view_layer.update()


def free(ch, cam_inv):
    return sdf(skinned()[chain_mask(ch, 0)], cam_inv).min() >= GAP


def close_chain(ch, limits, cam_inv, step=math.radians(1.0)):
    """Two-parameter curl (knuckle, middle+tip coupled) on true hinges; first open out of the camera if
    the start pose is inside it, then close both until the skin touches."""
    mcp, pip = 0.0, 0.0
    set_finger(ch, mcp, pip)
    while not free(ch, cam_inv) and pip > -PIP_OPEN:
        pip -= step
        mcp = max(mcp - step, -MCP_OPEN)
        set_finger(ch, mcp, pip)
    moving = True
    while moving:
        moving = False
        for which in (1, 0):
            nm, np_ = (mcp + step, pip) if which == 0 else (mcp, pip + step)
            if nm > limits[0] or np_ > limits[1]:
                continue
            set_finger(ch, nm, np_)
            if free(ch, cam_inv):
                mcp, pip = nm, np_
                moving = True
            else:
                set_finger(ch, mcp, pip)
    return [mcp, pip, max(-DIP_OPEN, min(DIP_MAX, PIP_DIP * pip))]


def fit(cam):
    """cam: Matrix, camera transform in hand space (initial guess; moved along the palm normal)."""
    for p in pb:
        p.rotation_mode = "QUATERNION"
    for n in sum(FINGERS, []) + THUMB:
        pb[n].rotation_quaternion = Quaternion()
    bpy.context.view_layer.update()
    pal = Vector((0, 1, 0))
    palm = seg_verts("l_hand")
    # the palm alone decides the camera's distance: touching, not floating, not inside
    for _ in range(300):
        if sdf(skinned()[palm], np.array(cam.inverted())).min() >= GAP:
            break
        cam = Matrix.Translation(pal * 0.0005) @ cam
    for _ in range(300):
        c2 = Matrix.Translation(-pal * 0.0003) @ cam
        if sdf(skinned()[palm], np.array(c2.inverted())).min() < GAP:
            break
        cam = c2
    cam_inv = np.array(cam.inverted())
    compute_hinges()
    rep = {}
    for ch in FINGERS:
        rep[ch[0]] = [round(math.degrees(x)) for x in close_chain(ch, LIMITS, cam_inv)]
    # curling lifts the palm skin near the knuckles: seat the camera on the hand again (no gap), then
    # re-close every finger onto the new surface
    nothumb = ~chain_mask(THUMB, 0)
    for _ in range(300):
        c2 = Matrix.Translation(-pal * 0.0002) @ cam
        if sdf(skinned()[nothumb], np.array(c2.inverted())).min() < GAP:
            break
        cam = c2
    cam_inv = np.array(cam.inverted())
    for ch in FINGERS:
        rep[ch[0]] = [round(math.degrees(x)) for x in close_chain(ch, LIMITS, cam_inv)]
    d = sdf(skinned(), cam_inv)
    contact = {}
    for b in sum(FINGERS, []) + THUMB + ["l_hand"]:
        m = seg_verts(b)
        if m.any():
            contact[b] = round(float(d[m].min()) * 1000, 2)
    fingers = {n: pb[n].rotation_quaternion.copy() for n in sum(FINGERS, []) + THUMB}
    builtins.LGRIP_FIT = {"cam": cam, "fingers": fingers, "angles": rep, "contact_mm": contact}
    return builtins.LGRIP_FIT


def camera_in_hand(x=-0.066, y=-0.010, z=0.03):
    """Phone grip: back of the camera on the palm, lens away from it, top towards the index finger."""
    cy = Vector((0, -1, 0))     # battery thin axis against the palm (palm normal is +Y here)
    cz = Vector((0, 0, 1))      # contact end towards the index side, sticking out
    cx = cy.cross(cz)
    m = Matrix((cx, cy, cz)).transposed().to_4x4()
    m.translation = Vector((x, y, z))
    return m


def fit_thumb(cam, target):
    """Grid search the thumb (base: three axes, joints: one flex) so nothing is inside the camera and the
    thumb pad rests at `target` (camera-local point) with its closest skin just touching."""
    import itertools
    cam_inv = np.array(cam.inverted())
    mask = np.ones(len(sel), bool)            # the whole hand: the thumb base drags palm skin with it
    tipm = seg_verts(THUMB[2])
    T = np.array(target)

    def pose(a, b, c, e):
        pb[THUMB[0]].rotation_quaternion = (Quaternion((1, 0, 0), math.radians(a)) @ Quaternion((0, 1, 0), math.radians(b))
                                            @ Quaternion((0, 0, 1), math.radians(c)))
        pb[THUMB[1]].rotation_quaternion = Quaternion(HINGE[THUMB[1]], math.radians(e) * 0.6)
        pb[THUMB[2]].rotation_quaternion = Quaternion(HINGE[THUMB[2]], math.radians(e))
        bpy.context.view_layer.update()

    def score(args):
        pose(*args)
        p = skinned()
        d = sdf(p[mask], cam_inv)
        if d.min() < GAP * 0.8:
            return None
        tip = (np.c_[p[tipm], np.ones(tipm.sum())] @ cam_inv.T)[:, :3].mean(0)
        pad = float(sdf(p[tipm], cam_inv).min())          # the thumb pad itself must rest on the camera
        return float(np.linalg.norm(tip - T) + 4 * abs(pad - GAP * 1.3)), float(d.min())

    best = None
    for args in itertools.product(range(-60, 61, 15), range(-60, 61, 15), range(-60, 61, 15), (-10, 0, 15, 30, 45, 60)):
        s = score(args)
        if s and (best is None or s[0] < best[0]):
            best = (s[0], args, s[1])
    for step in (5, 2):
        a0 = best[1]
        for args in itertools.product(*[range(v - 2 * step, v + 2 * step + 1, step) for v in a0]):
            s = score(args)
            if s and s[0] < best[0]:
                best = (s[0], args, s[1])
    pose(*best[1])
    return best


builtins.lgrip_fit_thumb = fit_thumb
builtins.lgrip_fit = fit
builtins.battery_in_hand = camera_in_hand
builtins.lgrip_sdf = sdf
builtins.lgrip_skinned = skinned
