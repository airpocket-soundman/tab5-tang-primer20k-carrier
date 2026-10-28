"""Desktop-only bringup-v0 oracle. No serial/device access; not a timing simulator."""
from dataclasses import dataclass

FRAME_BYTES = 8
ID, ECHO, INVERT = 1, 2, 3
OK, BAD_FRAME, BAD_OPCODE = 0, 1, 2


def byte(value):
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError('expected uint8')
    return value


def crc16(data):
    crc = 0xffff
    for value in data:
        crc ^= byte(value) << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xffff
    return crc


def seal(prefix):
    prefix = bytes(prefix)
    if len(prefix) != 6:
        raise ValueError('six-byte frame prefix required')
    return prefix + crc16(prefix).to_bytes(2, 'little')


def request(opcode, sequence, a=0, b=0):
    return seal(bytes([0xa5, byte(opcode), byte(sequence), 2, byte(a), byte(b)]))


def crc_valid(frame):
    return len(frame) == FRAME_BYTES and int.from_bytes(frame[6:8], 'little') == crc16(frame[:6])


def respond(frame):
    """A complete eight-byte request yields one response, including on format error."""
    frame = bytes(frame)
    if len(frame) != FRAME_BYTES:
        raise ValueError('partial/oversized request has no framed response')
    status, data = OK, bytes(2)
    if frame[0] != 0xa5 or frame[3] != 2 or not crc_valid(frame):
        status = BAD_FRAME
    elif frame[1] == ID:
        data = b'TP'
    elif frame[1] == ECHO:
        data = frame[4:6]
    elif frame[1] == INVERT:
        data = bytes(v ^ 255 for v in frame[4:6])
    else:
        status = BAD_OPCODE
    return seal(bytes([0x5a, status, frame[2], 2]) + data)


def validate_response(frame, sent):
    """Host validation: frame, status, sequence AND operation result must match."""
    frame, sent = bytes(frame), bytes(sent)
    if len(sent) != FRAME_BYTES or sent[1] not in (ID, ECHO, INVERT):
        return False
    if not crc_valid(frame) or frame[:4] != bytes([0x5a, OK, sent[2], 2]):
        return False
    expected = b'TP' if sent[1] == ID else sent[4:6] if sent[1] == ECHO else bytes(v ^ 255 for v in sent[4:6])
    return frame[4:6] == expected


@dataclass
class Endpoint:
    """Byte/strobe lifecycle model after synchronizers have settled.

    Clock-domain synchronizers and electrical bus contention require RTL/hardware
    verification. This model covers the observable framing/state contract only.
    """
    timeout_cycles: int = 100
    armed: bool = False
    reset_n: bool = True
    direction: int = 0

    def __post_init__(self):
        if type(self.timeout_cycles) is not int or self.timeout_cycles < 1:
            raise ValueError('positive timeout required')
        self._clear()

    def _clear(self):
        self.received = bytearray()
        self.response = b''
        self.tx_index = 0
        self.idle_cycles = 0

    @property
    def ready(self):
        return self.armed and self.reset_n and bool(self.response)

    @property
    def output_enabled(self):
        return self.ready and self.direction == 1

    @property
    def output_byte(self):
        return self.response[self.tx_index] if self.output_enabled else None

    def set_arm(self, enabled):
        self.armed = bool(enabled)
        if not self.armed:
            self._clear()

    def set_reset(self, released):
        self.reset_n = bool(released)
        if not self.reset_n:
            self._clear()

    def set_direction(self, direction):
        if type(direction) is not int or direction not in (0, 1):
            raise ValueError('direction must be 0 or 1')
        self.direction = direction
        if direction == 1:
            self.received.clear()  # partial request is discarded

    def advance(self, cycles):
        if type(cycles) is not int or cycles < 0:
            raise ValueError('nonnegative cycle count required')
        if not self.armed or not self.reset_n:
            self._clear()
        elif self.idle_cycles + cycles >= self.timeout_cycles:
            self._clear()
        else:
            self.idle_cycles += cycles

    def rising_strobe(self, incoming=0):
        byte(incoming)
        if not self.armed or not self.reset_n:
            self._clear()
            return
        self.idle_cycles = 0
        if self.direction == 0 and not self.response:
            self.received.append(incoming)
            if len(self.received) == FRAME_BYTES:
                self.response = respond(self.received)
                self.received.clear()
                self.tx_index = 0
        elif self.direction == 1 and self.response:
            self.tx_index += 1
            if self.tx_index == FRAME_BYTES:
                self._clear()


def vectors():
    """Golden requests/replies shared by Python, host C and future RTL runs."""
    pairs = [('id', request(ID, 0))]
    for i in range(256):
        pairs.append((f'echo-{i:03}', request(ECHO, i, i, i ^ 0xa5)))
        pairs.append((f'invert-{i:03}', request(INVERT, i, i, 255-i)))
    for opcode in (0, 4, 127, 255):
        pairs.append((f'unknown-{opcode}', request(opcode, 255, 0x55, 0xaa)))
    base = request(ECHO, 0x73, 0x55, 0xaa)
    for bit in range(64):
        changed = bytearray(base)
        changed[bit//8] ^= 1 << (bit % 8)
        pairs.append((f'bit-corrupt-{bit:02}', bytes(changed)))
    pairs.extend([('bad-magic-crc-correct', seal(bytes([0, ECHO, 255, 2, 0x55, 0xaa]))),
                  ('bad-length-crc-correct', seal(bytes([0xa5, ECHO, 255, 3, 0x55, 0xaa])))])
    return [{'name': name, 'request': sent.hex(), 'response': respond(sent).hex(),
             'host_accept': validate_response(respond(sent), sent)} for name, sent in pairs]
