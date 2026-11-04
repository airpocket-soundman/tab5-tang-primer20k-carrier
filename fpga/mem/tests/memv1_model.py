"""Bit-level reference model of MEMV1 (docs/MEMV1_プロトコル仕様_v1確定案_2026-11-05.md) and test-vector generator.

Independent of the RTL and of the C codec: only Python (zlib for CRC32, a bitwise CRC16-CCITT-FALSE).
The model is a pure function request-bytes -> response-bytes plus a sparse 16-byte-beat memory. It models the
normal state (calibrated, no BIST running, no reset/cancel); reset, cancel, generation changes and stalls are
exercised by hand-written RTL benches.

  python memv1_model.py --selftest
  python memv1_model.py --vectors fpga/build/memv1-tests/memv1_vectors.hex   (one hex byte per line, $readmemh)
Vector file records: lenQ(le16) lenR(le16) Q... R... ; terminated by lenQ=0.
"""
import argparse
import random
import zlib
from pathlib import Path

CAPACITY = 134217728
MAX_BEATS = 256
FORMAT = 0x4d31
OP = dict(ID=1, ECHO=2, INVERT=3, LCAPS=4, CAPS=0x60, STATUS=0x61, RD=0x62, WR=0x63, FILL=0x64, COPY=0x65,
          CRC32=0x66, CANCEL=0x67, MEM_CAPS=0x50)
ST = dict(OK=0, FORMAT=1, UNKNOWN=2, INVALID=3, TIMEOUT=4, NOT_READY=5, BUSY=6, CRC_ERROR=7, CANCELLED=8,
          DDR_FAULT=9, STALE=10)


def crc16(data, seed=0xffff):
    c = seed
    for b in data:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xffff if c & 0x8000 else (c << 1) & 0xffff
    return c


def crc32(data, prev=0):
    """zlib-style chaining: prev is a finalized CRC32 (0 for a new message)."""
    c = prev ^ 0xffffffff
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xedb88320 if c & 1 else c >> 1
    return c ^ 0xffffffff


def frame(op, seq, a=0, b=0, tagged=False):
    h = bytes([0xa5, op | (0x80 if tagged else 0), seq & 255, 2, a & 255, b & 255])
    return h + crc16(h).to_bytes(2, 'little')


def ext_request(op, seq, beats, addr, arg=0, payload=b'', tagged=False):
    h = frame(op, seq, beats & 255, beats >> 8, tagged)
    body = addr.to_bytes(4, 'little') + (arg & 0xffffffff).to_bytes(4, 'little') + payload
    c = crc16(h[:6] + body)
    return h + body + c.to_bytes(2, 'little')


def reply(status, seq, r0=0, r1=0, tagged=False):
    h = bytes([0x5a, status, seq & 255, 2, r0 & 255, r1 & 255])
    return (b'\xc3' * 8 if tagged else b'') + h + crc16(h).to_bytes(2, 'little')


def ext_reply(seq, gen, payload, tagged=False):
    h = bytes([0x5a, 0, seq & 255, 2, gen & 255, gen >> 8])
    return (b'\xc3' * 8 if tagged else b'') + h + crc16(h).to_bytes(2, 'little') + payload + \
        crc16(h + payload).to_bytes(2, 'little')


