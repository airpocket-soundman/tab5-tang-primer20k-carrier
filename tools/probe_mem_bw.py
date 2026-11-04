"""DDR3 bandwidth measurement host script (mem_bw, LINK opcodes 0x60..0x6F). Style of probe_mem_bist.py: without --execute it
only prints the plan (no UART); no retries, no implicit recalibration; raw envelopes are kept in the JSON record.

Transport: the Tab5 USB JSON API of the standalone MEM probe firmware. The firmware in tab5-fpga-gpu-mem-scheduler-diag (37af57f)
has NO bandwidth action yet (UNIMPLEMENTED on the host side, recorded in docs/DDR3_帯域測定_実機手順_2026-11-04.md). This script
requires one generic action that forwards a bandwidth opcode to the device and returns the 16 bit result:
    request : {"v":1,"id":N,"cmd":"mem","action":"bw","op":96..111,"arg":0..65535}
    success : {"v":1,"id":N,"ok":true,"data":{..., "value":<u16>, "device_status":0}}
    failure : ok=false with "device_status" (0 = transport/semantic fault) like the existing mem actions.
The firmware must reject op outside 0x60..0x6F and must keep the wire validation (fpga/host/mem_protocol.h) in sync.

What is measured (definitions, fpga/mem/BW_ENGINE.md):
    cycles   = USER clock cycles from the first accepted command to the last data beat (write data accepted / read data received)
    bytes    = (write_beats + read_beats) * 16
    seconds  = cycles / USER_HZ,  USER_HZ = 27 MHz * 59/4 (memory clock 398.25 MHz) / 4 = 99,562,500 Hz   (override: --user-hz)
    MB/s     = bytes / seconds / 1e6;  efficiency = bytes / (cycles * 16)   (1.0 = one 128 bit beat per USER cycle = 1.593 GB/s)
    latency  = lat_sum / lat_samples USER cycles (command accepted -> its first data beat, sampled commands only)
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import time

SIGNATURE = 0x0150
ABI = 1
SNAPSHOT_WORDS = 62
USER_HZ = 99_562_500
BYTES_PER_BEAT = 16
OPS = dict(CFG_BASE_LO=0x60, CFG_BASE_HI=0x61, CFG_COUNT_LO=0x62, CFG_COUNT_HI=0x63, CFG_SEED_LO=0x64, CFG_SEED_HI=0x65,
           CFG_CTL=0x66, CFG_MIX=0x67, CFG_RUN=0x68, CFG_STRIDE_LO=0x69, CFG_STRIDE_HI=0x6A,
           START=0x6B, CANCEL=0x6C, SNAPSHOT=0x6D, READ=0x6E, QUERY=0x6F)
MODES = dict(write=0, read=1, mixed=2)
PATTERNS = dict(seq=0, bank=1, rowmiss=2, lfsr=3, scatter=4, strided=5)
FLAG = dict(calibrated=1, user_alive=2, busy=4, done=8, faulted=16, port_timeout=32, snapshot_valid=64, bist_busy=128)
MEM_SYS_REQUIRED = 1 | 128 | 256 | 512          # calibrated, guard ready, user ready, heartbeat fresh (MEM diagnostic SYSQUERY 6)
MEM_SYS_FORBIDDEN = 2 | 4 | 32 | 64 | 0xFC00    # busy, user fault, timeout, context lost, loss reasons


def words_value(words):
    return sum(v << (16 * i) for i, v in enumerate(words))


def job(name, mode, pattern, beats, base=0, seed=0x12345678, region_log2=23, burst_log2=0, run=1, stride=1, mix_w=1, mix_r=1, verify=True):
    """One bandwidth job. beats = 128 bit beats (16 B). All fields are validated like mem_bw's valid_cfg."""
    j = dict(name=name, mode=mode, pattern=pattern, beats=beats, base=base, seed=seed, region_log2=region_log2,
             burst_log2=burst_log2, run=run, stride=stride, mix_w=mix_w, mix_r=mix_r, verify=verify)
    validate(j)
    return j


