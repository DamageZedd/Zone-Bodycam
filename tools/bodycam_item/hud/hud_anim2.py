"""Bodycam HUD animations v2: per-frame solve of both arms from keyed tracks, baked to bone keys.

exec() in Blender after hud_rig.py, clear.py; needs builtins R, CLEAR, GRIPS (right: front/back), BATGRIP
and LPINCH (left key pinch on the battery).

World = player eye at the origin, +Y forward, +Z up. The view pitch (camera effector) is the cam_pivot
rotation; hands live in camera space, so world targets go through the inverse pitch every frame.
Props: bc_prop (bodycam, carried by lead_gun) and bat_prop (battery, a second bone of the item model:
its pose relative to the bodycam is stored per frame in BATREL).
"""
import builtins
import math
import bpy
from mathutils import Matrix, Vector, Quaternion

SC = bpy.data.scenes["zbc_hud"]
PIVOT = SC.objects["cam_pivot"]
PROP = SC.objects["bc_prop"]
BAT = SC.objects["bat_prop"]
MB = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
GAP = 0.0006

CHEST = Vector((0.0, 0.105, -0.33))
CHEST_ROT = Quaternion((0, 0, 1), math.pi)          # lens forward when worn
SLOT_IN = Matrix.Translation(Vector((0.0, -0.0015, -0.0345)))   # battery fully inside the bottom slot
INS_HOLD = 0.010            # how far out the battery still is when the pinch lets go and the fingertips push it home
LOW_R = Vector((0.34, 0.12, -0.62))                 # camera space, out of view
LOW_L = Vector((-0.34, 0.12, -0.62))
POLE_R = Vector((0.75, -0.05, -0.55))
POLE_L = Vector((-0.75, -0.05, -0.55))
TAP_F = Vector((-0.35, 0.92, -0.15))
TAP_P = Vector((0, 0.25, -1))


def smooth(t):
    return t * t * (3 - 2 * t)


def rz(d):
    return Quaternion((0, 0, 1), math.radians(d))


def rx(d):
    return Quaternion((1, 0, 0), math.radians(d))


def ry(d):
    return Quaternion((0, 1, 0), math.radians(d))


def mat(pos, q):
    m = q.to_matrix().to_4x4()
    m.translation = pos
    return m


def basis(fdir, palm):
    f = fdir.normalized()
    p = (palm - f * palm.dot(f)).normalized()
    m = Matrix((-f, p.cross(-f), p)).transposed()
    return m.to_quaternion()


class Track:
    """Keys -> value at frame f. Values: float, Vector, Quaternion, Matrix (pos+rot) or callables (lazy).
    Motion passes through inner keys without stopping (Catmull-Rom positions, rotation eased only at the
    first and last key), so nothing stops dead at every key."""

    def __init__(self, keys, ease=False):
        self.keys = sorted(keys, key=lambda k: k[0])
        self.cache = {}
        self.ease = ease                 # True: ease in/out at every key (no overshoot; used for the view pitch)

    def val(self, i):
        i = max(0, min(len(self.keys) - 1, i))
        if i not in self.cache:
            v = self.keys[i][1]
            self.cache[i] = v() if callable(v) else v
        return self.cache[i]

    def __call__(self, f):
        ks = self.keys
        n = len(ks)
        if f <= ks[0][0]:
            return self.val(0)
        for i in range(n - 1):
            f0, f1 = ks[i][0], ks[i + 1][0]
            if f0 <= f <= f1:
                u = (f - f0) / float(f1 - f0) if f1 > f0 else 1.0
                first, last = i == 0, i == n - 2
                if self.ease:
                    a, b = self.val(i), self.val(i + 1)
                    return a + (b - a) * smooth(u)
                if first and last:
                    tr = smooth(u)
                elif first:
                    tr = u * u * (2 - u)          # ease in, leave with speed
                elif last:
                    tr = u * (1 + u - u * u)      # arrive with speed, ease out
                else:
                    tr = u
                a, b = self.val(i), self.val(i + 1)
                if isinstance(a, Quaternion):
                    return a.slerp(b, smooth(u))
                pa, pb_ = self._pos(a), self._pos(b)
                pp, pn = self._pos(self.val(i - 1)) if i > 0 else pa, self._pos(self.val(i + 2)) if i < n - 2 else pb_
                # tangents scaled to segment length in frames (non-uniform Catmull-Rom)
                fp = ks[i - 1][0] if i > 0 else f0 - (f1 - f0)
                fn = ks[i + 2][0] if i < n - 2 else f1 + (f1 - f0)
                m0 = (pb_ - pp) * ((f1 - f0) / float(f1 - fp)) if i > 0 else (pb_ - pa) * 0.0
                m1 = (pn - pa) * ((f1 - f0) / float(fn - f0)) if i < n - 2 else (pb_ - pa) * 0.0
                h00, h10, h01, h11 = 2*u**3 - 3*u**2 + 1, u**3 - 2*u**2 + u, -2*u**3 + 3*u**2, u**3 - u**2
                pos = pa * h00 + m0 * h10 + pb_ * h01 + m1 * h11
                if isinstance(a, Matrix):
                    return mat(pos, a.to_quaternion().slerp(b.to_quaternion(), smooth(u)))
                return pos
        return self.val(n - 1)

    @staticmethod
    def _pos(v):
        return v.to_translation() if isinstance(v, Matrix) else v


