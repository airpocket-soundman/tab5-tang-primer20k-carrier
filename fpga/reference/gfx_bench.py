"""Independent stateful oracle for the Dock GFX diagnostic protocol."""
from reference.link_protocol import crc_valid, respond, seal

INFO, COLOR, CLEAR, PIXEL, READ, ORIGIN, RECT = range(0x10, 0x17)


class GfxBench:
    def __init__(self):
        self.color = 0xffff
        self.origin = (0, 0)
        self.pixels = None

    def exchange(self, frame):
        frame = bytes(frame)
        if len(frame) != 8:
            raise ValueError('eight-byte request required')
        if not crc_valid(frame) or frame[0] != 0xa5 or frame[3] != 2 or frame[1] < INFO:
            return respond(frame)
        op, a, b = frame[1], frame[4], frame[5]
        status, value = 0, a | b << 8
        if op == INFO:
            value = 0x2020
        elif op == COLOR:
            self.color = value
        elif op == CLEAR:
            self.pixels = [self.color] * 1024
            self.origin = (0, 0)
            value = 0
        elif op in (PIXEL, READ, ORIGIN):
            if a >= 32 or b >= 32:
                status, value = 3, 0
            elif op == ORIGIN:
                self.origin = (a, b)
            elif self.pixels is None:
                status, value = 5, 0
            elif op == READ:
                value = self.pixels[b * 32 + a]
            else:
                self.pixels[b * 32 + a] = self.color
        elif op == RECT:
            x, y = self.origin
            if not a or not b or x + a > 32 or y + b > 32:
                status, value = 3, 0
            elif self.pixels is None:
                status, value = 5, 0
            else:
                for row in range(y, y + b):
                    for col in range(x, x + a):
                        self.pixels[row * 32 + col] = self.color
        else:
            status, value = 2, 0
        return seal(bytes([0x5a, status, frame[2], 2, value & 255, value >> 8]))