def validate(j):
    L = 1 << j['burst_log2']
    if j['mode'] not in MODES.values() or j['pattern'] not in PATTERNS.values() or not 0 <= j['burst_log2'] <= 6:
        raise ValueError('mode/pattern/burst_log2')
    if not (1 <= j['beats'] <= 8388608 and j['base'] % (16 * L) == 0 and 0 <= j['base'] < 1 << 27 and j['beats'] % L == 0):
        raise ValueError('beats 1..2^23 (multiple of L), base aligned to 16*L, base < 128 MiB')
    if j['burst_log2'] and (j['mode'] == 2):
        raise ValueError('mixed mode is single-beat only')
    if j['mode'] == 2 and not (1 <= j['mix_w'] <= 255 and 1 <= j['mix_r'] <= 255):
        raise ValueError('mix_w/mix_r 1..255')
    if j['pattern'] in (3, 4) and not 1 <= j['region_log2'] <= 23:
        raise ValueError('region_log2 1..23')
    if j['pattern'] == 4 and j['beats'] > (1 << j['region_log2']):
        raise ValueError('scatter needs beats <= 2^region_log2')
    if j['pattern'] == 5 and not (1 <= j['run'] <= 65535 and 1 <= j['stride'] <= 0x7FFFFF and j['stride'] % L == 0):
        raise ValueError('strided: run 1..65535, stride 1..2^23-1 multiple of L')
    if j['base'] + 16 * j['beats'] > 1 << 27 and j['pattern'] in (0, 1, 2):
        raise ValueError('sequential-type pattern would wrap at 128 MiB')


