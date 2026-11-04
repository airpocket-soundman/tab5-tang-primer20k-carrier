"""Bit-level reference model of the DDR3 bandwidth engine mem_bw (fpga/mem/rtl/mem_bw.v) and of the tb_mem_bw.v memory shim.

Written from the documented behaviour (fpga/mem/BW_ENGINE.md), not from the RTL source. tb_mem_bw.v prints one
`BWRES ...` line per job; this module recomputes every field independently:
  * command byte addresses of all patterns (incl. strided runs and burst length) -> FNV hash `wh` / `rh`
  * the xorshift data stream, the rolling checksums ck_wr / ck_rd / ck_exp (128 bit), shim memory read-back
  * the cycle counters: cnt_cycles, cmd_stall, wd_stall (greedy issue against the shim's ready pattern),
    read-latency sampler (lat_sum / lat_samples / lat_max)
  * mixed mode on the ideal shim: 2 cycles per command (one idle cycle after each accepted command)

EN_PIPE (mem_bw parameter, native-enable structure):
  0 original and 1 registered enables: identical cycle behaviour (one command / data beat per cycle when ready).
  2 BIST-PIPELINE=4 style: every accepted command or data beat blocks the NEXT cycle (stale-want block), so the issue spacing is
    2 cycles (STEP = 2). Cycle definitions are unchanged (first accepted command .. last data beat, both included); with the issue
    times t_k of the accepted commands / beats the span is last_fire - first_fire + 1. Ideal shim, N beats, burst L:
      write_stream : cnt_cycles = 2*N - 1        (N beats, every beat takes STEP cycles, the last one has no trailing idle cycle)
      read_stream  : cnt_cycles = 2*(N/L - 1) + lat + L   (commands every 2 cycles, L data beats per command arrive back to back)
    versus N and N + lat (L=1) for EN_PIPE 0/1. Stall counters only count unblocked cycles (the idle cycle is not a stall).
    Mixed mode is unchanged (it already inserted one idle cycle per accepted command): 2 cycles per command, ideal shim
      cnt_cycles = 4*ncmd + lat - 1   (ncmd = number of write/read PAIRS; 2*ncmd commands in total).
  With a stalling shim the stall counters count only unblocked cycles (the idle cycle after an acceptance is never a stall); the span
  is computed by the greedy issue simulation write_cycles()/read_cycles() with STEP = 2 after every accepted command / data beat.
It models the engine in USER clock cycles only. It is simulation evidence; it says nothing about the real DDR3 IP.
"""
import re

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1
BASE_MASK = (1 << 27) - 1


def xs32(x):
    x &= M32
    x ^= (x << 13) & M32
    x ^= x >> 17
    x ^= (x << 5) & M32
    return x


def lane0(s, k):
    v = (s ^ k) & M32
    return k if v == 0 else v


def data_stream(seed, n):
    """128-bit beats {lane3,lane2,lane1,lane0}, one new beat per accepted write (and per expected beat)."""
    x = [lane0(seed, 0x9E3779B9), lane0(seed, 0x243F6A88), lane0(seed, 0xB7E15162), lane0(seed, 0x85EBCA6B)]
    out = []
    for _ in range(n):
        out.append(x[0] | (x[1] << 32) | (x[2] << 64) | (x[3] << 96))
        x = [xs32(v) for v in x]
    return out


def checksum(beats):
    """ck = {b, a}; fold = hi64 ^ lo64; a += fold; b = rotl1(b) ^ fold."""
    a = b = 0
    for d in beats:
        f = (d >> 64) ^ (d & M64)
        a = (a + f) & M64
        b = (((b << 1) | (b >> 63)) & M64) ^ f
    return (b << 64) | a


