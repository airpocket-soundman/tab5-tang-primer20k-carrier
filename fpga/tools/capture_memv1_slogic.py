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
    p.add_argument('--prearm', action='store_true', help='finish GPIO ARM before capture, so triggers select CAPS')
    p.add_argument('--stages', default='caps', help='comma-separated read-only stages: caps,status,rd1,rd256')
    p.add_argument('--display-status', action='store_true', help='Opt in to start/final LCD status; requires display-capable host firmware/tool')
    p.add_argument('--test-name', default='MEMV1 SLOGIC CAPTURE', help='LCD test name, at most 40 printable ASCII characters')
    a = p.parse_args()
    if len(a.test_name) > 40 or any(ord(c) < 32 or ord(c) > 126 for c in a.test_name):
        p.error('--test-name must contain at most 40 printable ASCII characters')
    if a.rate <= 0 or a.samples <= 0 or a.samples / a.rate > 5:
        p.error('capture duration must be positive and at most 5 seconds')
    stages = a.stages.split(',')
    if not stages or any(stage not in ('caps', 'status', 'rd1', 'rd256') for stage in stages):
        p.error('only read-only stages caps,status,rd1,rd256 are allowed')
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    record = dict(started=datetime.now(timezone(timedelta(hours=9))).isoformat(),
                  scope='CAPS read-only; bounded capture; no retries or fallback',
                  project_serial=a.project_serial, analyzer_serial=a.analyzer_serial,
                  sample_rate=a.rate, samples=a.samples, channels=a.channels,
                  logic_channels=a.logic_channels, threshold_v=1.7, trigger=a.trigger)
    record['prearm'] = a.prearm
    record['stages_requested'] = stages
    record['display_status'], record['test_name'] = a.display_status, a.test_name
    caps = None
    capture = None
    active_client = None
    host_started = False
    sys.path.insert(0, str(a.host.resolve() / 'tools'))
    from gpu_lab import Client
    from probe_mem_bist import Client as ProbeClient
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
            if a.prearm and a.display_status and info.get('mem_status_display') is not True:
                raise RuntimeError('Firmware does not advertise the status display; nothing changed')
            if a.prearm and a.display_status:
                record['display_initial'] = info.get('display')
        finally:
            client.close()
        config = f'logic_channels={a.logic_channels}:samplerate={a.rate}:voltage_threshold=1.7-1.7'
        preflight = subprocess.run(cli + ['--config', config, '--channels', a.channels,
                                         '--get', 'samplerate'],
                                   capture_output=True, text=True, timeout=15, check=True)
        (out / 'config-readback.txt').write_text(preflight.stdout + preflight.stderr, encoding='utf-8')
        if preflight.stdout.strip() != str(a.rate):
            raise RuntimeError('Analyzer sample rate was not acknowledged')
        if a.prearm:
            active_client = ProbeClient(port, timeout=8)
            record['mode'] = active_client.call('mem', action='xferx_mode', mode='dma',
                                              tx_hz=a.tx_hz, rx_hz=a.rx_hz,
                                              tx_phase='positive', sample_edge=a.edge)
            if (record['mode'].get('xferx_tx_hz'), record['mode'].get('xferx_rx_hz')) != (a.tx_hz, a.rx_hz):
                raise RuntimeError('DMA clock settings were not acknowledged')
            if a.display_status:
                if record['mode'].get('link_armed') is not False or record['mode'].get('mem_session') is not False:
                    raise RuntimeError('Display requires an acknowledged disarmed idle session')
                try:
                    record['display_start'] = active_client.call('mem', action='display', test_name=a.test_name,
                        stage='LINK CHECK + TRANSFER', step=0, total=len(stages), result='RUNNING', transfer_us=0)
                except Exception as exc:
                    record['display_error'] = repr(exc)
                    raise
            host_started = True
            record['arm'] = active_client.call('mem', action='arm')
        command = cli + ['--loglevel', '5', '--config', config,
                         '--channels', a.channels, '--samples', str(a.samples),
                         '--output-format', 'srzip', '--output-file', str(out / 'capture.sr')]
        if a.trigger:
            command += ['--triggers', a.trigger, '--wait-trigger']
        record['capture_command'] = command
        with (out / 'capture-console.txt').open('w', encoding='utf-8') as log:
            capture = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            marker = 'Starting acquisition.' if a.trigger else 'Received SR_DF_LOGIC'
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                text = (out / 'capture-console.txt').read_text(encoding='utf-8', errors='replace')
                if marker in text:
                    record['capture_ready_marker'] = marker
                    if a.trigger:
                        time.sleep(0.05)
                    break
                if capture.poll() is not None:
                    raise RuntimeError('Capture exited before the exchange; inspect capture-console.txt')
                time.sleep(0.01)
            else:
                raise RuntimeError('No acquisition readiness marker; no exchange sent')
            host_command = [sys.executable, str(a.host.resolve() / 'tools/memv1_xfer.py'),
                            '--port', port, '--mode', 'dma', '--tx-hz', str(a.tx_hz),
                            '--rx-hz', str(a.rx_hz), '--tx-phase', 'positive', '--edge', a.edge,
                            '--stages', a.stages, '--expected-elf-sha', a.expected_elf,
                            '--record', str(out / 'caps.json')]
            if a.display_status and not a.prearm:
                host_command += ['--display-status', '--test-name', a.test_name]
            record['host_command'] = host_command
            if a.prearm:
                from memv1_xfer import Runner, BridgeXfer
                caps = dict(mode='dma', tx_hz=a.tx_hz, rx_hz=a.rx_hz,
                            info=record['info'], execute=False, stages_requested=stages)
                try:
                    result = Runner(BridgeXfer(active_client), 0x100000, 0x4d31, False,
                                    caps, dma=True).run(stages)
                    record['host_exit_code'] = 0 if result == 'PASS' else 1
                except Exception as exc:
                    caps['result'], caps['error'] = 'FAIL', getattr(exc, 'reply', repr(exc))
                    record['host_exit_code'] = 1
                (out / 'caps.json').write_text(json.dumps(caps, indent=2) + '\n', encoding='utf-8')
            else:
                with (out / 'caps-console.txt').open('w', encoding='utf-8') as host_log:
                    host_started = True
                    host = subprocess.run(host_command, stdout=host_log, stderr=subprocess.STDOUT, timeout=15)
                    record['host_exit_code'] = host.returncode
            record['capture_exit_code'] = capture.wait(timeout=15)
        record['result'] = 'PASS' if record['capture_exit_code'] == record['host_exit_code'] == 0 else 'FAIL'
    except Exception as exc:
        record['result'], record['error'] = 'FAIL', repr(exc)
    finally:
        if active_client is not None:
            try:
                record['prearm_disarm'] = active_client.call('mem', action='disarm')
                if a.display_status:
                    state = record['prearm_disarm']
                    if state.get('link_armed') is not False or state.get('mem_session') is not False:
                        raise RuntimeError('DISARM was not acknowledged; final display suppressed')
            except Exception as exc:
                record['prearm_cleanup_error'] = repr(exc)
                record['result'] = 'FAIL'
            # Every render request is before ARM or after an acknowledged DISARM.
            # If cleanup failed, do not ask the firmware to render while bus ownership is uncertain.
            if a.display_status and 'display_start' in record and 'prearm_cleanup_error' not in record:
                result = record.get('result', 'FAIL')
                frames = (caps or {}).get('frames', [])
                transfer_us = int((frames[-1].get('timing') or {}).get('total_us', 0)) if frames else 0
                completed = (caps or {}).get('stages_completed', sum(
                    stage.get('result') == 'PASS' for stage in (caps or {}).get('stages', {}).values()))
                final_stage = ('LINK CHECK FAILED' if 'arm' not in record else
                               'COMPLETE' if result == 'PASS' else
                               'CAPTURE FAILED' if (caps or {}).get('result') == 'PASS' else
                               'FAILED: ' + (caps or {}).get('active_stage', 'CAPTURE').upper())
                try:
                    record['display_finish'] = active_client.call('mem', action='display', test_name=a.test_name,
                        stage=final_stage, step=min(len(stages), max(0, int(completed))), total=len(stages),
                        result='PASS' if result == 'PASS' else 'FAIL', transfer_us=transfer_us)
                except Exception as exc:
                    record['display_error'] = repr(exc)
                    record['result'] = 'FAIL'
            try:
                (out / 'usb-trace.json').write_text(json.dumps(active_client.trace, indent=2) + '\n', encoding='utf-8')
            finally:
                active_client.close()
        if capture is not None and capture.poll() is None:
            # Only the process tree launched by this invocation is terminated.
            subprocess.run(['taskkill', '/PID', str(capture.pid), '/T', '/F'], capture_output=True)
            capture.wait(timeout=10)
        if host_started and not (a.prearm and a.display_status):
            client = None
            try:
                client = Client(port, timeout=8)
                record['disarm'] = client.call('mem', action='disarm')
            except Exception as exc:
                record['cleanup_error'] = repr(exc)
                record['result'] = 'FAIL'
            finally:
                if client is not None:
                    client.close()
        record['finished'] = datetime.now(timezone(timedelta(hours=9))).isoformat()
        (out / 'run.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'output': str(out), 'result': record.get('result'),
                          'error': record.get('error')}, ensure_ascii=False))
    # Evaluate only after cleanup/UI errors have had a chance to mark the run FAIL.
    return 0 if record.get('result') == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
