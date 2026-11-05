"""Compare independent Python, C header and FPGA Fire integer_g0 v1."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def valid(w, h, load):
    return (w, h) in ((640, 360), (320, 180), (160, 96)) and 0 <= load < 3


def pixel(x, y, w, h, frame, load):
    if not valid(w, h, load) or x >= w or y >= h:
        return 0
    iw, ih = {640: 1638, 320: 3276, 160: 6553}[w], {360: 2912, 180: 5825, 96: 10922}[h]
    nx, altitude = ((x * iw) >> 11) - 256, ((h - 1 - y) * ih) >> 12
    turbulence = 0

    def noise(xx, yy, octave):
        v = ((xx & 65535) * 1973 + (yy & 65535) * 9277 + (17 + octave) * 26699) & 65535
        v = ((v ^ (v >> 7)) * 25173) & 65535
        return (v ^ (v >> 8)) & 255

    def smooth(f):
        return (f * f * (768 - 2 * f)) >> 16

    for o in range(2 + load * 2):
        frequency = 3 << o
        u = ((nx + 256) * frequency) // 2 + 3072
        v = altitude * frequency - (frame & 65535) * (12 + 2 * o)
        ix, iy = u // 256, v // 256
        fx, fy = smooth(u % 256), smooth(v % 256)
        top = (noise(ix, iy, o) * (256 - fx) + noise(ix + 1, iy, o) * fx) >> 8
        bottom = (noise(ix, iy + 1, o) * (256 - fx) + noise(ix + 1, iy + 1, o) * fx) >> 8
        sample = (top * (256 - fy) + bottom * fy) >> 8
        turbulence += (sample * (128 >> o)) >> 8
    heat = ((256 - altitude) * 3) // 2 - ((abs(nx) * (128 + altitude)) >> 8) + ((turbulence * 218) >> 8) - 179
    clamp = lambda a: min(256, max(0, a))
    r, g, b = (clamp(heat * 3) * 255) >> 8, (clamp(heat * 3 - 205) * 240) >> 8, (clamp(heat * 4 - 640) * 160) >> 8
    return ((r & 248) << 8) | ((g & 252) << 3) | (b >> 3)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog', required=True)
    p.add_argument('--vvp', required=True)
    p.add_argument('--zig', required=True)
    a = p.parse_args()
    env = dict(os.environ)
    bindir = Path(a.iverilog).resolve().parent
    env['PATH'] = str(bindir) + os.pathsep + str(bindir.parent / 'lib') + os.pathsep + env['PATH']
    cases = [(0, 0, 640, 360, 0, 0), (288, 288, 640, 360, 17, 1),
             (608, 352, 640, 360, 403, 2), (320, 192, 640, 360, 65535, 2),
             (320, 192, 640, 360, 65536, 2), (96, 64, 160, 96, 17, 0),
             (64, 32, 160, 96, 403, 2), (128, 64, 160, 96, 1234, 1),
             (128, 128, 320, 180, 37, 2), (288, 160, 320, 180, 65535, 0),
             (65535, 65535, 640, 360, 0xffffffff, 2),
             (0, 0, 0, 360, 0, 0), (0, 0, 640, 359, 0, 0), (0, 0, 640, 360, 0, 3)]
    expected = []
    for x, y, w, h, frame, load in cases:
        n = 1024 if valid(w, h, load) else 0
        expected.append(str(n))
        if n:
            expected.extend(f'{pixel(x + xx, y + yy, w, h, frame, load):04x}' for yy in range(32) for xx in range(32))
    with tempfile.TemporaryDirectory(prefix='fire-fixed-') as td:
        td = Path(td)
        exe, sim = td / 'reference.exe', td / 'fire.vvp'
        subprocess.run([a.zig, 'cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I' + str(ROOT / 'host'), str(ROOT / 'gfx/tests/fire_fixed_vectors.c'), '-o', str(exe)], check=True, timeout=180)
        inp = ''.join(' '.join(str(v) for v in c) + '\n' for c in cases)
        c_result = subprocess.run([str(exe)], input=inp, text=True, capture_output=True, check=True, timeout=30)
        assert c_result.stdout.split() == expected, 'C/Python Fire mismatch'
        vf, cf = td / 'expected.hex', td / 'cases.txt'
        pixels = []
        for x, y, w, h, frame, load in cases:
            if valid(w, h, load):
                pixels.extend(f'{pixel(x + xx, y + yy, w, h, frame, load):04x}' for yy in range(32) for xx in range(32))
        vf.write_text('\n'.join(pixels) + '\n', encoding='ascii')
        cf.write_text(''.join(' '.join(str(v) for v in c) + (' 1024\n' if valid(c[2], c[3], c[5]) else ' 0\n') for c in cases), encoding='ascii')
        subprocess.run([a.iverilog, '-g2012', '-s', 'tb_fire_tile', '-o', str(sim),
                        str(ROOT / 'gfx/rtl/fire_tile.v'), str(ROOT / 'gfx/tests/tb_fire_tile.v')], check=True, timeout=30, env=env)
        r = subprocess.run([a.vvp, str(sim), '+vectors=' + str(vf), '+cases=' + str(cf), '+words=' + str(len(pixels))], text=True, capture_output=True, timeout=180, env=env)
        if r.returncode:
            raise RuntimeError(r.stdout + r.stderr)
        print('C/Python exact: ' + str(len(pixels)) + ' pixels')
        print(r.stdout.strip())


if __name__ == '__main__':
    main()
