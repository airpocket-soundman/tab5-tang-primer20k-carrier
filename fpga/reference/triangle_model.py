"""Bit-exact oracle for the resident triangle model (MODEL_* v1).

Desktop-only. The RTL (fpga/link/rtl/triangle_model.v) and the portable C
reference (fpga/host/triangle_model.h) must produce identical integers.
"""
from .link_protocol import crc16, request

MODEL_CAPS, MODEL_LOAD, MODEL_POSE, MODEL_DRAW = 0x48, 0x49, 0x4a, 0x4b
MAX_VERTICES, MAX_TRIANGLES = 64, 96
FORMAT = 1
TILE = 32
TILE_Q4 = TILE * 16  # Q12.4 units per tile edge

OK, BAD_CRC, BAD_OPCODE, BAD_ARGUMENT, NOT_READY = 0, 1, 2, 3, 5


def s16(value):
    value &= 0xffff
    return value - 65536 if value & 0x8000 else value


def u16(value):
    return value & 0xffff


def trunc_div(numerator, divisor):
    """C-style division, rounding toward zero. divisor must be positive."""
    quotient = abs(numerator) // divisor
    return -quotient if numerator < 0 else quotient


def fits16(value):
    return -32768 <= value <= 32767


class Pose:
    """rotation: nine Q2.14 values (row major). translation: camera-space
    offset in model units. focal/center are Q12.4 screen units. depth_shift is
    0..15."""

    def __init__(self, rotation, translation, focal, center_x, center_y, depth_shift):
        if len(rotation) != 9 or len(translation) != 3 or not 0 <= depth_shift <= 15:
            raise ValueError('bad pose')
        self.rotation = [s16(v) for v in rotation]
        self.translation = [s16(v) for v in translation]
        self.focal, self.center_x, self.center_y = s16(focal), s16(center_x), s16(center_y)
        self.depth_shift = depth_shift

    def words(self):
        return [u16(v) for v in self.rotation + self.translation +
                [self.focal, self.center_x, self.center_y, self.depth_shift]]


def project_vertex(vertex, pose):
    """Returns (valid, sx, sy, depth). Invalid vertices have zero payload."""
    r, t = pose.rotation, pose.translation
    cam = []
    for row in range(3):
        accum = r[3 * row] * vertex[0] + r[3 * row + 1] * vertex[1] + r[3 * row + 2] * vertex[2]
        cam.append((accum >> 14) + t[row])
    xc, yc, zc = cam
    if zc < 1:
        return (False, 0, 0, 0)
    sx = pose.center_x + trunc_div(pose.focal * xc, zc)
    sy = pose.center_y + trunc_div(pose.focal * yc, zc)
    if not fits16(sx) or not fits16(sy):
        return (False, 0, 0, 0)
    depth = min(zc >> pose.depth_shift, 65535)
    return (True, sx, sy, depth)


def project_model(vertices, pose):
    return [project_vertex(v, pose) for v in vertices]


class Model:
    def __init__(self, vertices, triangles):
        """vertices: [(x,y,z)] int16. triangles: [(i0,i1,i2,color)]."""
        if not 1 <= len(vertices) <= MAX_VERTICES or not 1 <= len(triangles) <= MAX_TRIANGLES:
            raise ValueError('bad counts')
        self.vertices = [tuple(s16(c) for c in v) for v in vertices]
        self.triangles = [(a, b, c, u16(color)) for a, b, c, color in triangles]
        if any(i >= len(vertices) for t in self.triangles for i in t[:3]):
            raise ValueError('vertex index out of range')


def tile_records(model, screen, tile_x, tile_y):
    """Replay for one 32x32 tile. Returns (records, drawn, skipped).

    records holds the ten setter values AX,AY,BX,BY,CX,CY,ZA,ZB,ZC,COLOR for
    every triangle that is submitted, in model order -- exactly what a scalar
    or TRI_BATCH host would send. Triangles are skipped (counted) when a vertex
    is invalid or a tile-local coordinate leaves int16; a conservative bounding
    box test removes triangles that cannot touch a pixel centre (not counted).
    """
    ox, oy = tile_x * TILE_Q4, tile_y * TILE_Q4
    records, drawn, skipped = [], 0, 0
    for i0, i1, i2, color in model.triangles:
        verts = [screen[i0], screen[i1], screen[i2]]
        if not all(v[0] for v in verts):
            skipped += 1
            continue
        local = [(v[1] - ox, v[2] - oy) for v in verts]
        if not all(fits16(c) for p in local for c in p):
            skipped += 1
            continue
        xs, ys = [p[0] for p in local], [p[1] for p in local]
        if max(xs) < 0 or min(xs) > TILE_Q4 - 1 or max(ys) < 0 or min(ys) > TILE_Q4 - 1:
            continue
        rec = []
        for px, py in local:
            rec += [u16(px), u16(py)]
        rec += [verts[0][3], verts[1][3], verts[2][3], color]
        records.append(rec)
        drawn += 1
    return records, drawn, skipped


# Wire encoders -----------------------------------------------------------

def _with_crc(header, body):
    return header + body + crc16(header[:6] + body).to_bytes(2, 'little')


def encode_caps(seq, which, tagged=False):
    return request(MODEL_CAPS | (128 if tagged else 0), seq, which, 0)


def encode_load(seq, model, tagged=False):
    header = request(MODEL_LOAD | (128 if tagged else 0), seq, len(model.vertices), len(model.triangles))
    body = b''.join(u16(c).to_bytes(2, 'little') for v in model.vertices for c in v)
    body += b''.join(bytes([a, b, c, 0]) + color.to_bytes(2, 'little')
                     for a, b, c, color in model.triangles)
    return _with_crc(header, body)


def encode_pose(seq, pose, tagged=False):
    header = request(MODEL_POSE | (128 if tagged else 0), seq, 0, FORMAT)
    body = b''.join(w.to_bytes(2, 'little') for w in pose.words())
    return _with_crc(header, body)


def encode_draw(seq, tile_x, tile_y, tagged=False):
    return request(MODEL_DRAW | (128 if tagged else 0), seq, tile_x, tile_y)


LOAD_BODY_BYTES = lambda nv, nt: 6 * nv + 6 * nt
POSE_BODY_BYTES = 32
