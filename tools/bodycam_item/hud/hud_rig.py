"""Pose helpers for the bodycam HUD hand animations (scene zbc_hud). exec() in Blender; puts `R` in builtins.

Bones in the X-Ray hands rig are 2 cm stubs, so Blender IK is useless: arms are solved here as a two-bone
chain on bone heads (shoulder = r_upperarm head, elbow = r_forearm head, wrist = r_hand head).
All positions are in armature space (= HUD camera space before the camera pivot): +Y forward, +Z up.
"""
import builtins
import math
import bpy
from mathutils import Matrix, Vector, Quaternion

ARM = "wpn_hand_loner_novice.ogf"


class Rig:
    def __init__(self):
        self.arm = bpy.data.scenes["zbc_hud"].objects[ARM]
        self.pb = self.arm.pose.bones
        self.rest_grip = {}

    def bone(self, n):
        return self.pb[n]

    def world(self, n):
        return self.pb[n].matrix.copy()

    def reset(self):
        for p in self.pb:
            p.matrix_basis = Matrix()
        bpy.context.view_layer.update()

    def set_world(self, n, m):
        self.pb[n].matrix = m
        bpy.context.view_layer.update()

    def rotate_world(self, n, q, pivot=None):
        """Apply a world-space rotation q to bone n about its head (children follow)."""
        m = self.world(n)
        head = m.to_translation() if pivot is None else pivot
        t = Matrix.Translation(head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-head)
        self.set_world(n, t @ m)

    def aim(self, n, child, target, pole=None, pole_child=None):
        """Rotate bone n so the head of `child` moves onto `target` (shortest arc), then optionally roll about
        that axis so `pole_child` lies on the side of `pole`."""
        h = self.world(n).to_translation()
        c = self.world(child).to_translation()
        q = (c - h).rotation_difference(target - h)
        self.rotate_world(n, q)
        if pole is not None and pole_child is not None:
            axis = (target - h).normalized()
            p = self.world(pole_child).to_translation() - h
            p -= axis * p.dot(axis)
            w = pole - h
            w -= axis * w.dot(axis)
            if p.length > 1e-6 and w.length > 1e-6:
                ang = p.angle(w)
                if axis.dot(p.cross(w)) < 0:
                    ang = -ang
                self.rotate_world(n, Quaternion(axis, ang))

    def solve_arm(self, side, wrist, pole, hand_rot=None):
        """side 'r'/'l'. wrist: target for <side>_hand head. pole: point the elbow bends towards.
        hand_rot: world rotation (Quaternion) for the hand, relative to its rest world rotation."""
        up, fo, ha = side + "_upperarm", side + "_forearm", side + "_hand"
        s = self.world(up).to_translation()
        e = self.world(fo).to_translation()
        w = self.world(ha).to_translation()
        l1, l2 = (e - s).length, (w - e).length
        d = wrist - s
        dist = min(d.length, (l1 + l2) * 0.999)
        dn = d.normalized()
        # elbow position: in the plane of (s, wrist, pole)
        a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
        hgt = math.sqrt(max(l1 * l1 - a * a, 0.0))
        pv = pole - s
        pv -= dn * pv.dot(dn)
        pv = pv.normalized() if pv.length > 1e-6 else Vector((0, 0, -1))
        elbow = s + dn * a + pv * hgt
        wrist_r = s + dn * dist
        self.aim(up, fo, elbow)
        self.aim(fo, ha, wrist_r)
        if hand_rot is not None:
            rest = self.arm.data.bones[ha].matrix_local.to_quaternion()
            m = self.world(ha)
            nm = (hand_rot @ rest).to_matrix().to_4x4()
            nm.translation = m.to_translation()
            self.set_world(ha, nm)
            # spread half the hand roll onto the forearm twist bone if it exists
        return elbow

    def fingers(self, side, values):
        """values: {bone: Quaternion local (matrix_basis rotation)}."""
        for n, q in values.items():
            p = self.pb[n]
            p.rotation_mode = "QUATERNION"
            p.rotation_quaternion = q
        bpy.context.view_layer.update()

    def capture_fingers(self, side, action, frame):
        """Read finger local rotations of one side from an existing action at a frame."""
        ad = self.arm.animation_data or self.arm.animation_data_create()
        old = ad.action
        ad.action = bpy.data.actions[action]
        ad.action_slot = ad.action.slots[0]
        bpy.context.scene.frame_set(frame)
        names = [b.name for b in self.arm.data.bones if ("_%s_finger" % side) in b.name or b.name.startswith(side + "_finger")]
        out = {}
        for n in names:
            p = self.pb[n]
            out[n] = p.matrix_basis.to_quaternion()
        ad.action = old
        return out

    def key(self, frame, names=None):
        for p in self.pb:
            if names and p.name not in names:
                continue
            p.rotation_mode = "QUATERNION"
            p.keyframe_insert("rotation_quaternion", frame=frame, group=p.name)
            p.keyframe_insert("location", frame=frame, group=p.name)


builtins.R = Rig()
