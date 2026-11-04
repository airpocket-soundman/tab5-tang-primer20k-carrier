"""MEMV1 image check through the existing ESP-IDF serial xfer bridge (8-byte LINK frames only).

Replaces the MEM probe for the first look at the memv1 image: LINK ID, MEMV1 CAPS words, STATUS words (calibrated,
USER alive, BIST, generation) and optionally the old BIST via the legacy ops 0x50..0x5c. Extended RD/WR/CRC32
frames (up to 4 KiB) need a long-frame command in the Tab5 bridge that does NOT exist yet; this tool therefore
never claims a RD/WR result. Link speed must stay <= 500 kHz (SYS-synchronized PHY).

  python fpga/tools/memv1_probe.py --mock                       # offline: reference model as the device
  python fpga/tools/memv1_probe.py --port COM4 --arm            # real device, reviewed Dock profile only
  python fpga/tools/memv1_probe.py --port COM4 --arm --bist 1024 --seed 0x1234
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'mem/tests'))
sys.path.insert(0, str(ROOT / 'tools'))
import memv1_model as model  # noqa: E402

FEATURES = {1: 'RD', 2: 'WR', 4: 'FILL', 8: 'COPY', 16: 'CRC32', 32: 'BIST', 64: 'CANCEL'}


class Link:
    def __init__(self, exchange):
        self.exchange, self.seq = exchange, 0x20

    def op(self, op, a=0, b=0):
        self.seq = (self.seq + 1) & 255
        q = model.frame(op, self.seq, a, b)
        r = self.exchange(q)
        if len(r) != 8 or r[0] != 0x5a or r[2] != self.seq or r[3] != 2 or r[6:8] != model.crc16(r[:6]).to_bytes(2, 'little'):
            raise RuntimeError(f'malformed reply to op {op:#x}: {r.hex()}')
        return r[1], r[4] | r[5] << 8


def check(link, bist_beats=0, seed=0x1234):
    out = {}
    st, v = link.op(1)
    assert st == 0 and v == 0x5054, ('LINK ID', st, v)
    caps = []
    for i in range(8):
        st, v = link.op(model.OP['CAPS'], i)
        assert st == 0, ('CAPS', i, st)
        caps.append(v)
    assert caps[0] == model.FORMAT, f'not a MEMV1 image: CAPS format {caps[0]:#06x}'
    assert caps[3] == 16 and caps[4] == 256, caps
    out['caps'] = dict(format=hex(caps[0]), version=hex(caps[1]), capacity_mib=caps[2], align=caps[3], max_beats=caps[4],
                       features=[n for m, n in FEATURES.items() if caps[5] & m], regions=caps[6], spec_only=hex(caps[7]))
    assert link.op(model.OP['CAPS'], 8)[0] == 3  # out-of-range word index is INVALID, not UNKNOWN
    words = [link.op(model.OP['STATUS'], i)[1] for i in range(7)]
    out['status'] = dict(flags=words[0], calibrated=bool(words[0] & 1), user_alive=bool(words[0] & 2), inflight=bool(words[0] & 4),
                         bist_active=bool(words[0] & 8), undefined_range=bool(words[0] & 16), generation=words[1],
                         last_status=words[2], ops=words[3])
    st, v = link.op(model.OP['FILL'], 1)
    assert st == 2, 'FILL is spec-only and must answer UNKNOWN'
    st, v = link.op(model.OP['CANCEL'])
    assert st == 0 and v == 0  # nothing running
    st, v = link.op(0x50)
    out['legacy_mem_caps'] = hex(v)
    assert st == 0 and v == 0x014d
    if bist_beats:
        if not out['status']['calibrated']:
            raise RuntimeError('DDR3 not calibrated; BIST would be rejected')
        for op, val in ((0x51, 0), (0x52, 0), (0x53, bist_beats & 0xffff), (0x54, bist_beats >> 16),
                        (0x55, seed & 0xffff), (0x56, seed >> 16 & 0xffff)):
            st, v = link.op(op, val & 255, val >> 8)
            assert st == 0, ('BIST setup', hex(op), st)
        st, _ = link.op(0x57)
        assert st == 0, ('BIST start', st)
        deadline = time.monotonic() + 90
        while True:
            assert link.op(0x58)[0] == 0
            st, flags = link.op(0x59, 0)
            if flags & 4:
                break
            if time.monotonic() > deadline:
                raise TimeoutError('BIST did not finish in 90 s')
            time.sleep(0.2)
        out['bist'] = dict(beats=bist_beats, flags=hex(flags), done=True, faulted=bool(flags & 8), errors=bool(flags & 16))
        assert not (flags & 8) and not (flags & 16), out['bist']
    return out


class MockDevice:
    """The reference model standing in for a device (8-byte ops only)."""
    def __init__(self):
        self.m = model.Model(1)

    def exchange(self, q):
        if (q[1] & 0x7f) == 0x50:
            return model.reply(0, q[2], 0x4d, 0x01)
        return self.m.handle(bytes(q))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mock', action='store_true')
    p.add_argument('--port')
    p.add_argument('--arm', action='store_true', help='enable the reviewed dock-jumper-v0 GPIO profile')
    p.add_argument('--bist', type=int, default=0, help='beats of the legacy BIST to run (0 = none)')
    p.add_argument('--seed', type=lambda s: int(s, 0), default=0x1234)
    a = p.parse_args()
    if a.mock == bool(a.port):
        p.error('use exactly one of --mock or --port COMn --arm')
    if a.port and not a.arm:
        p.error('--port requires --arm (wiring reviewed)')
    if a.mock and a.bist:
        p.error('--bist needs a real device')
    bridge = None
    try:
        if a.mock:
            exchange = MockDevice().exchange
        else:
            import dock_gfx_demo as demo
            bridge = demo.SerialBridge(a.port)
            state = bridge.command('status')
            if state.get('profile') != 'dock-jumper-v0' or not state.get('verified'):
                raise RuntimeError('Dock profile is not enabled in the ESP-IDF build')
            if not bridge.command('arm dock-jumper-v0').get('armed'):
                raise RuntimeError('could not arm')
            exchange = bridge.exchange
        print(json.dumps(check(Link(exchange), a.bist, a.seed), indent=1))
    finally:
        if bridge is not None:
            bridge.close()


if __name__ == '__main__':
    main()
