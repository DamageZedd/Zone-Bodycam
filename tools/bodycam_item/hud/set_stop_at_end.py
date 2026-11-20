"""Set the X-Ray "stop at end" motion flag (1 << 1) on named motions inside an OMF / skeleton OGF, in place.

Motion params entry (params v3/v4): name\\0, u32 flags, u16 bone_or_part, u16 motion index, f32 speed, power,
accrue, falloff. The motion-data chunk repeats each name followed by a u32 frame count, so an occurrence is
only taken as the params entry when its speed reads 1.0 and its power/accrue/falloff are sane floats.
usage: py set_stop_at_end.py <file> <motion> [<motion> ...]
"""
import struct
import sys

STOP_AT_END = 1 << 1


def patch(path, names):
    data = bytearray(open(path, "rb").read())
    done = {}
    for name in names:
        key = name.encode() + b"\0"
        start = 0
        while True:
            i = data.find(key, start)
            if i < 0:
                break
            start = i + 1
            if i > 0 and 32 < data[i - 1] < 127:
                continue                      # part of a longer name
            p = i + len(key)
            if p + 24 > len(data):
                continue
            flags, part, idx = struct.unpack_from("<IHH", data, p)
            speed, power, accrue, falloff = struct.unpack_from("<4f", data, p + 8)
            if abs(speed - 1.0) > 1e-6 or not (0 <= accrue <= 100 and 0 <= falloff <= 100) or flags > 0xFFFF:
                continue
            struct.pack_into("<I", data, p, flags | STOP_AT_END)
            done.setdefault(name, []).append((p, flags, flags | STOP_AT_END))
    open(path, "wb").write(bytes(data))
    return done


if __name__ == "__main__":
    res = patch(sys.argv[1], sys.argv[2:])
    for n in sys.argv[2:]:
        print(n, res.get(n, "NOT FOUND"))