class Model:
    def __init__(self, gen):
        self.gen = gen
        self.beats = {}  # beat index -> 16 bytes
        self.ops = 0
        self.last_status = 0

    def read(self, addr, n):
        return b''.join(self.beats[addr // 16 + i] for i in range(n))

    def caps_word(self, i):
        return {0: FORMAT, 1: 0x0100, 2: 128, 3: 16, 4: 256, 5: 0x0073, 6: 1, 7: 0x000c}.get(i)

    def status_word(self, i):
        return {0: 0x0003, 1: self.gen, 2: self.last_status, 3: self.ops & 0xffff, 4: 0, 5: 0, 6: 0}.get(i)

    def handle(self, q):
        """Response bytes for the complete request bytes q (header [+ extended body])."""
        tagged = bool(q[1] & 0x80)
        op, seq = q[1] & 0x7f, q[2]
        if len(q) < 8 or q[0] != 0xa5 or q[3] != 2 or q[6:8] != crc16(q[:6]).to_bytes(2, 'little'):
            return reply(ST['FORMAT'], seq)  # untagged: prefix only after a valid header
        a, b = q[4], q[5]
        r = lambda s, v=0: reply(s, seq, v & 255, v >> 8, tagged)
        if op == 1:
            return r(0, 0x5054)
        if op == 2:
            return r(0, a | b << 8)
        if op == 3:
            return r(0, (~(a | b << 8)) & 0xffff)
        if op == 4:
            return r(0, 0x0108)
        if op == OP['CAPS']:
            v = self.caps_word(a) if b == 0 else None
            return r(ST['INVALID']) if v is None else r(0, v)
        if op == OP['STATUS']:
            v = self.status_word(a) if b == 0 else None
            return r(ST['INVALID']) if v is None else r(0, v)
        if op == OP['CANCEL']:
            return r(0, 0) if a == 0 and b == 0 else r(ST['INVALID'])
        if op in (OP['FILL'], OP['COPY']):
            return r(ST['UNKNOWN'])
        if op in (OP['RD'], OP['WR'], OP['CRC32']):
            beats = a | b << 8
            if beats == 0 or beats > MAX_BEATS:
                return r(ST['INVALID'])
            n_pay = beats * 16 if op == OP['WR'] else 0
            if len(q) != 8 + 8 + n_pay + 2:
                raise ValueError('malformed extended request in model input')
            body, trailer = q[8:-2], q[-2:]
            if trailer != crc16(q[:6] + body).to_bytes(2, 'little'):
                return r(ST['CRC_ERROR'])
            addr = int.from_bytes(body[0:4], 'little')
            arg = int.from_bytes(body[4:8], 'little')
            payload = body[8:]
            if addr % 16 or addr + beats * 16 > CAPACITY or (op == OP['RD'] and arg):
                return r(ST['INVALID'])
            if op == OP['WR'] and crc32(payload) != arg:
                return r(ST['CRC_ERROR'])
            self.ops += 1
            self.last_status = 0
            if op == OP['WR']:
                for i in range(beats):
                    self.beats[addr // 16 + i] = payload[16 * i:16 * i + 16]
                return reply(0, seq, self.gen & 255, self.gen >> 8, tagged)
            data = self.read(addr, beats)
            if op == OP['RD']:
                return ext_reply(seq, self.gen, data, tagged)
            return ext_reply(seq, self.gen, crc32(data, arg).to_bytes(4, 'little'), tagged)
        return r(ST['UNKNOWN'])


def selftest():
    assert crc16(b'123456789') == 0x29b1
    assert crc32(b'123456789') == 0xcbf43926 == zlib.crc32(b'123456789')
    d = bytes(range(200))
    assert crc32(d[100:], crc32(d[:100])) == zlib.crc32(d)  # chaining == zlib continuation
    m = Model(1)
    p = bytes(range(32))
    assert m.handle(ext_request(OP['WR'], 1, 2, 0x100, crc32(p), p)) == reply(0, 1, 1, 0)
    assert m.handle(ext_request(OP['RD'], 2, 2, 0x100)) == ext_reply(2, 1, p)
    assert m.handle(ext_request(OP['CRC32'], 3, 2, 0x100, 0)) == ext_reply(3, 1, crc32(p).to_bytes(4, 'little'))
    print('PASS memv1_model selftest')


def vectors(rng):
    G = 1  # RTL generation after the bench's initial reset
    m = Model(G)
    rec = []

    def ex(q, resp=None):
        rec.append((q, m.handle(q) if resp is None else resp))
    seq = [0]

    def nxt():
        seq[0] = (seq[0] + 1) & 255
        return seq[0]
    ex(frame(OP['STATUS'], nxt(), 1))  # generation word must equal G
    ex(frame(1, nxt())); ex(frame(2, nxt(), 0x5a, 0xa5)); ex(frame(3, nxt(), 0x5a, 0xa5)); ex(frame(4, nxt()))
    ex(frame(OP['MEM_CAPS'], nxt()))
    rec[-1] = (rec[-1][0], reply(0, seq[0], 0x4d, 0x01))  # legacy MEM_CAPS 0x014d
    ex(frame(0x82, nxt(), 1, 2, True)); ex(frame(OP['CAPS'], nxt(), 0, 0, True))
    for i in range(9):
        ex(frame(OP['CAPS'], nxt(), i))
    ex(frame(OP['CAPS'], nxt(), 0, 1))
    for i in range(8):
        ex(frame(OP['STATUS'], nxt(), i))
    ex(frame(OP['CANCEL'], nxt())); ex(frame(OP['CANCEL'], nxt(), 1)); ex(frame(OP['FILL'], nxt(), 1)); ex(frame(OP['COPY'], nxt(), 1))
    ex(frame(0x6f, nxt())); ex(frame(0x5d, nxt()))
    bad = bytearray(frame(OP['CAPS'], nxt())); bad[7] ^= 1
    ex(bytes(bad))

    def wr(addr, n, tag=False, data=None):
        p = data if data is not None else bytes(rng.randrange(256) for _ in range(16 * n))
        ex(ext_request(OP['WR'], nxt(), n, addr, crc32(p), p, tag))
        return p
    # round trips
    p1 = wr(0, 1)
    ex(ext_request(OP['RD'], nxt(), 1, 0))
    ex(ext_request(OP['CRC32'], nxt(), 1, 0, 0))
    p2 = wr(0x10000, 256, tag=True)
    ex(ext_request(OP['RD'], nxt(), 256, 0x10000, 0, b'', True))
    ex(ext_request(OP['RD'], nxt(), 16, 0x10100))
    ex(ext_request(OP['RD'], nxt(), 2, 0x10fe0, 0, b'', True))
    full = crc32(p2)
    ex(ext_request(OP['CRC32'], nxt(), 256, 0x10000, 0))
    h1 = crc32(p2[:2048])
    ex(ext_request(OP['CRC32'], nxt(), 128, 0x10000, 0))
    ex(ext_request(OP['CRC32'], nxt(), 128, 0x10800, h1))  # chained == full
    assert crc32(p2[2048:], h1) == full
    wr(0x7fff000, 256)  # last 4 KiB of the 128 MiB
    ex(ext_request(OP['RD'], nxt(), 256, 0x7fff000))
    wr(0x7fffff0, 1)
    ex(ext_request(OP['RD'], nxt(), 1, 0x7fffff0))
    for k in range(3):  # overwrite + partial overlap
        wr(0x20000 + 16 * k, 8)
    ex(ext_request(OP['RD'], nxt(), 10, 0x20000))
    # rejected requests (memory must be unchanged afterwards)
    junk = bytes(range(32))
    ex(ext_request(OP['WR'], nxt(), 2, 0x10001, crc32(junk), junk))  # unaligned
    ex(ext_request(OP['WR'], nxt(), 2, 0x7fffff0, crc32(junk), junk))  # one beat past the end
    ex(ext_request(OP['WR'], nxt(), 2, 0xfffffff0, crc32(junk), junk))  # 32-bit wrap
    ex(ext_request(OP['WR'], nxt(), 2, 0x8000000, crc32(junk), junk))  # at capacity
    ex(ext_request(OP['RD'], nxt(), 1, 0x8000000))
    ex(ext_request(OP['RD'], nxt(), 2, 0x7fffff0))
    ex(ext_request(OP['CRC32'], nxt(), 1, 0x7fffff8))
    ex(ext_request(OP['RD'], nxt(), 1, 0x10000, 5))  # RD reserved arg must be 0
    ex(frame(OP['WR'], nxt(), 0, 0)); ex(frame(OP['RD'], nxt(), 0, 0)); ex(frame(OP['CRC32'], nxt(), 0, 0))  # beats 0 (header only)
    ex(frame(OP['WR'], nxt(), 1, 1)); ex(frame(OP['RD'], nxt(), 1, 1)); ex(frame(OP['WR'], nxt(), 0xff, 0xff))  # beats > 256
    ex(ext_request(OP['WR'], nxt(), 2, 0x30000, crc32(junk) ^ 1, junk))  # payload CRC32 mismatch
    ex(ext_request(OP['WR'], nxt(), 1, 0, crc32(p1) ^ 0x80000000, p1))
    ex(ext_request(OP['RD'], nxt(), 1, 0))  # still p1
    tbad = bytearray(ext_request(OP['WR'], nxt(), 2, 0x0, crc32(junk), junk)); tbad[-1] ^= 0x40
    ex(bytes(tbad))  # trailer CRC16 mismatch
    pbad = bytearray(ext_request(OP['WR'], nxt(), 2, 0x0, crc32(junk), junk)); pbad[20] ^= 1
    ex(bytes(pbad))  # payload bit flip -> trailer mismatch
    dbad = bytearray(ext_request(OP['RD'], nxt(), 1, 0x0)); dbad[9] ^= 1
    ex(bytes(dbad))  # descriptor bit flip -> trailer mismatch
    ex(ext_request(OP['RD'], nxt(), 1, 0))
    # random fuzz of legal + illegal ranges, small
    for _ in range(40):
        n = rng.choice([1, 2, 3, 7, 16, 33])
        addr = rng.choice([0x40000, 0x50000, 0x60000]) + 16 * rng.randrange(0, 64)
        wr(addr, n, tag=rng.random() < 0.3)
        a2 = addr
        ex(ext_request(OP['RD'], nxt(), n, a2, 0, b'', rng.random() < 0.3))
        ex(ext_request(OP['CRC32'], nxt(), n, a2, rng.choice([0, 0x12345678])))
    return rec


def write_vectors(path, rng_seed=0x4d315):
    rec = vectors(random.Random(rng_seed))
    out = bytearray()
    for q, r in rec:
        out += len(q).to_bytes(2, 'little') + len(r).to_bytes(2, 'little') + q + r
    out += b'\0\0\0\0'
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('\n'.join('%02x' % b for b in out) + '\n')
    return len(rec), len(out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--vectors')
    a = ap.parse_args()
    if a.selftest:
        selftest()
    if a.vectors:
        n, size = write_vectors(a.vectors)
        print('wrote %d records, %d bytes' % (n, size))
