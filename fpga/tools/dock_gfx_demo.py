"""Draw/read/compare a Dock GFX frame through the ESP-IDF serial xfer bridge.

Does not flash either device. Serial mode requires an explicitly reviewed board
profile and an explicit --arm. --mock performs no device access.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.link_protocol import crc_valid, request
from reference.gfx_bench import GfxBench, INFO, COLOR, CLEAR, PIXEL, READ, ORIGIN, RECT


def exercise(exchange):
    sequence = 0
    def command(op, a=0, b=0):
        nonlocal sequence
        sent = request(op, sequence, a, b)
        sequence = (sequence + 1) & 255
        reply = bytes(exchange(sent))
        if not crc_valid(reply) or reply[:4] != bytes([0x5a, 0, sent[2], 2]):
            raise RuntimeError(f'bad response for opcode {op:#x}: {reply.hex()}')
        return int.from_bytes(reply[4:6], 'little')
    if command(1) != 0x5054 or command(INFO) != 0x2020:
        raise RuntimeError('incompatible LINK/GFX bitstream')
    for value in range(256):
        if command(2, value, value ^ 0xa5) != (value | (value ^ 0xa5) << 8):
            raise RuntimeError('echo mismatch')
        if command(3, value, 255-value) != ((255-value) | value << 8):
            raise RuntimeError('invert mismatch')
    command(COLOR, 0, 0)
    command(CLEAR)
    # Asymmetric rectangles expose X/Y swaps and byte/channel ordering errors.
    rectangles = [(1, 2, 9, 5, 0xf800), (12, 4, 7, 11, 0x07e0),
                  (4, 20, 23, 7, 0x001f), (25, 1, 7, 3, 0xffff)]
    expected = [0] * 1024
    for x, y, w, h, color in rectangles:
        command(COLOR, color & 255, color >> 8)
        command(ORIGIN, x, y)
        command(RECT, w, h)
        for row in range(y, y+h):
            expected[row*32+x:row*32+x+w] = [color] * w
    command(COLOR, 0xe0, 0xff)
    command(PIXEL, 31, 31)
    expected[-1] = 0xffe0
    actual = [command(READ, x, y) for y in range(32) for x in range(32)]
    for index, (want, got) in enumerate(zip(expected, actual)):
        if want != got:
            raise RuntimeError(f'pixel ({index%32},{index//32}): {got:04x}, expected {want:04x}')
    return actual, sequence


def ppm(pixels):
    rgb = bytearray()
    for value in pixels:
        rgb.extend((((value >> 11) & 31) * 255 // 31,
                    ((value >> 5) & 63) * 255 // 63, (value & 31) * 255 // 31))
    return b'P6\n32 32\n255\n' + rgb


class SerialBridge:
    def __init__(self, port):
        import serial
        # Opening a USB port may affect device state. Only created in --arm mode.
        self.port = serial.Serial()
        self.port.port, self.port.baudrate, self.port.timeout = port, 115200, 0.2
        self.port.dtr = self.port.rts = False
        self.port.open()
        self.arm_attempted = False

    def command(self, line):
        if line.startswith('arm '):
            # An arm can succeed even if its acknowledgement is lost.
            self.arm_attempted = True
        self.port.reset_input_buffer()
        self.port.write((line + '\n').encode('ascii'))
        self.port.flush()
        until = time.monotonic() + 5
        while time.monotonic() < until:
            text = self.port.readline().decode('utf-8', errors='replace').strip()
            if not text.startswith('{'):
                continue
            result = json.loads(text)
            if not isinstance(result, dict) or 'service' in result:
                continue
            if line.startswith('xfer '):
                _, op, seq, _, _ = line.split()
                if ('op' in result and result['op'] != int(op)) or ('seq' in result and result['seq'] != int(seq)):
                    continue
            if result.get('error') or result.get('ok') is False:
                raise RuntimeError(result)
            if line.startswith('xfer '):
                if result.get('op') != int(op) or result.get('seq') != int(seq) or 'frame' not in result:
                    continue
            elif line == 'status':
                if not all(k in result for k in ('armed', 'profile', 'verified')):
                    continue
            elif line.startswith('arm '):
                if result.get('armed') is not True or 'profile' in result:
                    continue
            elif line == 'disarm':
                if result.get('armed') is not False or 'profile' in result:
                    continue
            return result
        raise TimeoutError(f'no response to {line}')

    def exchange(self, sent):
        # Send the request sequence too, so host and PC validate the same frame.
        result = self.command(f'xfer {sent[1]} {sent[2]} {sent[4]} {sent[5]}')
        return bytes.fromhex(result['frame'])

    def close(self):
        try:
            if self.arm_attempted:
                self.command('disarm')
        finally:
            self.port.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mock', action='store_true')
    parser.add_argument('--port')
    parser.add_argument('--arm', action='store_true', help='Enable reviewed Dock GPIO profile')
    parser.add_argument('--output', type=Path, default=ROOT/'build/dock-gfx/frame.ppm')
    args = parser.parse_args()
    if args.mock and (args.port or args.arm):
        parser.error('--mock cannot be combined with device options')
    if not args.mock and not (args.port and args.arm):
        parser.error('use --mock, or --port COMn --arm after wiring review')
    bridge = None
    try:
        if args.mock:
            exchange = GfxBench().exchange
        else:
            bridge = SerialBridge(args.port)
            state = bridge.command('status')
            if state.get('profile') != 'dock-jumper-v0' or not state.get('verified'):
                raise RuntimeError('Dock profile is not enabled in the ESP-IDF build')
            if not bridge.command('arm dock-jumper-v0').get('armed'):
                raise RuntimeError('could not arm')
            exchange = bridge.exchange
        pixels, _ = exercise(exchange)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(ppm(pixels))
        print(json.dumps(dict(result='passed', mode='mock' if args.mock else 'serial',
                              pixels=1024, output=str(args.output))))
    finally:
        if bridge is not None:
            if sys.exc_info()[0] is None:
                bridge.close()
            else:
                try:
                    bridge.close()
                except Exception:
                    pass  # Preserve the original failure.


if __name__ == '__main__':
    main()
