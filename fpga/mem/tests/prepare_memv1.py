"""Prepare the MEMV1 image inputs (offline). Copies the RTL to build/memv1/rtl, applies the established 398.25MHz PLL
setting (same text substitution as prepare_variant.py sampleip_map_t4) and checks the pinned Sipeed IP.
The Sipeed sample IP (Gowin encrypted, license unconfirmed) is NOT in git: pass --ip-src to copy it into the ignored
fpga/build/sipeed-ddr-test-e469df4c tree after its SHA-256 matched fpga/validation/sipeed-ddr-test-reference-2026-11-04.json."""
import argparse, hashlib, json, shutil
from pathlib import Path
root = Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser()
ap.add_argument('--ip-src', help='path of a verified ddr3_memory_interface.v to copy into the ignored build tree')
a = ap.parse_args()
ref = json.loads((root / 'validation/sipeed-ddr-test-reference-2026-11-04.json').read_text(encoding='utf-8'))['files']
rel = 'src/ddr3_memory_interface/ddr3_memory_interface.v'
dest = root / 'build/sipeed-ddr-test-e469df4c' / rel
if a.ip_src:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(a.ip_src, dest)
data = dest.read_bytes() if dest.exists() else b''
sha = hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()
if sha != ref[rel]['sha256_lf_normalized']:
    raise SystemExit(f'pinned Sipeed IP missing or modified ({sha}); see docs/DDR3_旧IP保管と再現手順_2026-11-04.md')
out = root / 'build/memv1/rtl'
out.mkdir(parents=True, exist_ok=True)
names = ['memv1_crc32b', 'mem_pll', 'mem_bist', 'mem_mailbox', 'mem_adapter', 'memv1_bridge', 'memv1_sys', 'mem_v1_core', 'mem_v1_top']
rec = {'ip_sha256': sha, 'files': {}}
for n in names:
    text = (root / f'mem/rtl/{n}.v').read_bytes().decode()
    if n == 'mem_pll':
        # Same three substitutions as prepare_variant.py (clk400/sampleip*): IDIV_SEL 0->3 is REQUIRED, otherwise
        # the memory clock is 27*59=1593MHz and the IP never calibrates (first memv1 image, 2026-11-05).
        for o, r in [('pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'), ('pll.FBDIV_SEL=11', 'pll.FBDIV_SEL=58'),
                     ('27*(11+1)/(0+1)=324MHz; ODIV2 gives648MHz VCO.', '27*(58+1)/(3+1)=398.25MHz; ODIV2 gives796.5MHz VCO.')]:
            assert text.count(o) == 1, o
            text = text.replace(o, r)
        import re as _re
        a = {k: int(v) for k, v in _re.findall(r'pll[.](IDIV_SEL|FBDIV_SEL|ODIV_SEL)=(\d+)', text)}
        fclk = 27.0 * (a['FBDIV_SEL'] + 1) / (a['IDIV_SEL'] + 1)
        assert abs(fclk - 398.25) < 0.01 and 500 <= fclk * a['ODIV_SEL'] <= 1250 and fclk <= 625, (a, fclk)
        rec['pll'] = dict(a, memory_clk_mhz=fclk, vco_mhz=fclk * a['ODIV_SEL'], user_clk_mhz=fclk / 4)
    (out / f'{n}.v').write_bytes(text.encode())
    rec['files'][n] = hashlib.sha256(text.encode()).hexdigest()
sdc = (root / 'mem/config/mem_bist_sampleip.sdc').read_text(encoding='utf-8')
# the mailbox instance is `control` in mem_top but `core/control` in mem_v1_top
assert sdc.count('control/') > 0
sdc = sdc.replace('control/', 'core/control/')
# deep_debug is tied to 0 in mem_v1_core (sample IP has no scheduler taps): the deep snapshot registers are optimized away
sdc = chr(10).join(l for l in sdc.splitlines() if 'deep_snapshot' not in l) + chr(10)
(out.parent / 'mem_v1.sdc').write_text(sdc, encoding='utf-8')
rec['sdc_sha256'] = hashlib.sha256(sdc.encode()).hexdigest()
(out.parent / 'prepared.json').write_text(json.dumps(rec, indent=2) + '\n')
print('prepared build/memv1/rtl; IP sha256', sha)
