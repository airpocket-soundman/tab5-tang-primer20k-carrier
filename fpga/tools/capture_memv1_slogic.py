"""Capture a bounded MEMV1 CAPS exchange; no flashing, retries, or DDR writes.

Connect the probes before invoking. Default: all 16 channels at 5MS/s, 2s,
and a known 0.5MHz tagged CAPS sequence for channel identification.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True, help='new run directory')
    p.add_argument('--host', type=Path, default=Path('D:/github/airpocket-soundman/tab5-fpga-gpu-cancel'))
    p.add_argument('--slogic', type=Path, default=Path('D:/tools/slogic-2.3.2/run-sigrok.ps1'))
    p.add_argument('--project-serial', default='30:ED:A0:E2:FE:C0')
    p.add_argument('--analyzer-serial', default='202512191855')
    p.add_argument('--expected-elf', default='ea98777e43cbc926d342ecd8ab8386fa7e881c3a8b02cc1864734eae72246712')
    p.add_argument('--tx-hz', type=int, default=500000)
    p.add_argument('--rx-hz', type=int, default=500000)
    p.add_argument('--edge', choices=('positive', 'negative'), default='positive')
    p.add_argument('--rate', type=int, default=5000000)
    p.add_argument('--samples', type=int, default=10000000)
    p.add_argument('--logic-channels', type=int, choices=(4, 8, 16), default=16)
    p.add_argument('--channels', default=','.join(f'D{i}' for i in range(16)))
    p.add_argument('--trigger', help='optional sigrok trigger, after channel mapping')
    a = p.parse_args()
    if a.rate <= 0 or a.samples <= 0 or a.samples / a.rate > 5:
        p.error('capture duration must be positive and at most 5 seconds')
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    record = dict(started=datetime.now(timezone(timedelta(hours=9))).isoformat(),
                  scope='CAPS read-only; bounded capture; no retries or fallback',
                  project_serial=a.project_serial, analyzer_serial=a.analyzer_serial,
                  sample_rate=a.rate, samples=a.samples, channels=a.channels,
                  logic_channels=a.logic_channels, threshold_v=1.7, trigger=a.trigger)
    capture = None
    host_started = False
    sys.path.insert(0, str(a.host.resolve() / 'tools'))
    from gpu_lab import Client
    import serial.tools.list_ports
    ports = [x for x in serial.tools.list_ports.comports()
             if (x.serial_number or '').upper() == a.project_serial.upper()]
    if len(ports) != 1:
        raise RuntimeError('Project Tab5 identity is absent or ambiguous')
    port = ports[0].device
    record['port'] = port
    cli = ['powershell', '-NoProfile', '-File', str(a.slogic.resolve()),
           '--driver', 'sipeed-slogic-analyzer']
    try:
        scan = subprocess.run(cli + ['--scan'], capture_output=True, text=True, timeout=15, check=True)
        (out / 'scan.txt').write_text(scan.stdout + scan.stderr, encoding='utf-8')
        if scan.stdout.count('sipeed-slogic-analyzer -') != 1 or a.analyzer_serial not in scan.stdout:
            raise RuntimeError('Analyzer identity is absent or ambiguous')
        client = Client(port, timeout=8)
        try:
            info = client.call('info')
            record['info'] = info
            if (info.get('profile') != 'standalone_mem_bist_probe' or
                    info.get('app_elf_sha256') != a.expected_elf or info.get('link_armed')):
                raise RuntimeError('Require the expected, disarmed MEM probe')
        finally:
            client.close()
        config = f'logic_channels={a.logic_channels}:samplerate={a.rate}:voltage_threshold=1.7-1.7'
        preflight = subprocess.run(cli + ['--config', config, '--channels', a.channels,
                                         '--get', 'samplerate'],
                                   capture_output=True, text=True, timeout=15, check=True)
        (out / 'config-readback.txt').write_text(preflight.stdout + preflight.stderr, encoding='utf-8')
        if preflight.stdout.strip() != str(a.rate):
            raise RuntimeError('Analyzer sample rate was not acknowledged')
        command = cli + ['--config', config,
                         '--channels', a.channels, '--samples', str(a.samples),
                         '--output-format', 'srzip', '--output-file', str(out / 'capture.sr')]
        if a.trigger:
            command += ['--triggers', a.trigger, '--wait-trigger']
        record['capture_command'] = command
        with (out / 'capture-console.txt').open('w', encoding='utf-8') as log:
            capture = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            time.sleep(0.5)
            if capture.poll() is not None:
                raise RuntimeError('Capture exited before the exchange; inspect capture-console.txt')
            host_command = [sys.executable, str(a.host.resolve() / 'tools/memv1_xfer.py'),
                            '--port', port, '--mode', 'dma', '--tx-hz', str(a.tx_hz),
                            '--rx-hz', str(a.rx_hz), '--tx-phase', 'positive', '--edge', a.edge,
                            '--stages', 'caps', '--expected-elf-sha', a.expected_elf,
                            '--record', str(out / 'caps.json')]
            record['host_command'] = host_command
            with (out / 'caps-console.txt').open('w', encoding='utf-8') as host_log:
                host_started = True
                host = subprocess.run(host_command, stdout=host_log, stderr=subprocess.STDOUT, timeout=15)
                record['host_exit_code'] = host.returncode
            record['capture_exit_code'] = capture.wait(timeout=15)
        record['result'] = 'PASS' if record['capture_exit_code'] == record['host_exit_code'] == 0 else 'FAIL'
        return 0 if record['result'] == 'PASS' else 1
    except Exception as exc:
        record['result'], record['error'] = 'FAIL', repr(exc)
        return 1
    finally:
        if capture is not None and capture.poll() is None:
            # Only the process tree launched by this invocation is terminated.
            subprocess.run(['taskkill', '/PID', str(capture.pid), '/T', '/F'], capture_output=True)
            capture.wait(timeout=10)
        if host_started:
            client = None
            try:
                client = Client(port, timeout=8)
                record['disarm'] = client.call('mem', action='disarm')
            except Exception as exc:
                record['cleanup_error'] = repr(exc)
            finally:
                if client is not None:
                    client.close()
        record['finished'] = datetime.now(timezone(timedelta(hours=9))).isoformat()
        (out / 'run.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'output': str(out), 'result': record.get('result'),
                          'error': record.get('error')}, ensure_ascii=False))


if __name__ == '__main__':
    sys.exit(main())