# ---------------------------------------------------------------- sequences
def seq_dead():
    S = {"L": 170}
    S["pitch"] = Track([(0, 0.0), (14, -15.0), (52, -15.0), (72, 0.0), (170, 0.0)], ease=True)   # a glance down; the chest stays off screen
    face = rx(-14)                                   # lens towards the eye (camera a little below it)
    cam = Track([
        (42, mat(CHEST, CHEST_ROT)),
        (48, mat(CHEST + Vector((0, 0, 0.035)), CHEST_ROT)),
        (54, mat(CHEST + Vector((0.02, 0.06, 0.045)), CHEST_ROT @ rz(-30))),
        (62, mat(Vector((0.05, 0.215, -0.18)), CHEST_ROT @ rz(-20))),
        (74, mat(Vector((0.04, 0.25, -0.12)), rz(-15))),                       # after the twirl, front towards him
        (90, mat(Vector((0.02, 0.27, -0.075)), face)),
        (104, mat(Vector((0.02, 0.27, -0.075)), face @ rz(4))),
        (106, mat(Vector((0.021, 0.27, -0.075)), face @ rz(9))),              # little shake
        (109, mat(Vector((0.019, 0.27, -0.075)), face @ rz(-9))),
        (112, mat(Vector((0.021, 0.27, -0.075)), face @ rz(7))),
        (115, mat(Vector((0.019, 0.27, -0.075)), face @ rz(-4))),
        (118, mat(Vector((0.02, 0.27, -0.075)), face)),
        (124, mat(Vector((0.02, 0.27, -0.075)), face)),
        (146, mat(Vector((0.24, 0.10, -0.62)), face @ rx(-45))),
        (150, mat(Vector((0.26, 0.08, -0.70)), face @ rx(-50))),
    ])
    F0, F1 = 62, 74                                  # the twirl: it turns half round inside the loosened hand
    flip = {}

    def flip_at(f):
        if not flip:
            H0 = right_from_cam(cam(F0), "front")
            H1 = right_from_cam(cam(F1), "back")
            gf, gb = GRIPS["front"]["cam"], GRIPS["back"]["cam"]
            qf, qb = gf.to_quaternion(), gb.to_quaternion()
            best = None
            for phi in (math.pi, -math.pi):
                r = (qf @ Quaternion((0, 0, 1), phi)).inverted() @ qb
                ang = r.angle if r.angle <= math.pi else 2 * math.pi - r.angle
                if best is None or ang < best[0]:
                    best = (ang, phi, r)
            flip.update(H0=H0, H1=H1, gf=gf, gb=gb, qf=qf, phi=best[1], r=best[2])
        u = (f - F0) / float(F1 - F0)
        e = smooth(u)
        lift = math.sin(math.pi * u) ** 2
        H0, H1 = flip["H0"], flip["H1"]
        hand = mat(H0.to_translation().lerp(H1.to_translation(), e) + Vector((0, 0, 0.012)) * lift,
                   H0.to_quaternion().slerp(H1.to_quaternion(), e))
        q = flip["qf"] @ Quaternion((0, 0, 1), flip["phi"] * e) @ Quaternion().slerp(flip["r"], e)
        p = flip["gf"].to_translation().lerp(flip["gb"].to_translation(), e) + Vector((0, 0, 0.032)) * lift
        return hand, hand @ mat(p, q)                # camera eased off the palm while it turns

    S["cam"] = lambda f: (mat(CHEST, CHEST_ROT) if f < 42 else (flip_at(f)[1] if F0 < f < F1 else cam(f))
                          if f <= 150 else None)
    S["r_override"] = lambda f: (lambda h: (h.to_translation(), h.to_quaternion()))(flip_at(f)[0]) if F0 < f < F1 else None
    S["bat"] = lambda f: None                        # inside the camera all along
    S["r_hold"] = lambda f: "front" if 42 <= f <= F0 else ("back" if F1 <= f <= 150 else None)
    S["r_free"] = [
        (0, "low"),
        (16, (Vector((0.045, 0.02, -0.215)), basis(TAP_F, TAP_P))),
        (20, (Vector((0.035, 0.035, -0.25)), basis(TAP_F, TAP_P))),
        (24, (Vector((0.035, 0.035, -0.225)), basis(TAP_F, TAP_P))),
        (28, (Vector((0.035, 0.035, -0.25)), basis(TAP_F, TAP_P))),
        (31, (Vector((0.045, 0.03, -0.225)), basis(TAP_F, TAP_P))),
        (36, (Vector((0.06, 0.08, -0.20)), basis(TAP_F, TAP_P))),          # up and forward, round the camera
        (39, lambda: (lambda H: (H.to_translation() + Vector((0.0, 0.06, 0.012)), H.to_quaternion()))(
            right_from_cam(mat(CHEST, CHEST_ROT), "front"))),              # in front of the lens, then straight in
        (42, ("hold", "front", 42)),
        (150, ("hold", "back", 150)),
        (165, "low"),
    ]
    S["r_fing"] = (Track([(0, 0.0), (42, 0.0), (45, 1.0), (61, 1.0), (65, 0.35), (68, 0.0)]),
                   Track([(0, 0.0), (68, 0.0), (71, 0.35), (74, 1.0), (150, 1.0), (156, 0.2)]))
    S["l_hold"] = lambda f: False
    S["l_free"] = [(0, "low")]
    S["l_fing"] = Track([(0, 0.0)])
    S["contact"] = {(20, "r", "cam"), (28, "r", "cam")}
    S["neutral"] = Track([(0, 0.0), (124, 0.0), (146, 0.85)])
    return S


