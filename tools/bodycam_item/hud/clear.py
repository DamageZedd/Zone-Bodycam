"""Hand-to-prop clearance for both hands against the bodycam and the battery (exec in Blender; needs R).

builtins.CLEAR(side, prop, prop_arm) -> closest signed distance (m) from that hand's skin to the prop.
prop_arm is the prop's matrix in armature space. Skin is linear-blend skinned from the current pose.
"""
import builtins
import numpy as np
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

SC = bpy.data.scenes["zbc_hud"]
HM = SC.objects["wpn_hand_loner_novice.ogf 00"]
arm = R.arm
pb = arm.pose.bones
names = [b.name for b in arm.data.bones]
idx = {n: i for i, n in enumerate(names)}
vg = {g.index: g.name for g in HM.vertex_groups}
co = np.array([v.co[:] for v in HM.data.vertices])
W = np.zeros((len(co), len(names)))
for v in HM.data.vertices:
    for g in v.groups:
        n = vg.get(g.group)
        if n in idx:
            W[v.index, idx[n]] = g.weight
W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
rest_inv = [np.array(arm.data.bones[n].matrix_local.inverted()) for n in names]
SIDE = {}
for s in ("r", "l"):
    cols = [i for i, n in enumerate(names) if n.startswith(s + "_") or n.startswith("bip01_%s_" % s)]
    sel = np.where(W[:, cols].sum(1) > 0.5)[0]
    SIDE[s] = (sel, W[sel], np.c_[co[sel], np.ones(len(sel))])


def skin(s):
    sel, w, rh = SIDE[s]
    acc = np.zeros((len(sel), 4))
    for j in np.where(w.sum(0) > 0)[0]:
        acc += w[:, j:j + 1] * (rh @ (np.array(pb[names[j]].matrix) @ rest_inv[j]).T)
    return acc[:, :3]


def hull_planes(vs):
    """Outward planes (n, d) of the convex hull: a point is inside when n.p - d <= 0 for all planes."""
    import bmesh
    bm = bmesh.new()
    for v in vs:
        bm.verts.new(v)
    bmesh.ops.convex_hull(bm, input=bm.verts[:])
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    bm.normal_update()
    c = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
    planes = []
    for f in bm.faces:
        n = f.normal.copy()
        if n.dot(f.calc_center_median() - c) < 0:
            n = -n
        planes.append((n, n.dot(f.verts[0].co)))
    bm.free()
    return np.array([p[0][:] for p in planes]), np.array([p[1] for p in planes])


def bvh_of(obj):
    """BVH of the real surface (distance) + its convex hull (solid inside test; recesses count as inside)."""
    me = obj.data
    vs = [v.co.copy() for v in me.vertices]
    lo = np.array([min(v[i] for v in vs) for i in range(3)])
    hi = np.array([max(v[i] for v in vs) for i in range(3)])
    return BVHTree.FromPolygons(vs, [p.vertices[:] for p in me.polygons]), lo, hi, hull_planes(vs)


def signed(prop, q):
    """Signed distance of local points q (N,3) to the prop: unsigned surface distance, negative inside the hull."""
    bvh, lo, hi, (pn, pd) = PROPS[prop]
    far = np.linalg.norm(np.maximum(np.maximum(lo - q, q - hi), 0), axis=1)
    out = far.copy()
    near = np.where(far < 0.004)[0]
    if len(near):
        inside = np.all(q[near] @ pn.T - pd <= 0, axis=1)
        for k, i in enumerate(near):
            loc, nor, _, dist = bvh.find_nearest(Vector(q[i]))
            out[i] = -dist if inside[k] else dist
    return out


PROPS = {"cam": bvh_of(SC.objects["bc_prop"]), "bat": bvh_of(SC.objects["bat_prop"])}


def clear(s, prop, prop_arm):
    p = skin(s)
    q = (np.c_[p, np.ones(len(p))] @ np.array(prop_arm.inverted()).T)[:, :3]
    return float(signed(prop, q).min())


builtins.CLEAR = clear
builtins.PROP_SIGNED = signed
