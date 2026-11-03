"""Compare full color/depth triangle tiles over an explicitly armed serial bridge.

--mock never accesses hardware. Serial mode neither flashes nor selects a profile
implicitly. Output is the last verified FPGA color readback, not a local substitute.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.triangle_tile import TriangleTile, INFO, CLEAR, DRAW, READ_COLOR, READ_DEPTH, ROW
from reference.link_protocol import request, crc_valid, crc16
from tools.dock_gfx_demo import SerialBridge, ppm


def exercise(exchange, comprehensive=True, bulk=False):
    oracle = TriangleTile()
    sequence, commands, draws = 0, 0, 0
    def command(op, a=0, b=0):
        nonlocal sequence, commands
        sent = request(op, sequence, a, b)
        sequence = (sequence + 1) & 255
        expected = oracle.exchange(sent)
        actual = bytes(exchange(sent))
        commands += 1
        valid = crc_valid(actual) if len(actual)==8 else (
            len(actual)==74 and crc_valid(actual[:8]) and
            crc16(actual[:6]+actual[8:72])==int.from_bytes(actual[72:], 'little'))
        if not valid or actual != expected:
            raise RuntimeError(f'op={op:#x} a={a} b={b}: {actual.hex()} expected {expected.hex()}')
        if op==ROW and len(actual)==74:
            return [int.from_bytes(actual[i:i+2], 'little') for i in range(8,72,2)]
        return int.from_bytes(actual[4:6], 'little')
    def word(op, value):
        value &= 65535
        return command(op, value & 255, value >> 8)
    def triangle(xy, z, color):
        nonlocal draws
        for index, value in enumerate([*xy, *z, color]): word(0x21+index, value)
        command(DRAW)
        draws += 1
    def compare():
        if bulk:
            colors = [value for y in range(32) for value in command(ROW,y,0)]
            for y in range(32): command(ROW,y,1)
            return colors
        colors = [command(READ_COLOR, x, y) for y in range(32) for x in range(32)]
        for y in range(32):
            for x in range(32): command(READ_DEPTH, x, y)
        return colors
    command(1)
    command(INFO)
    word(CLEAR, 0x0841)
    triangle([32, 48, 464, 64, 80, 464], [100, 400, 900], 0xf800)
    pixels = compare()
    if comprehensive:
        # Farther draw and equal-depth draw cannot replace the existing image.
        triangle([32, 48, 464, 64, 80, 464], [10, 40, 90], 0x07e0)
        triangle([32, 48, 464, 64, 80, 464], [100, 400, 900], 0xffff)
        pixels = compare()
        # Reverse winding and negative/subpixel coordinates, near overlap.
        triangle([-8, 8, 80, 504, 488, 40], [1200, 1500, 1300], 0x001f)
        pixels = compare()
        # Degenerate triangle is a successful no-op.
        triangle([16, 16, 32, 32, 48, 48], [65535]*3, 0xffff)
        pixels = compare()
        # Two triangles sharing a diagonal use the same top-left ownership rule.
        word(CLEAR, 0)
        triangle([0, 0, 512, 0, 512, 512], [1000]*3, 0xffe0)
        triangle([0, 0, 512, 512, 0, 512], [1000]*3, 0x07ff)
        pixels = compare()
    return pixels, dict(commands=commands, draws=draws, pixels_per_plane=1024,
                        compared_planes=['RGB565', 'depth16'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mock', action='store_true')
    p.add_argument('--port')
    p.add_argument('--arm', action='store_true')
    p.add_argument('--quick', action='store_true', help='One triangle and two full-plane reads')
    p.add_argument('--bulk', action='store_true', help='74-byte row replies; mock only until a row serial bridge is selected')
    p.add_argument('--output', type=Path, default=ROOT/'build/dock-triangle/frame.ppm')
    args = p.parse_args()
    if args.mock and (args.port or args.arm): p.error('--mock cannot use device options')
    if not args.mock and not (args.port and args.arm): p.error('use --mock or --port COMn --arm')
    if args.bulk and not args.mock: p.error('--bulk currently supports --mock; use Tab5 bulk CLI for hardware')
    bridge = None
    try:
        if args.mock:
            exchange = TriangleTile().exchange
        else:
            bridge = SerialBridge(args.port)
            state = bridge.command('status')
            if state.get('profile') != 'dock-jumper-v0' or not state.get('verified'):
                raise RuntimeError('reviewed Dock profile required')
            bridge.command('arm dock-jumper-v0')
            exchange = bridge.exchange
        started = time.monotonic()
        pixels, report = exercise(exchange, not args.quick, args.bulk)
        report['readback'] = 'row74' if args.bulk else 'pixel8'
        report.update(result='passed', mode='mock' if args.mock else 'serial',
                      total_seconds=time.monotonic()-started, output=str(args.output),
                      physical_link_tested=not args.mock)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(ppm(pixels))
        args.output.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(report))
    finally:
        if bridge:
            failed = sys.exc_info()[0] is not None
            try: bridge.close()
            except Exception:
                if not failed: raise


if __name__ == '__main__': main()
