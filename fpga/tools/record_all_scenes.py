"""Archive the all-scene GFX experiment and completed probe map; never access devices.

The source ZIP is captured at archive time. Project file lists and tool hashes
identify inputs, but cannot reconstruct unrecorded historical source contents.
Only explicitly selected self-authored sources/output and text evidence enter
the archive; Gowin primitive libraries, encrypted netlists and DDR IP do not.
"""
import argparse
import binascii
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
FPGA = ROOT / 'fpga'
SELECTED_SHA = '7660c5be31dd99c7522ddb46cfcaf31ffd088314ec0e8d5aef0f10cc90969b9f'
COUNTS = ['Numbers of Paths Analyzed', 'Numbers of Endpoints Analyzed',
          'Numbers of Setup Violated Endpoints', 'Numbers of Hold Violated Endpoints']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write('\n')


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def timing(path):
    soup = BeautifulSoup(path.read_text(), 'html.parser')
    text = soup.get_text(' ', strip=True)
    counts = {k: int(re.search(re.escape(k) + r'\s+(\d+)', text).group(1)) for k in COUNTS}
    a = soup.find('a', {'name': 'Setup_Slack_Table1'})
    rows = a.find_next('table').find_all('tr')[1:]
    paths = []
    for row in rows:
        c = [x.get_text(' ', strip=True) for x in row.find_all('td')]
        if len(c) >= 6:
            paths.append(dict(slack_ns=float(c[1]), source=c[2], endpoint=c[3], from_clock=c[4], to_clock=c[5]))
    return dict(counts=counts, worst_setup_path=min(paths, key=lambda x: x['slack_ns']))


def exceptions(path):
    lines = path.read_text().splitlines()
    pairs = []
    for line in lines:
        if line.lstrip().startswith('set_false_path'):
            m = re.fullmatch(r'set_false_path -from \[get_pins \{([^}]+)\}\] -to \[get_pins \{([^}]+)\}\]', line.strip())
            if not m:
                raise ValueError('Unrecognized exception: ' + line)
            pairs.append(m.groups())
        elif re.match(r'\s*set_(multicycle_path|clock_groups)\b', line):
            raise ValueError('Unexpected new timing exception')
    assert len(pairs) == len(set(pairs)) == 30
    for src, dst in pairs:
        sm = re.fullmatch(r'core/fast_metadata_(\d+)_s0/Q', src)
        dm = re.fullmatch(r'core/fast_serializer.serializer/metadata_meta_(\d+)_s0/D', dst)
        assert sm and dm and sm.group(1) == dm.group(1), (src, dst)
    return pairs


