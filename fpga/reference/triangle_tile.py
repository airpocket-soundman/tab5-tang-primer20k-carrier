"""Stateful triangle diagnostic oracle using the independent G0 CPU model."""
from reference.link_protocol import crc_valid, crc16, respond, seal
from reference.game_gpu_reference import Frame, Vertex

INFO, CLEAR, DRAW, READ_COLOR, READ_DEPTH = 0x20, 0x2b, 0x2c, 0x2d, 0x2e
ROW = 0x2f


class TriangleTile:
    def __init__(self):
        self.abort()

    def abort(self):
        self.params = {}
        self.frame = None

    def exchange(self, frame):
        frame = bytes(frame)
        if len(frame) != 8:
            raise ValueError('eight-byte frame required')
        if not crc_valid(frame) or frame[0] != 0xa5 or frame[3] != 2 or frame[1] < INFO:
            return respond(frame)
        op, a, b = frame[1], frame[4], frame[5]
        status, value = 0, a | b << 8
        if op == INFO:
            value = 0x2020
        elif 0x21 <= op <= 0x2a:
            self.params[op - 0x21] = value
        elif op == CLEAR:
            self.frame = Frame(32, 32)
            self.frame.clear(value, 0)
            value = 0
        elif op == DRAW:
            value = 0
            if a or b:
                status = 3
            elif self.frame is None or len(self.params) != 10:
                status = 5
            else:
                def signed(v): return v if v < 32768 else v - 65536
                vertices = [Vertex(signed(self.params[2*i]), signed(self.params[2*i+1]), self.params[6+i])
                            for i in range(3)]
                old = self.frame.depth[:]
                self.frame.triangle(*vertices, self.params[9])
                value = sum(x != y for x, y in zip(old, self.frame.depth))
        elif op == ROW:
            if a >= 32 or b >= 2:
                status, value = 3, 0
            elif self.frame is None:
                status, value = 5, 0
            else:
                prefix = bytes([0x5a, 0, frame[2], 2, a, b])
                plane = self.frame.color if b == 0 else self.frame.depth
                payload = b''.join(v.to_bytes(2, 'little') for v in plane[a*32:a*32+32])
                return seal(prefix) + payload + crc16(prefix+payload).to_bytes(2, 'little')
        elif op in (READ_COLOR, READ_DEPTH):
            value = 0
            if a >= 32 or b >= 32:
                status = 3
            elif self.frame is None:
                status = 5
            else:
                value = (self.frame.color if op == READ_COLOR else self.frame.depth)[b * 32 + a]
        else:
            status, value = 2, 0
        return seal(bytes([0x5a, status, frame[2], 2, value & 255, value >> 8]))
