"""Bit-exact integer reference for the GPU LAB "Procedural fire" scene (fire_g0).

This is a hardware-friendly integer re-definition of main/lab.cpp::fire(). It is NOT
pixel-identical to the float scene (different noise hash, power-of-two octave
amplitudes, 1/4-step time scaling). All values are fixed point with 16 fractional
bits (Q16). The RTL (fire_pixel.v) and the C header (fpga/host/fire_g0.h) must match
this model for every input.

Frame geometry is fixed to the 640x360 visual profile (see FIRE_W / FIRE_H).
"""

FIRE_W = 640
FIRE_H = 360
SX = 205            # Q16 of 1/320 (204.8)
SY = 182            # Q16 of 1/360 (182.04)
TIME_STEP = 2949    # Q16 of 0.045
HASH_A = 0x9E37
HASH_B = 0x85EB
HASH_C = 0xC2B3
HASH_M = 0x2C1B
M32 = 0xFFFFFFFF


def hash16(ix, iy, octave):
    seed = 17 + octave
    hv = (ix * HASH_A + iy * HASH_B + seed * HASH_C) & M32
    x1 = hv ^ (hv >> 15)
    m = (x1 & 0xFFFF) * HASH_M
    return ((m ^ (m >> 11)) ^ (hv >> 16)) & 0xFFFF


def smooth(f):
    s = (f * f) >> 16
    return (s * (196608 - 2 * f)) >> 16


def noise(u, v, octave):
    ix, fx = u >> 16, u & 0xFFFF
    iy, fy = v >> 16, v & 0xFFFF
    n00 = hash16(ix, iy, octave)
    n10 = hash16(ix + 1, iy, octave)
    n01 = hash16(ix, iy + 1, octave)
    n11 = hash16(ix + 1, iy + 1, octave)
    sx, sy = smooth(fx), smooth(fy)
    a = n00 + (((n10 - n00) * sx) >> 16)
    b = n01 + (((n11 - n01) * sx) >> 16)
    return a + (((b - a) * sy) >> 16)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def rgb565(r, g, b):
    return ((r & 248) << 8) | ((g & 252) << 3) | (b >> 3)


def heat(x, y, frame, octaves):
    """Return heat in Q16 (0..65536)."""
    nx = (x - 320) * SX
    h = (359 - y) * SY
    t = frame * TIME_STEP
    turb = 0
    for o in range(octaves):
        freq = 3 << o
        u = nx * freq + (12 << 16)
        tm = t + (t >> 2) * o
        v = h * freq - tm
        turb += noise(u, v, o) >> (o + 1)
    a = ((65536 - h) * 3) >> 1
    b = (abs(nx) * (32768 + h)) >> 16
    c = (turb * 55706) >> 16
    return clamp(a - b + c - 45875, 0, 65536)


def color(x, y, frame, octaves):
    hq = heat(x, y, frame, octaves)
    r = (min(65536, hq * 3) * 255) >> 16
    g = (clamp(hq * 3 - 52429, 0, 65536) * 240) >> 16
    b = (clamp(hq * 4 - 163840, 0, 65536) * 160) >> 16
    return rgb565(r, g, b)


def tile(tile_x, tile_y, frame, octaves):
    """1024 RGB565 words, row-major, for the 32x32 tile (pixels outside the frame are computed too)."""
    return [color(tile_x * 32 + i, tile_y * 32 + j, frame, octaves)
            for j in range(32) for i in range(32)]


def frame_image(frame, octaves):
    return [color(x, y, frame, octaves) for y in range(FIRE_H) for x in range(FIRE_W)]


if __name__ == "__main__":
    import sys
    f = int(sys.argv[1]) if len(sys.argv) > 1 else 17
    o = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    print([hex(color(x, 300, f, o)) for x in (0, 160, 320, 480, 639)])