def default_suite(mib=1, burst=False):
    """Bandwidth matrix: direction x locality (x burst length with --burst, which relies on the unverified app_burst_number)."""
    n = mib * 65536                                   # beats (1 MiB = 65536 beats)
    s = [job('write_seq', 0, 0, n), job('read_seq', 1, 0, n), job('mixed_seq_4_4', 2, 0, n // 4, mix_w=4, mix_r=4),
         job('write_rowmiss16k', 0, 5, n // 8, run=1, stride=1024), job('read_rowmiss16k', 1, 5, n // 8, run=1, stride=1024),
         job('write_page_runs', 0, 5, n // 4, run=128, stride=1152), job('read_page_runs', 1, 5, n // 4, run=128, stride=1152),
         job('write_bank_rot', 0, 1, n), job('read_bank_rot', 1, 1, n),
         job('write_scatter', 0, 4, 1 << 16, region_log2=16), job('read_scatter', 1, 4, 1 << 16, region_log2=16)]
    if burst:
        for b in (1, 2, 3, 4, 5, 6):
            s += [job(f'write_burst{1 << b}', 0, 0, n, burst_log2=b), job(f'read_burst{1 << b}', 1, 0, n, burst_log2=b)]
    return s


def decode_snapshot(words, user_hz=USER_HZ):
    if len(words) != SNAPSHOT_WORDS or any(type(v) is not int or not 0 <= v <= 65535 for v in words):
        raise ValueError('invalid 62-word snapshot')
    w = words
    r = dict(busy=w[0] & 1, done=(w[0] >> 1) & 1, faulted=(w[0] >> 2) & 1, wr_match=(w[0] >> 3) & 1, rd_match=(w[0] >> 4) & 1,
             error=w[1] & 255, job_id=words_value(w[2:4]), cycles=words_value(w[4:8]), commands=words_value(w[8:12]),
             write_beats=words_value(w[12:16]), read_beats=words_value(w[16:20]), cmd_stall=words_value(w[20:24]),
             wd_stall=words_value(w[24:28]), lat_sum=words_value(w[28:32]), lat_samples=words_value(w[32:36]),
             lat_max=words_value(w[36:38]), ck_wr=f'{words_value(w[38:46]):032x}', ck_rd=f'{words_value(w[46:54]):032x}',
             ck_exp=f'{words_value(w[54:62]):032x}')
    beats = r['write_beats'] + r['read_beats']
    if r['cycles']:
        seconds = r['cycles'] / user_hz
        r.update(bytes=beats * BYTES_PER_BEAT, seconds=seconds, mb_per_s=beats * BYTES_PER_BEAT / seconds / 1e6,
                 efficiency=beats / r['cycles'], theoretical_mb_per_s=BYTES_PER_BEAT * user_hz / 1e6)
    r['avg_latency_cycles'] = r['lat_sum'] / r['lat_samples'] if r['lat_samples'] else None
    r['avg_latency_ns'] = r['avg_latency_cycles'] * 1e9 / user_hz if r['lat_samples'] else None
    r['cmd_stall_ratio'] = r['cmd_stall'] / r['cycles'] if r['cycles'] else None
    r['wd_stall_ratio'] = r['wd_stall'] / r['cycles'] if r['cycles'] else None
    return r


def check_result(j, r):
    """Pass criteria of ONE job: it finished cleanly, counters are exactly those of the plan, data check passed, bound respected.
    No throughput threshold: the value is the measurement."""
    L = 1 << j['burst_log2']
    n = j['beats']
    bad = []
    if not r['done'] or r['busy'] or r['faulted'] or r['error']:
        bad.append(f"job state done={r['done']} busy={r['busy']} faulted={r['faulted']} error={r['error']}")
    wb = n if j['mode'] in (0, 2) else 0
    rb = n if j['mode'] in (1, 2) else 0
    cmds = (n // L) * (2 if j['mode'] == 2 else 1)
    if (r['write_beats'], r['read_beats'], r['commands']) != (wb, rb, cmds):
        bad.append(f"counters wb/rb/cmds {r['write_beats']}/{r['read_beats']}/{r['commands']} expected {wb}/{rb}/{cmds}")
    if r['cycles'] < (wb + rb) or r.get('efficiency', 0) > 1.0 + 1e-9:
        bad.append('cycle count below one beat per USER cycle: measurement invalid')
    if j['verify']:
        if j['mode'] in (0, 2) and not r['wr_match']:
            bad.append('write checksum != expected stream')
        if j['mode'] in (1, 2) and not r['rd_match']:
            bad.append('read checksum != expected stream (data mismatch or address collisions)')
    return bad


class ProbeError(RuntimeError):
    def __init__(self, reply):
        self.reply = reply
        super().__init__(json.dumps(reply, ensure_ascii=False))


class Client:
    """Single request/response, no mutation retry; raw envelopes retained (same transport as probe_mem_bist.py)."""
    def __init__(self, port, timeout=15):
        import serial
        self.serial = serial.Serial(port=None, baudrate=115200, timeout=.25, write_timeout=5)
        self.serial.dtr = True
        self.serial.rts = False
        self.serial.port = port
        self.serial.open()
        self.timeout = timeout
        self.sequence = 0
        self.trace = []
        self.pending = bytearray()

    def call(self, cmd, **params):
        self.sequence += 1
        request = dict(v=1, id=self.sequence, cmd=cmd, **params)
        self.trace.append(dict(request=request))
        self.serial.write((json.dumps(request) + '\n').encode())
        deadline = time.monotonic() + self.timeout
        decoder = json.JSONDecoder()
        while time.monotonic() < deadline:
            self.pending.extend(self.serial.readline())
            if len(self.pending) > 1048576:
                raise ValueError('oversized USB envelope')
            if b'\n' not in self.pending:
                continue
            raw, _, remaining = self.pending.partition(b'\n')
            self.pending = bytearray(remaining)
            line = raw.decode('utf-8', errors='replace')
            self.trace.append(dict(raw=line))
            if not line.strip():
                continue
            try:
                reply, _ = decoder.raw_decode(line[line.index('{'):])
            except (ValueError, TypeError):
                continue
            if reply.get('id') != self.sequence:
                continue
            if reply.get('v') != 1 or reply.get('ok') is not True:
                raise ProbeError(reply)
            return reply['data']
        raise TimeoutError('USB response timeout; command is not retried')

    def close(self):
        self.serial.close()


class Device:
    """Bandwidth opcodes on top of a Client-like object (anything with .call(cmd, **params))."""
    def __init__(self, client):
        self.client = client

    def op(self, name_or_code, arg=0, allow=(0,)):
        code = OPS[name_or_code] if isinstance(name_or_code, str) else name_or_code
        try:
            data = self.client.call('mem', action='bw', op=code, arg=arg)
            status = data.get('device_status', 0)
            value = data['value']
        except ProbeError as exc:
            status = exc.reply.get('device_status', exc.reply.get('data', {}).get('device_status') if isinstance(exc.reply.get('data'), dict) else None)
            if status not in allow or not status:
                raise
            value = 0
        if status not in allow:
            raise ValueError(f'bandwidth op {code:#x}: device status {status}')
        return value, status

    def query(self, a):
        return self.op('QUERY', a)[0]

    def flags(self):
        return self.query(1)

    def configure(self, j):
        def put(name, v):
            echo, _ = self.op(name, v)
            if echo != v:
                raise ValueError(f'{name}: echo {echo:#x} != {v:#x}')
        base, cnt, seed = j['base'], j['beats'], j['seed']
        put('CFG_BASE_LO', base & 0xFFFF); put('CFG_BASE_HI', base >> 16)
        put('CFG_COUNT_LO', cnt & 0xFFFF); put('CFG_COUNT_HI', cnt >> 16)
        put('CFG_SEED_LO', seed & 0xFFFF); put('CFG_SEED_HI', seed >> 16)
        put('CFG_CTL', j['mode'] | (j['pattern'] << 2) | (j['region_log2'] << 5) | (j['burst_log2'] << 10))
        put('CFG_MIX', j['mix_w'] | (j['mix_r'] << 8))
        put('CFG_RUN', j['run'])
        put('CFG_STRIDE_LO', j['stride'] & 0xFFFF)
        put('CFG_STRIDE_HI', (j['stride'] >> 16) & 0xFF)

    def run(self, j, timeout, poll, clock=time.monotonic, sleep=time.sleep):
        self.configure(j)
        started, _ = self.op('START')
        deadline = clock() + timeout
        while True:
            f = self.flags()
            if f & FLAG['port_timeout']:
                raise ValueError('bandwidth port timeout flag set')
            if f & FLAG['done'] and not f & FLAG['busy']:
                break
            if clock() >= deadline:
                raise TimeoutError('bounded bandwidth job wait expired')
            sleep(poll)
        gen, _ = self.op('SNAPSHOT')
        words = [self.op('READ', i)[0] for i in range(SNAPSHOT_WORDS)]
        gen_after = self.query(2)
        if gen_after != gen:
            raise ValueError('snapshot generation changed while reading')
        return started, words


def wait_ready(client, args, record, clock, sleep):
    deadline = clock() + args.ready_timeout
    while True:
        system = client.call('mem', action='sys')
        record['sys_before'] = system
        values = system['sys']
        if values[4:6] not in ([324, 81], [398, 100]):
            raise ValueError('MEM clock pair not recognised (expected 324/81 or 398/100)')
        flags = values[6]
        if flags & MEM_SYS_FORBIDDEN & ~2:
            raise ValueError('MEM context/fault; explicit separate recalibration required')
        if flags & MEM_SYS_REQUIRED == MEM_SYS_REQUIRED and not flags & 2:
            return values
        if clock() >= deadline:
            raise TimeoutError('calibration guard readiness timeout')
        sleep(args.poll_interval)


def bist_pass(client, args, record, clock, sleep):
    """BIST re-pass after the bandwidth jobs, with the existing MEM actions (configure/start/snapshot). Exact PASS only."""
    cfg = client.call('mem', action='configure', base=0, count=args.bist_beats, seed=0x12345678)
    start = client.call('mem', action='start', execute=True)
    deadline = clock() + args.timeout
    while True:
        snap = client.call('mem', action='snapshot')
        w = snap['words']
        flags, phase_err = w[0], w[1]
        verified, mism = words_value(w[4:6]), words_value(w[6:8])
        record.setdefault('bist_snapshots', []).append(dict(flags=flags, phase_error=phase_err, verified=verified, mismatches=mism))
        if flags & 4:
            ok = (flags & 31) == 5 and phase_err == 0x0500 and verified == args.bist_beats * 2 and mism == 0
            record['bist_after'] = dict(configure=cfg, start=start, pass_=ok, verified_beats=verified, mismatches=mism)
            if not ok:
                raise ValueError('BIST after bandwidth jobs is not an exact PASS')
            return
        if mism or phase_err & 255 or flags & (8 | 16):
            raise ValueError('BIST fault after bandwidth jobs')
        if clock() >= deadline:
            raise TimeoutError('bounded BIST wait expired')
        sleep(args.poll_interval)


def execute(client, args, record, *, clock=time.monotonic, sleep=time.sleep):
    armed = False
    started_any = False
    dev = Device(client)
    record['jobs'] = []
    try:
        info = client.call('info')
        record['info'] = info
        if info.get('profile') != 'standalone_mem_bist_probe' or info.get('running') is not False:
            raise ValueError('wrong firmware profile; no settings changed')
        if info.get('mem_bw_available') is not True:
            raise ValueError('firmware has no bandwidth action (mem_bw_available missing): UNIMPLEMENTED on the host side')
        if args.expected_elf_sha and info.get('app_elf_sha256') != args.expected_elf_sha:
            raise ValueError('runtime ELF SHA mismatch')
        if info.get('link_armed'):
            raise ValueError('require fresh disarmed session')
        record['arm'] = client.call('mem', action='arm')
        armed = True
        if args.recalibrate:
            record['recalibrate'] = client.call('mem', action='recalibrate', execute=True)
        wait_ready(client, args, record, clock, sleep)
        sig, abi, words = dev.query(0), dev.query(4), dev.query(3)
        record['bw_port'] = dict(signature=sig, abi=abi, snapshot_words=words, user_mhz=dev.query(5))
        if (sig, abi, words) != (SIGNATURE, ABI, SNAPSHOT_WORDS):
            raise ValueError('bandwidth port signature/ABI mismatch (image without BW_ENABLE, or other ABI)')
        if dev.flags() & (FLAG['busy'] | FLAG['faulted'] | FLAG['bist_busy'] | FLAG['port_timeout']):
            raise ValueError('bandwidth port not idle/clean; explicit recalibration required')
        for j in args.plan:
            started_any = True
            entry = dict(plan=j)
            record['jobs'].append(entry)
            started, words_ = dev.run(j, args.timeout, args.poll_interval, clock, sleep)
            r = decode_snapshot(words_, args.user_hz)
            entry.update(start_ack=started, snapshot_words=words_, result=r)
            bad = check_result(j, r)
            entry['problems'] = bad
            if bad:
                raise ValueError(f"job {j['name']}: " + '; '.join(bad))
        if args.bist_after:
            bist_pass(client, args, record, clock, sleep)
        record['result'] = 'PASS'
    except Exception as exc:
        record['result'] = 'FAIL'
        record['error'] = dict(type=type(exc).__name__, message=str(exc))
        raise
    finally:
        if armed and started_any and record.get('result') != 'PASS':
            try:
                if dev.flags() & FLAG['busy']:
                    record.setdefault('cleanup', []).append(dict(cancel=dev.op('CANCEL', allow=(0, 5))))
            except Exception as exc:
                record.setdefault('cleanup', []).append(dict(cancel_error=str(exc)))
        try:
            if armed:
                record.setdefault('cleanup', []).append(dict(disarm=client.call('mem', action='disarm')))
        except Exception as exc:
            record.setdefault('cleanup', []).append(dict(disarm_error=str(exc)))


def summary_table(record):
    rows = ['name,cycles,bytes,MB_per_s,efficiency,avg_latency_ns,cmd_stall_ratio,wd_stall_ratio']
    for e in record.get('jobs', []):
        r = e.get('result')
        if r and r.get('cycles'):
            rows.append(f"{e['plan']['name']},{r['cycles']},{r['bytes']},{r['mb_per_s']:.1f},{r['efficiency']:.4f},"
                        f"{'' if r['avg_latency_ns'] is None else format(r['avg_latency_ns'], '.1f')},{r['cmd_stall_ratio']:.4f},{r['wd_stall_ratio']:.4f}")
    return '\n'.join(rows)


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--execute', action='store_true', help='run the jobs (DESTRUCTIVE: overwrites DDR3 content); otherwise plan only, no UART')
    p.add_argument('--recalibrate', action='store_true', help='explicit pre-job RECAL; never automatic')
    p.add_argument('--port')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--mib', type=int, default=1, help='data volume of the sequential jobs in MiB (default 1)')
    p.add_argument('--burst', action='store_true', help='add burst-length jobs (app_burst_number semantics unverified on hardware)')
    p.add_argument('--user-hz', type=int, default=USER_HZ)
    p.add_argument('--timeout', type=float, default=70)
    p.add_argument('--ready-timeout', type=float, default=5)
    p.add_argument('--poll-interval', type=float, default=.1)
    p.add_argument('--bist-after', action='store_true', help='re-run the 64-beat-class BIST after the jobs and require an exact PASS')
    p.add_argument('--bist-beats', type=int, default=64)
    p.add_argument('--expected-elf-sha')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if not 1 <= args.mib <= 64 or not 0 < args.timeout <= 600 or not .01 <= args.poll_interval <= 1:
        raise ValueError('invalid size/deadline/poll bounds')
    if args.execute and not args.port:
        raise ValueError('--execute requires --port')
    args.plan = default_suite(args.mib, args.burst)
    record = dict(schema=1, started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  plan=dict(jobs=args.plan, user_hz=args.user_hz, theoretical_mb_per_s=BYTES_PER_BEAT * args.user_hz / 1e6,
                            destructive=True, recalibrate_explicit=args.recalibrate),
                  executed=args.execute, tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    code = 0
    client = None
    try:
        if args.execute:
            client = Client(args.port)
            execute(client, args, record)
        else:
            record['result'] = 'PLAN_ONLY_NO_UART'
    except Exception as exc:
        record.setdefault('error', dict(type=type(exc).__name__, message=str(exc)))
        record['result'] = 'FAIL'
        code = 1
    finally:
        if client:
            record['usb_trace'] = client.trace
            client.close()
        record['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(result=record['result'], output=str(args.output))))
    if record.get('jobs'):
        print(summary_table(record))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