def cmd_addresses(pat, ncmd, base, region_log2, seed, bl, run, stride):
    """Byte address of the first beat of every command. L = 1<<bl beats per command."""
    L = 1 << bl
    m = (1 << region_log2) - 1
    out = []
    x = seed if seed != 0 else 0x2545F491
    for k in range(ncmd):
        ib = (k * L) & 0x7FFFFF              # beat index of the first beat
        if pat == 0:
            p = ib
        elif pat == 1:
            p = ((ib >> 10) << 10) | ((ib & 7) << 7) | ((ib >> 3) & 127)   # bank=i[2:0] (byte[13:11]), col group i[9:3], row i[22:10]
        elif pat == 2:
            p = ((ib & 0x1FFF) << 10) | (ib >> 13)
        elif pat == 3:
            p = ((x >> 9) & m) & ~(L - 1) & 0x7FFFFF
        elif pat == 4:
            p = (((k * 0x4F1BBD) & 0x7FFFFF) & (m >> bl)) << bl
        elif pat == 5:
            p = ((k // run) * stride + (k % run) * L) & 0x7FFFFF
        else:
            raise ValueError(pat)
        out.append(((p << 4) + base) & BASE_MASK)
        x = xs32(x)
    return out


def beat_addresses(cmds, bl):
    L = 1 << bl
    return [(a + 16 * j) & BASE_MASK for a in cmds for j in range(L)]


def fnv(addrs):
    h = 0x811C9DC5
    for a in addrs:
        h = ((h ^ a) * 0x01000193) & M32
    return h


def ready(sh, n):
    """(cmd_ready, write_ready) seen at clock edge number n (the shim drives them from the previous edge count)."""
    if sh == 1:
        return ((n - 1) % 5 != 0), ((n - 1) % 7 < 3)
    return True, True


def write_cycles(sh, first, ncmd, L, step=1):
    t = first
    cs = ws = 0
    for _ in range(ncmd):
        while True:
            cr, wr = ready(sh, t)
            if cr and wr:
                break
            cs += (not cr)
            ws += (not wr)
            t += 1
        t += step
        for _ in range(L - 1):
            while not ready(sh, t)[1]:
                ws += 1
                t += 1
            t += step
    last = t - step
    return last, cs, ws


def read_cycles(sh, first, lat, ncmd, L, step=1):
    t = first
    cs = 0
    issue = []
    for _ in range(ncmd):
        while not ready(sh, t)[0]:
            cs += 1
            t += 1
        issue.append(t)
        t += step
    valid = set()
    prev = -1
    for k, ti in enumerate(issue):
        for j in range(L):
            due = ti + lat + j + ((k % 4) if sh == 1 else 0)
            d = max(due, prev + 1)
            valid.add(d)
            prev = d
    last = prev
    fires = set(issue)
    rd_out = 0
    busy = False
    left = start = 0
    ssum = sn = smax = 0
    for t in range(first, last + 1):
        v = t in valid
        f = t in fires
        nz = rd_out > 0
        if busy and v and left == 0:
            lt = t - start
            ssum += lt
            sn += 1
            smax = max(smax, lt)
            busy = False
        elif busy and v:
            left -= 1
        elif (not busy) and f:
            busy = True
            start = t
            left = rd_out - (1 if v else 0)
        rd_out += (L if f else 0) - (1 if (v and nz) else 0)
    return last, cs, ssum, sn, smax


class Model:
    def __init__(self, paired, enpipe=0):
        self.paired = paired
        self.step = 2 if enpipe >= 2 else 1
        self.mem = {}
        self.errors = []

    def clear(self):
        self.mem = {}

    def expect(self, r, name, got, want):
        if got != want:
            self.errors.append(f"{r['nm']}: {name} dut={got!r} model={want!r} (line: {r['_line'][:160]})")

    @staticmethod
    def hashes(r, e, wh, rh):
        if 'wh' in r:   # top-level (LINK) records carry no address hashes
            e('wh', int(r['wh'], 16), wh); e('rh', int(r['rh'], 16), rh)

    @staticmethod
    def last(r, e, last):
        if 'last' in r:
            e('last_cycle', r['last'], last)

    def job(self, r):
        mode, pat, bl = r['mode'], r['pat'], r['blg']
        L = 1 << bl
        n = r['count']
        ncmd = n >> bl
        seed = r['seed']
        cmds = cmd_addresses(pat, ncmd, r['base'], r['rl'], seed, bl, r['run'], r['stride'])
        data = data_stream(seed, n)
        beats = beat_addresses(cmds, bl)
        e = lambda name, got, want: self.expect(r, name, got, want)
        cke = checksum(data)
        e('ck_exp', int(r['cke'], 16), cke)
        e('err', r['err'], 0)
        if mode == 0:
            for a, d in zip(beats, data):
                self.mem[a >> 4] = d
            e('cmds', r['cmds'], ncmd); e('wbeats', r['wb'], n); e('rbeats', r['rb'], 0)
            e('ck_wr', int(r['ckw'], 16), cke); e('ck_rd', int(r['ckr'], 16), 0)
            e('wr_match', r['wrok'], 1); e('rd_match', r['rdok'], 0)
            self.hashes(r, e, fnv(cmds), fnv([]))
            e('lat_samples', r['latn'], 0)
            if self.paired and r['sh'] in (0, 1):
                last, cs, ws = write_cycles(r['sh'], r['first'], ncmd, L, self.step)
                self.last(r, e, last)
                e('cnt_cycles', r['cyc'], last - r['first'] + 1); e('cmd_stall', r['cs'], cs); e('wd_stall', r['ws'], ws)
        elif mode == 1:
            rd = [self.mem.get(a >> 4, 0xDEADBEEF_DEADBEEF_DEADBEEF_DEADBEEF) for a in beats]
            ckr = checksum(rd)
            e('cmds', r['cmds'], ncmd); e('wbeats', r['wb'], 0); e('rbeats', r['rb'], n)
            e('ck_wr', int(r['ckw'], 16), 0); e('ck_rd', int(r['ckr'], 16), ckr)
            e('wr_match', r['wrok'], 0); e('rd_match', r['rdok'], int(ckr == cke))
            self.hashes(r, e, fnv([]), fnv(cmds))
            if True:   # the read side has no write pairing: same timing in both configurations
                if r['sh'] in (0, 1):
                    last, cs, ssum, sn, smax = read_cycles(r['sh'], r['first'], r['lat'], ncmd, L, self.step)
                    self.last(r, e, last)
                    e('cnt_cycles', r['cyc'], last - r['first'] + 1); e('cmd_stall', r['cs'], cs); e('wd_stall', r['ws'], 0)
                    e('lat_sum', r['latsum'], ssum); e('lat_samples', r['latn'], sn); e('lat_max', r['latmax'], smax)
        elif mode == 2:
            assert bl == 0
            uniq = len(set(a >> 4 for a in beats)) == len(beats)
            for a, d in zip(beats, data):
                self.mem[a >> 4] = d
            e('cmds', r['cmds'], 2 * ncmd); e('wbeats', r['wb'], n); e('rbeats', r['rb'], n)
            e('ck_wr', int(r['ckw'], 16), cke); e('wr_match', r['wrok'], 1)
            self.hashes(r, e, fnv(cmds), fnv(cmds))
            if uniq:
                e('ck_rd', int(r['ckr'], 16), cke); e('rd_match', r['rdok'], 1)
            if r['sh'] == 0:
                e('cnt_cycles', r['cyc'], 4 * ncmd + r['lat'] - 1)   # 2 commands per pair x 2 cycles/command, minus 1, plus read latency
        else:
            raise ValueError(mode)


def parse(line):
    r = {'_line': line}
    for k, v in re.findall(r'(\w+)=(\S+)', line):
        r[k] = v if k in ('nm', 'tag', 'words', 'ckw', 'ckr', 'cke', 'wh', 'rh') else int(v)
    return r


def parse_port(line):
    """PORTSNAP line of tb_mem_bw_top: 62 snapshot words of mem_bw_port -> the same record layout as a BWRES line."""
    r = parse(line)
    wh = r.pop('words')
    r['nm'] = r.pop('tag')
    w = [int(wh[i:i + 4], 16) for i in range(0, len(wh), 4)]
    assert len(w) == 62, len(w)
    val = lambda o, n: sum(w[o + k] << (16 * k) for k in range(n))
    r.update(sh=0, lat=6, first=1000, paired=1, rowpad=r.get('sample', 0), mixw=r['mixw'], mixr=r['mixr'],
             busy=w[0] & 1, done=(w[0] >> 1) & 1, faulted=(w[0] >> 2) & 1, wrok=(w[0] >> 3) & 1, rdok=(w[0] >> 4) & 1,
             err=w[1] & 255, jobid=val(2, 2), cyc=val(4, 4), cmds=val(8, 4), wb=val(12, 4), rb=val(16, 4), cs=val(20, 4), ws=val(24, 4),
             latsum=val(28, 4), latn=val(32, 4), latmax=val(36, 2),
             ckw='%032x' % val(38, 8), ckr='%032x' % val(46, 8), cke='%032x' % val(54, 8))
    r['mode'] = r['mode']
    return r


def check_port_output(text, enpipe=0):
    """Verify every PORTSNAP record (LINK-visible snapshot of the bandwidth engine behind mem_top) against the model.
    The stand-in IP has ideal readies and a 6-cycle command-to-data latency, so the ideal cycle formulas apply."""
    m = Model(True, enpipe)
    jobs = 0
    for line in text.splitlines():
        if line.startswith('PORTSNAP'):
            r = parse_port(line)
            if r['nm'] in ('after_cfgerr',):
                pass
            m.expect(r, 'done', r['done'], 1); m.expect(r, 'busy', r['busy'], 0); m.expect(r, 'faulted', r['faulted'], 0)
            if r['jobid'] < 0x10000:
                m.expect(r, 'job id namespace', r['jobid'], 'engine job ids start at 0x10000')
            m.job(r)
            jobs += 1
    return jobs, m.errors


def check_output(text, paired, enpipe=0):
    """Verify every BWRES line of a tb_mem_bw run. Returns (jobs_checked, list_of_mismatches)."""
    m = Model(paired, enpipe)
    jobs = 0
    for line in text.splitlines():
        if line.startswith('BWCLR'):
            m.clear()
        elif line.startswith('BWRES'):
            m.job(parse(line))
            jobs += 1
    return jobs, m.errors


def self_test():
    # xorshift32 reference vector (Marsaglia 13/17/5) from state 1
    assert xs32(1) == 270369
    # all-ones lanes of seed 0 are the constants themselves
    d = data_stream(0, 2)
    assert d[0] & M32 == 0x9E3779B9 and (d[0] >> 96) == 0x85EBCA6B and d[1] & M32 == xs32(0x9E3779B9)
    assert checksum([]) == 0
    # sequential pattern, 16 B per beat, wraps at 128 MiB
    assert cmd_addresses(0, 3, 0x7FFFFE0, 23, 1, 0, 1, 1) == [0x7FFFFE0, 0x7FFFFF0, 0]
    # burst command addresses advance by L beats
    assert cmd_addresses(0, 3, 0, 23, 1, 3, 1, 1) == [0, 128, 256]
    # strided: runs of 4, stride 1024 beats (16 KiB)
    assert cmd_addresses(5, 6, 0, 23, 1, 0, 4, 1024) == [0, 16, 32, 48, 16384, 16400]
    # row miss: row field i[12:0] moves by 16 KiB per beat
    assert cmd_addresses(2, 3, 0, 23, 1, 0, 1, 1) == [0, 16384, 32768]
    # bank interleave: bank = i[2:0] -> byte[13:11], then column group
    assert cmd_addresses(1, 9, 0, 23, 1, 0, 1, 1)[:9] == [0, 2048, 4096, 6144, 8192, 10240, 12288, 14336, 16]
    # ideal write: exactly N cycles; ideal read: N + latency
    last, cs, ws = write_cycles(0, 100, 64, 1)
    assert last - 100 + 1 == 64 and cs == ws == 0
    last, cs, ssum, sn, smax = read_cycles(0, 100, 6, 4096, 1)
    assert last - 100 + 1 == 4102 and sn == 586 and smax == 6
    return 'bw_model self test OK'


if __name__ == '__main__':
    print(self_test())