def seq_insert():
    """Battery in at eye level (held on its side in the front grip, slot facing left), then the hand takes it
    down to the chest mount just below the view: the slap and pat happen off screen."""
    S = {"L": 130}
    S["pitch"] = Track([(0, 0.0), (64, 0.0), (82, -15.0), (108, -15.0), (124, 0.0)], ease=True)   # a glance down only
    hold_q = rz(-25) @ ry(80) @ CHEST_ROT             # held on its side, battery slot facing left (in profile)
    cam = Track([
        (0, mat(Vector((0.24, 0.12, -0.64)), hold_q)),
        (22, mat(Vector((0.03, 0.26, -0.11)), hold_q)),
        (64, mat(Vector((0.028, 0.262, -0.108)), hold_q)),
        (84, mat(CHEST + Vector((0.035, 0.09, 0.02)), CHEST_ROT @ rz(-15))),
        (91, mat(CHEST + Vector((0.0, 0.012, 0.004)), CHEST_ROT)),
        (92, mat(CHEST, CHEST_ROT)),
    ])
    S["cam"] = lambda f: cam(f) if f < 92 else mat(CHEST, CHEST_ROT)
    h = INS_HOLD
    ins = Track([(0, 0.075), (30, 0.045), (40, 0.036), (44, max(0.031, h + 0.021)), (56, h), (60, h), (66, 0.0)])
    bat_in = Track([(0, lambda: mat(Vector((-0.30, 0.16, -0.60)), S["cam"](30).to_quaternion())),
                    (30, lambda: S["cam"](30) @ SLOT_IN @ Matrix.Translation((0, 0, -0.045)))])

    def bat(f):
        if f < 30:
            return bat_in(f)
        return S["cam"](f) @ SLOT_IN @ Matrix.Translation((0, 0, -ins(f)))
    S["bat"] = bat
    S["r_hold"] = lambda f: "front" if f <= 99 else None
    S["r_free"] = [
        (99, ("hold", "front", 99)),
        (103, (Vector((0.045, 0.035, -0.225)), basis(TAP_F, TAP_P))),
        (107, (Vector((0.035, 0.035, -0.25)), basis(TAP_F, TAP_P))),     # pat (off screen)
        (111, (Vector((0.045, 0.03, -0.222)), basis(TAP_F, TAP_P))),
        (124, "low"),
    ]
    S["r_fing"] = (Track([(0, 1.0), (95, 1.0), (99, 0.0)]), Track([(0, 0.0)]))
    S["l_hold"] = lambda f: f <= 58

    def l_after(k, side=0.0):
        """Left hand back along the slot axis by k (away from the camera), and `side` to the left."""
        def g():
            H = left_from_bat(S["bat"](58))
            out = S["cam"](58).to_3x3() @ Vector((0, 0, -1))
            return (H.to_translation() + out * k + Vector((-side, 0, 0)), H.to_quaternion())
        return g
    S["l_free"] = [
        (58, ("lhold", 58)),
        (62, l_after(0.022)),
        (65, l_after(0.004)),                # fingertips push it the last bit in (contact enforced)
        (72, l_after(0.06, 0.03)),
        (104, "low"),
    ]
    S["l_fing"] = Track([(0, 1.0), (58, 1.0), (62, 0.0)])
    S["l_neutral"] = Track([(0, 0.0), (64, 0.0), (74, 1.0)])   # after the push the wrist straightens with the forearm
    S["contact"] = {(107, "r", "cam"), (65, "l", "bat"), (66, "l", "bat")}
    S["neutral"] = Track([(0, 0.0)])
    return S


