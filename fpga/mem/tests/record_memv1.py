"""Attest the MEMV1 image build (offline). Reads build/memv1/out/mem_bist/impl/pnr and writes
validation/memv1-image-2026-11-05.json (+ gz'd reports; the .fs itself is NOT archived, only its SHA-256).
STA is the Gowin report under the DIAGNOSTIC sampleip SDC (blanket-asynchronous clock groups): cross-domain
paths (SYS27 <-> USER ~99.56MHz <-> memory 398MHz) are not timed by this SDC and the IP-internal paths are not
individually constrained. Not a sign-off; no hardware result."""
import gzip, hashlib, json, re
from html.parser import HTMLParser
from pathlib import Path
root = Path(__file__).resolve().parents[2]
pnr = root / 'build/memv1/out/mem_bist/impl/pnr'
class Text(HTMLParser):
    def __init__(s): super().__init__(); s.items = []
    def handle_data(s, d):
        if d.strip(): s.items.append(d.strip())
t = Text(); t.feed((pnr / 'mem_bist_tr_content.html').read_text()); I = t.items
def fol(l): return I[I.index(l) + 1]
def worst(tab):
    it = I[I.index(tab):]
    if 'Data Delay' not in it[:16]: return None
    i = it.index('Data Delay') + 1
    return {'slack_ns': float(it[i + 1]), 'from': it[i + 2], 'to': it[i + 3]} if it[i] == '1' else None
def neg(tab):
    s = I.index(tab)
    if 'Data Delay' not in I[s:s + 16]: return 0
    i = I.index('Data Delay', s) + 1; n = 0
    while I[i].isdigit():
        n += I[i + 1].startswith('-'); i += 9
    return n
fm = I[I.index('Max Frequency Summary:'):]
def fmax(n): return float(fm[fm.index(n) + 2].replace('(MHz)', ''))
def cst_audit(report):
    cst = (root / 'mem/config/mem_bist.cst').read_text(encoding='utf-8-sig')
    exp = dict(re.findall(r'^IO_LOC\s+"([^"]+)"\s+([A-Z]\d+(?:,[A-Z]\d+)?)', cst, re.M))
    types = dict(re.findall(r'^IO_PORT\s+"([^"]+)"\s+IO_TYPE=(\w+)', cst, re.M))
    act = {}
    for line in report.splitlines():
        f = [v.strip() for v in line.split('|')]
        if len(f) > 10 and re.fullmatch(r'[a-zA-Z_]\w*(?:\[\d+\])?', f[0]): act[f[0]] = f
    bad = []
    for n, b in exp.items():
        r = act.get(n)
        if not r or r[2].split('/')[0] != b or r[7] != types[n] or r[-1] != ('1.5' if '15' in types[n] else '3.3'): bad.append(n)
    return {'constrained_ports': len(exp), 'mismatches': bad, 'passed': not bad}
rep = (pnr / 'mem_bist.rpt.txt').read_text()
fs = (pnr / 'mem_bist.fs').read_bytes()
body = b'\n'.join(l for l in fs.split(b'\n') if not l.startswith(b'//'))
console = (root / 'build/memv1-console.log').read_bytes()
log = console.decode('utf-16') if console[:2] in (b'\xff\xfe', b'\xfe\xff') else console.decode('utf-8', errors='replace')
assert 'MEM_BUILD_FLOW_RETURNED' in log and not re.search(r'ERROR\s*\(', log)
# the first memv1 image had a 1593MHz memory clock: these two tool warnings flag exactly that
assert 'PA1019) : Invalid CLKOUT' not in log and 'TA1123' not in log, 'PLL/clock frequency warning in build log'
prep = json.loads((root / 'build/memv1/prepared.json').read_text())
out = root / 'validation/memv1-image-2026-11-05'
out.mkdir(parents=True, exist_ok=True)
for src, name in [(pnr / 'mem_bist.rpt.txt', 'mem_bist.rpt.txt.gz'), (pnr / 'mem_bist_tr_content.html', 'mem_bist_tr_content.html.gz'),
                  (root / 'build/memv1-console.log', 'build-console.log.gz')]:
    with gzip.GzipFile(out / name, 'wb', mtime=0) as g: g.write(src.read_bytes())
res = {
 'scope': 'offline build only; no programmer/UART/DRAM access; hardware behaviour of this image UNVERIFIED; IP is the Sipeed sample IP e469df4c (license unconfirmed, not in git)',
 'tool': 'Gowin V1.9.11.03 Education (81398), gw_sh, no programming', 'part': 'GW2A-LV18PG256C8/I7', 'top': 'mem_v1_top',
 'fs_sha256': hashlib.sha256(fs).hexdigest(), 'fs_sha256_without_comment_lines': hashlib.sha256(body).hexdigest(), 'fs_bytes': len(fs),
 'usercode': re.search(r'//UserCode: (0x\w+)', fs.decode()).group(1),
 'pll': prep['pll'], 'ip_sha256': prep['ip_sha256'], 'rtl_sha256': prep['files'], 'sdc_sha256': prep['sdc_sha256'],
 'sta': {'sdc': 'DIAGNOSTIC mem_bist_sampleip.sdc (blanket-async clock groups, control/ -> core/control/, deep_snapshot lines dropped)',
         'setup_violated_endpoints': int(fol('Numbers of Setup Violated Endpoints')), 'hold_violated_endpoints': int(fol('Numbers of Hold Violated Endpoints')),
         'worst_setup': worst('Setup Paths Table'), 'worst_hold': worst('Hold Paths Table'), 'worst_recovery': worst('Recovery Paths Table'), 'worst_removal': worst('Removal Paths Table'),
         'negative_paths': {k: neg(k + ' Paths Table') for k in ['Setup', 'Hold', 'Recovery', 'Removal']},
         'fmax_mhz': {n: fmax(n) for n in ('sys27', 'memory398', 'user100')}},
 'logic': re.search(r'Logic\s+\|\s+(\d+/\d+)', rep).group(1), 'registers': re.search(r'Register\s+\|\s+(\d+/\d+)', rep).group(1),
 'bsram': (re.search(r'BSRAM\s+\|\s+(\d+/\d+)', rep) or [None, None])[1],
 'pin_audit': cst_audit(rep),
 'archive': out.relative_to(root).as_posix()}
(root / 'validation/memv1-image-2026-11-05.json').write_text(json.dumps(res, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps(res, indent=1, ensure_ascii=False))