def run_gates(host):
    out = FPGA / 'build/all-scenes-record-gates'
    out.mkdir(exist_ok=True)
    b = Path('D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin')
    zig = host.parent / 'tab5-fpga-gpu-demo/build/test-tools/ziglang/zig.exe'
    common = ['--iverilog', str(b/'iverilog.exe'), '--vvp', str(b/'vvp.exe')]
    env = dict(os.environ, PATH=str(b)+os.pathsep+str(b.parent/'lib')+os.pathsep+os.environ['PATH'])
    commands = [
        ['fpga/gfx/tests/run_fire_tile.py', *common, '--zig', str(zig)],
        ['fpga/link/tests/run_reply_clock_filter_active.py', *common, '--waveform-matrix'],
        ['fpga/link/tests/run_request_data_alignment.py', *common],
    ]
    result = []
    for command in commands:
        r = subprocess.run([sys.executable, *command], cwd=ROOT, env=env,
                           text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
        label = Path(command[0]).stem
        (out/(label+'.log')).write_text(r.stdout, encoding='utf-8')
        result.append(dict(command=[sys.executable, *command], returncode=r.returncode))
        write_json(out/'commands.json', result)
        if r.returncode:
            raise RuntimeError(label + ' failed; evidence retained in ' + str(out))


class Archive:
    def __init__(self, directory):
        self.directory = directory
        self.items = []

    def add(self, source, relative, compress=True):
        source = Path(source)
        raw = source.read_bytes()
        name = relative + ('.gz' if compress else '')
        dest = self.directory / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = gzip.compress(raw, mtime=0) if compress else raw
        dest.write_bytes(data)
        self.items.append(dict(source=str(source.resolve()), archived=name,
                               source_sha256=sha(raw), archived_sha256=sha(data), bytes=len(raw)))


def probe_map(output, refresh):
    src = FPGA/'build/channel-map-20261105-03'
    mapping = json.loads((src/'channel-map.json').read_text())
    complete = json.loads((src/'completeness.json').read_text())
    assert mapping['result'] == 'complete' and complete['passed'] is True
    assert complete['actual_samples'] == complete['expected_samples'] == 50000000
    assert complete['rate'] == 100000000 and complete['actual_bytes'] == 100000000
    assert sha((src/'capture.sr').read_bytes()) == mapping['input_sha256']
    from verify_slogic_capture import verify
    recheck = verify(src/'capture.sr', 50000000, 100000000, log=src/'capture-console.txt')
    assert recheck['passed'] is True and recheck['raw_sha256'] == complete['raw_sha256']
    assert mapping['evidence']['frames'] == 9
    expected = dict(CLK=7, DIR=6, READY=4, **{'D'+str(i): 15-i for i in range(8)})
    assert {k: v['channel'] for k, v in mapping['mapping'].items()} == expected
    if (output/'manifest.json').exists() and not refresh:
        raise FileExistsError('Probe archive exists; use --refresh')
    output.mkdir(parents=True, exist_ok=True)
    archive = Archive(output)
    for f in sorted(src.iterdir()):
        if f.is_file() and f.suffix in ('.json', '.txt', '.bin', '.sr'):
            archive.add(f, f.name, compress=f.suffix not in ('.bin', '.sr'))
    responses = json.loads((src/'responses.json').read_text())['responses']
    assert len(responses) == 9
    for r in responses:
        data = (src/r['path']).read_bytes()
        q = bytes.fromhex(r['request_hex'])
        assert r['returned'] is True and sha(data) == r['sha256']
        # Selectors0..7 are valid CAPS; selector8 deliberately returnsstatus3.
        assert q[1] == 0xe0 and q[4] <= 8 and q[5] == 0
        assert len(q) == len(data) == 8 and data[0] == 0x5a and data[1] == (0 if q[4] < 8 else 3) and data[2] == q[2] and data[3] == 2
        assert int.from_bytes(data[6:8], 'little') == binascii.crc_hqx(data[:6], 0xffff)
        assert int.from_bytes(q[6:8], 'little') == binascii.crc_hqx(q[:6], 0xffff)
    write_json(output/'completeness-recheck.json', recheck)
    write_json(output/'manifest.json', dict(schema=1, archived_utc=datetime.now(timezone.utc).isoformat(),
        hardware_access_by_archiver=False, result='complete', channels=expected,
        sampled_hz=100000000, samples=50000000, tagged_caps_pairs=9,
        caps_selector_scope='Selectors0..7 success; selector8 intentionally rejects withstatus3; all9 exact bytes and CRC match',
        scope='Known tagged CAPS traffic and exact CRC matched; digital sampled mapping, not analog signal-integrity proof',
        artifacts=archive.items))
    hashes = {f.relative_to(output).as_posix(): sha(f.read_bytes()) for f in output.rglob('*') if f.is_file() and f.name != 'SHA256.json'}
    write_json(output/'SHA256.json', hashes)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=FPGA/'validation/all-scenes-2026-11-05')
    p.add_argument('--probe-output', type=Path, default=FPGA/'validation/probe-map-complete-2026-11-05')
    p.add_argument('--host-root', type=Path, default=ROOT.parent/'tab5-fpga-gpu-matched-tx-bench')
    p.add_argument('--run-offline-gates', action='store_true')
    p.add_argument('--refresh', action='store_true')
    a = p.parse_args()
    if (a.output/'manifest.json').exists() and not a.refresh:
        p.error('Archive exists; use --refresh')
    if a.run_offline_gates:
        run_gates(a.host_root)
    a.output.mkdir(parents=True, exist_ok=True)
    archive = Archive(a.output)
    selected = FPGA/'build/all-scenes-gfx-v5/all_scenes'
    fs = selected/'impl/pnr/all_scenes.fs'
    assert sha(fs.read_bytes()) == SELECTED_SHA
    sdc = FPGA/'constraints/dock/all_scenes.sdc'
    pairs = exceptions(sdc)
    assert set(pairs) == set(exceptions(FPGA/'constraints/dock/triangle54filtered_batch_cdc.sdc'))
    candidates = []
    for version in range(1, 6):
        d = FPGA/f'build/all-scenes-gfx-v{version}/all_scenes'
        pnr = d/'impl/pnr'
        sta = timing(pnr/'all_scenes_tr_content.html')
        if version == 5:
            assert sta['counts'][COUNTS[2]] == sta['counts'][COUNTS[3]] == 0
        elif version < 3:
            assert sta['counts'][COUNTS[2]] > 0
        summary = dict(version='v'+str(version), sta=sta,
            programmed=version >= 3, selected=version == 5,
            source_snapshot='archive-time current source only; original version-specific source contents were not snapshotted before this build')
        for f in [pnr/'all_scenes_tr_content.html', pnr/'all_scenes.rpt.txt',
                  pnr/'all_scenes.rpt.html', pnr/'all_scenes.pin.html',
                  d/'all_scenes.gprj', d/'impl/gwsynthesis/all_scenes_syn.rsc.xml',
                  d/'impl/gwsynthesis/all_scenes_syn_rsc.xml',
                  d/'impl/gwsynthesis/all_scenes_syn.rpt.html',
                  d/'impl/gwsynthesis/all_scenes.log', pnr/'all_scenes.log']:
            if f.exists():
                archive.add(f, f'builds/v{version}/'+f.relative_to(d).as_posix())
        buildlog = FPGA/f'build/all-scenes-build-v{version}.log'
        archive.add(buildlog, f'builds/v{version}/build.log')
        if version >= 3:
            archive.add(pnr/'all_scenes.fs', f'builds/v{version}/all_scenes.fs')
            summary['fs_sha256'] = sha((pnr/'all_scenes.fs').read_bytes())
        else:
            summary['fs_omitted_reason'] = 'Never programmed; failed setup timing; reports retained'
        candidates.append(summary)
    archive.add(selected/'impl/pnr/all_scenes.vo', 'builds/v5/all_scenes.vo')

    # Parse actual selected project input paths, reject outside/foreign input.
    project = ET.parse(selected/'all_scenes.gprj')
    project_sources = []
    for entry in project.findall('.//File'):
        path = Path(entry.attrib['path']).resolve()
        relative = path.relative_to(ROOT.resolve())
        assert relative.parts[0] == 'fpga' and relative.parts[1] in ('link', 'gfx', 'platform', 'constraints')
        assert path.suffix in ('.v', '.cst', '.sdc')
        project_sources.append(relative.as_posix())
    extra = ['fpga/link/rtl/link_bringup.v', 'fpga/gfx/rtl/triangle_tile.v',
             'fpga/host/fire_fixed.h', 'fpga/host/raster2d_protocol.h',
             'fpga/host/link_protocol.h', 'fpga/tools/record_all_scenes.py']
    extra += [f.relative_to(ROOT).as_posix() for f in (FPGA/'builds/dock').glob('build_all_scenes*.tcl')]
    extra += [f.relative_to(ROOT).as_posix() for directory in ('gfx/tests', 'link/tests')
              for f in (FPGA/directory).glob('*') if f.is_file() and ('fire_' in f.name or 'all_scenes' in f.name or 'request_data_alignment' in f.name or 'clock_filter_active' in f.name)]
    current_sources = sorted(set(project_sources+extra))
    source_hashes = {n: sha((ROOT/n).read_bytes()) for n in current_sources}
    with zipfile.ZipFile(a.output/'source-snapshot.zip', 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for n in current_sources:
            z.writestr(n, (ROOT/n).read_bytes())
    source_hashes_after = {n: sha((ROOT/n).read_bytes()) for n in current_sources}
    if source_hashes_after != source_hashes:
        raise RuntimeError('Source changed while taking snapshot')
    write_json(a.output/'source-snapshot-sha256.json', source_hashes)

    # Archive only text evidence or test vectors, never executables/sim libraries/IP.
    for d in sorted((FPGA/'build').glob('all-scenes-*')):
        if not d.is_dir() or d.name.startswith('all-scenes-gfx-'):
            continue
        for f in sorted(d.rglob('*')):
            if f.is_file() and f.suffix in ('.json', '.log', '.txt'):
                archive.add(f, 'evidence/'+d.name+'/'+f.relative_to(d).as_posix())
    for f in sorted((FPGA/'build/fire-fixed-check').iterdir()):
        if f.is_file() and f.suffix in ('.json', '.log'):
            archive.add(f, 'evidence/fire-fixed-check/'+f.name)
    for f in (FPGA/'build').glob('all-scenes-sta-v*.json'):
        archive.add(f, 'evidence/'+f.name)

    hardware_comparisons = []
    host_build = a.host_root/'build'
    for label in ('all8-hardware-640-20261105', 'all8-hardware-640-registered-20261105',
                  'all8-hardware-640-tx5-20261105', 'all8-flow-continuation-640-tx5-20261105',
                  'all8-hardware-640-aligned-tx8-20261105', 'all8-flow-continuation-640-tx8-20261105'):
        f = host_build/label/'result.json'
        if f.exists():
            r = json.loads(f.read_text())
            archive.add(f, 'host-evidence/'+label+'.json')
            hardware_comparisons.append(dict(run=label, source=str(f.resolve()), sha256=sha(f.read_bytes()),
                passed=r.get('passed'), error=r.get('error'), cases=len(r.get('cases', [])),
                elf_sha256=r.get('info', {}).get('elf_sha256')))
    qualified = json.loads((host_build/'all8-hardware-640-aligned-tx8-20261105/result.json').read_text())
    flow = json.loads((host_build/'all8-flow-continuation-640-tx8-20261105/result.json').read_text())
    assert qualified['passed'] is True and len(qualified['cases']) == 24
    assert {(c['scene'], c['load'], c['frame']) for c in qualified['cases']} == {(s, l, 0) for s in range(8) for l in range(3)}
    assert flow['passed'] is True and {(c['scene'], c['load'], c['frame']) for c in flow['cases']} == {(7, l, 1) for l in range(3)}
    assert all(c['passed'] is True for c in qualified['cases']+flow['cases'])
    operations_dir = FPGA/'build/all-scenes-hardware-v5-20261105'
    operations = json.loads((operations_dir/'operations.json').read_text())
    assert all(x['exit_code'] == 0 for x in operations)
    assert '0x000094F0' in (operations_dir/'usercode.log').read_text()
    assert '0x00006020' in (operations_dir/'status.log').read_text()
    report_text = (selected/'impl/pnr/all_scenes.rpt.txt').read_text()
    assert re.search(r'Logic\s*\|\s*6759/20736', report_text)
    assert re.search(r'BSRAM\s*\|\s*5/46', report_text)
    assert re.search(r'DSP\s*\|\s*16\.5/24', report_text)
    tool_hashes = {}
    for path in [Path('D:/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'),
                 Path('D:/Gowin/Gowin_V1.9.12.04_x64/Programmer/bin/programmer_cli.exe')]:
        tool_hashes[str(path)] = sha(path.read_bytes())
    manifest = dict(schema=1, archived_utc=datetime.now(timezone.utc).isoformat(),
        hardware_access_by_archiver=False, repository_head=git('rev-parse', 'HEAD'),
        selected=dict(version='v5', fs_sha256=SELECTED_SHA, usercode='0x000094F0', status='0x00006020',
            resources=dict(logic='6759/20736', registers='2952/16173', bsram='5/46', dsp='16.5/24'),
            sta=candidates[-1]['sta'], metadata_exception_count=30, no_new_waivers=True,
            configuration=dict(ALL_SCENES_ENABLE=1, REQUEST_DATA_PIPELINE=1, REGISTER_INPUT=1, REPLY_ACTIVE_PIPELINE=1)),
        source_snapshot=dict(scope='Current archive-time sources, NOT a pre-build source hash capture',
            project_input_paths=project_sources, current_sha256=source_hashes,
            source_zip_sha256=sha((a.output/'source-snapshot.zip').read_bytes()),
            selected_gprj_sha256=sha((selected/'all_scenes.gprj').read_bytes()),
            selected_synthesized_netlist_sha256=sha((selected/'impl/gwsynthesis/all_scenes.vg').read_bytes()),
            build_tool_executable_sha256=tool_hashes,
            historical_v1_v4_sources='No original pre-build source snapshots; do not equate the current source ZIP with historical builds'),
        candidates=candidates, hardware_comparisons=hardware_comparisons,
        qualified_scope='640x360 TX8/RX5 frame0 all8x3 exact pixels, Flow frame1 all3loads exact pixels; not a completed120-frame full suite claim',
        excluded='No Gowin primitive library, encrypted netlist/IP, DDR controller IP, executables, or nonselected output netlist is copied',
        artifacts=archive.items)
    write_json(a.output/'manifest.json', manifest)
    hashes = {f.relative_to(a.output).as_posix(): sha(f.read_bytes()) for f in a.output.rglob('*') if f.is_file() and f.name != 'SHA256.json'}
    write_json(a.output/'SHA256.json', hashes)
    probe_map(a.probe_output, a.refresh)
    print(json.dumps(dict(output=str(a.output), artifacts=len(archive.items), source_files=len(current_sources),
        fs_sha256=SELECTED_SHA, image_cases=24, flow_cases=3, probe_output=str(a.probe_output))))


if __name__ == '__main__':
    main()