# ---------------------------------------------------------------- solve
def right_from_cam(D, grip):
    return D @ GRIPS[grip]["cam"].inverted()


def left_from_bat(B):
    return B @ BATGRIP.inverted()


PUSH = {}
BATREL = {}


def low_pose(side, P):
    lw = P @ (LOW_R if side == "r" else LOW_L)
    fd = P.to_3x3() @ Vector((0, 1, 0.2))
    pn = P.to_3x3() @ Vector((-1 if side == "r" else 1, 0, 0))
    return lw, basis(fd, pn)


def build(seqf, frames=None, key=True, extra=None):
    S = seqf()
    L = S["L"]
    arm = R.arm
    name = "zbc_bodycam_" + seqf.__name__[4:]
    if key:
        for n in (name, name + "_cam"):
            a = bpy.data.actions.get(n)
            if a:
                bpy.data.actions.remove(a)
        (arm.animation_data or arm.animation_data_create()).action = bpy.data.actions.new(name)
        (PIVOT.animation_data or PIVOT.animation_data_create()).action = bpy.data.actions.new(name + "_cam")
        for o in (PROP, BAT):
            o.rotation_mode = "QUATERNION"
            ad = o.animation_data or o.animation_data_create()
            old = bpy.data.actions.get(name + "_" + o.name)
            if old:
                bpy.data.actions.remove(old)
            ad.action = bpy.data.actions.new(name + "_" + o.name)
    else:
        for o in (arm, PIVOT, PROP, BAT):
            if o.animation_data:
                o.animation_data.action = None
    fr_front, fr_back = S["r_fing"]
    rest_r = arm.data.bones["r_hand"].matrix_local.to_quaternion()
    rest_l = arm.data.bones["l_hand"].matrix_local.to_quaternion()
    fixed = {}

    def free_val(keys, f, side, P):
        ks = []
        for k, v in keys:
            if v == "low":
                v = low_pose(side, P)
            else:
                ck = (side, k)
                if ck not in fixed:
                    if isinstance(v, tuple) and len(v) == 3 and v[0] == "hold":
                        H = right_from_cam(S["cam"](v[2]), v[1])
                        fixed[ck] = (H.to_translation(), H.to_quaternion())
                    elif isinstance(v, tuple) and len(v) == 2 and v[0] == "lhold":
                        H = left_from_bat(S["bat"](v[1]))
                        fixed[ck] = (H.to_translation(), H.to_quaternion())
                    elif callable(v):
                        fixed[ck] = v()
                    else:
                        fixed[ck] = v
                v = fixed[ck]
            ks.append((k, v))
        m = Track([(k, mat(v[0], v[1])) for k, v in ks])(f)      # same no-stop spline as the props
        return m.to_translation(), m.to_quaternion()

    for f in (frames if frames is not None else range(L + 1)):
        p = S["pitch"](f)
        PIVOT.rotation_euler = (math.radians(p), 0, 0)
        bpy.context.view_layer.update()
        P = PIVOT.matrix_world.copy()
        Pinv = P.inverted()
        R.reset()
        bb = min(1.0, abs(p) / 40.0)
        root = arm.data.bones["bip01"].matrix_local.copy()
        R.set_world("bip01", Pinv @ Matrix.Translation(Vector((0, -0.04 * bb, -0.17 * bb))) @ root)
        D = S["cam"](f)
        B = S["bat"](f)
        g = S["r_hold"](f) if D is not None else None
        lh = bool(S["l_hold"](f) and B is not None)
        ov = S.get("r_override", lambda f: None)(f)
        if g:
            H = right_from_cam(D, g)
            wr, qr = H.to_translation(), H.to_quaternion()
        elif ov is not None:
            wr, qr = ov
        else:
            wr, qr = free_val(S["r_free"], f, "r", P)
        cl = lambda x: max(0.0, min(1.0, x))
        wf, wb = cl(fr_front(f)), cl(fr_back(f))
        gn = S.get("grip_names", ("front", "back"))
        fset, fw = (GRIPS[gn[0]]["fingers"], wf) if wf >= wb else (GRIPS[gn[1]]["fingers"], wb)
        op = getattr(builtins, "OPEN_R", {})
        rfing = {n: op.get(n, Quaternion()).slerp(q, fw) for n, q in fset.items()}   # open hand -> grip
        if lh:
            H = left_from_bat(B)
            wl, ql = H.to_translation(), H.to_quaternion()
        else:
            wl, ql = free_val(S["l_free"], f, "l", P)
        lw = cl(S["l_fing"](f))
        lfing = {n: Quaternion().slerp(q, lw) for n, q in LPINCH.items()}
        nw = cl(S["neutral"](f))

        def pose(side, w, q, fing):
            rest = rest_r if side == "r" else rest_l
            pole = POLE_R if side == "r" else POLE_L
            R.solve_arm(side, Pinv @ w, Pinv @ pole, hand_rot=(Pinv.to_quaternion() @ q) @ rest.inverted())
            R.fingers(side, fing)

        ex = dict((extra or {}).get(f, {}))
        if g or ov is not None:
            ex["r"] = Vector()                     # holding (or twirling) hands follow the camera exactly
        if lh:
            ex["l"] = Vector()
        wr = wr + ex.get("r", Vector())
        wl = wl + ex.get("l", Vector())
        wr0, wl0 = wr.copy(), wl.copy()
        pose("r", wr, qr, rfing)
        if g and nw > 0:
            R.bone("r_hand").matrix_basis = Matrix()
            R.solve_arm("r", Pinv @ wr, Pinv @ POLE_R)
            qn = P.to_quaternion() @ R.world("r_hand").to_quaternion()
            qr = qr.slerp(qn, nw)
            pose("r", wr, qr, rfing)
        pose("l", wl, ql, lfing)
        nwl = cl(S.get("l_neutral", lambda f: 0.0)(f)) if not lh else 0.0
        if nwl > 0:
            R.bone("l_hand").matrix_basis = Matrix()
            R.solve_arm("l", Pinv @ wl, Pinv @ POLE_L)
            qn = P.to_quaternion() @ R.world("l_hand").to_quaternion()
            ql = ql.slerp(qn, smooth(nwl))
            pose("l", wl, ql, lfing)
        props = []
        if D is not None:
            props.append(("cam", D))
        if B is not None and f < 66:
            props.append(("bat", B))
        for side, held in (("r", bool(g) or ov is not None), ("l", lh)):
            if held:
                continue
            wcur, qcur, fing = (wr, qr, rfing) if side == "r" else (wl, ql, lfing)
            for pname, M in props:
                Marm = Pinv @ M
                away = (wcur - M.to_translation()).normalized()
                up = Vector((0, 0, 1)) if side == "r" else (D.to_3x3() @ Vector((0, 0, -1)) if D is not None else Vector((0, 0, -1)))
                odir = (up * 3 + away).normalized()
                contact = (f, side, pname) in S["contact"]
                for _ in range(15):
                    d = CLEAR(side, pname, Marm)
                    want = GAP if contact else max(d, GAP)
                    if abs(d - want) < 0.0002:
                        break
                    wcur = wcur + odir * (want - d)
                    pose(side, wcur, qcur, fing)
                if CLEAR(side, pname, Marm) < GAP:
                    for _ in range(80):
                        wcur = wcur + odir * 0.001
                        pose(side, wcur, qcur, fing)
                        if CLEAR(side, pname, Marm) >= GAP:
                            break
            if side == "r":
                wr = wcur
            else:
                wl = wcur
        PUSH[f] = {"r": (wr - wr0) + ex.get("r", Vector()), "l": (wl - wl0) + ex.get("l", Vector())}
        if D is None:
            Dc = Pinv @ mat(Vector((0.26, 0.08, -0.70)), rx(-64))   # stowed: stays where the stow path ends (out of view)
        elif g:
            Dc = R.world("r_hand") @ GRIPS[g]["cam"]
        else:
            Dc = Pinv @ D
        R.set_world("lead_gun", Dc @ MB)
        Dw = P @ Dc
        if B is None:
            Bw = Dw @ SLOT_IN
        elif lh:
            Bw = P @ R.world("l_hand") @ BATGRIP         # the battery is wherever the left hand holds it
        else:
            Bw = B
        BATREL[f] = Dw.inverted() @ Bw
        PROP.matrix_world = Dw
        BAT.matrix_world = Bw
        if key:
            R.key(f)
            PIVOT.keyframe_insert("rotation_euler", frame=f)
            for o in (PROP, BAT):
                o.keyframe_insert("location", frame=f)
                o.keyframe_insert("rotation_quaternion", frame=f)
    return L


def build_smooth(seqf, key=True, win=3, sigma=2.5):
    L = seqf()["L"]
    PUSH.clear()
    build(seqf, key=False)
    raw = {f: PUSH.get(f, {"r": Vector(), "l": Vector()}) for f in range(L + 1)}
    dil = {}
    for k in range(L + 1):
        dil[k] = {}
        for s in ("r", "l"):
            c = [raw[j][s] for j in range(max(0, k - win), min(L, k + win) + 1)]
            dil[k][s] = max(c, key=lambda v: v.length)
    out = {}
    for f in range(L + 1):
        out[f] = {}
        for s in ("r", "l"):
            acc, ws = Vector(), 0.0
            for k in range(max(0, f - 3 * int(sigma)), min(L, f + 3 * int(sigma)) + 1):
                w = math.exp(-((k - f) ** 2) / (2 * sigma * sigma))
                acc += dil[k][s] * w
                ws += w
            out[f][s] = acc / ws
    return build(seqf, key=key, extra=out)


builtins.HA2 = {"build": build, "build_smooth": build_smooth, "seq_dead": seq_dead, "seq_insert": seq_insert,
                "BATREL": BATREL, "MB": MB, "SLOT_IN": SLOT_IN}
