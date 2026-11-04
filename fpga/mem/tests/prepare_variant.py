"""Generate single-variable DDR3 isolation variants from the paired-write candidate.

Each variant changes exactly ONE item against the baseline be42c604 sources
(PAIRED_WRITE=1, settle 256, PLL 324MHz, IP-driven ddr_cs, reset hold 27000).
Output: fpga/build/mem-variant-<id>/rtl/*.v (copies with a single textual edit).
No hardware access. Every substitution must match exactly once or the script fails.

  python fpga/mem/tests/prepare_variant.py base|cs0|rst|refwait|all
"""
import sys, hashlib, json
from pathlib import Path
root = Path(__file__).resolve().parents[2]
rtl = root / 'mem/rtl'
names = ['mem_deep_monitor', 'mem_pll', 'mem_bist', 'mem_mailbox', 'mem_link', 'mem_top']

# id -> (description, file, old, new)
VARIANTS = {
 'base': ('baseline: unchanged be42c604 sources, rebuilt for tool/netlist reproducibility', 'mem_top', 'module mem_top(', 'module mem_top('),
 'cs0': ('(b) ddr_cs fixed to 0 like the Sipeed sample; IP O_ddr_cs_n left open',
         'mem_top', '.O_ddr_cs_n(ddr_cs)', '.O_ddr_cs_n()'),
 'rst': ('(c) no extra 1ms reset hold after PLL lock: controller_reset_n = raw_reset_n && pll_lock',
         'mem_top', 'wire controller_reset_n=raw_reset_n&&pll_lock&&reset_hold==0;',
         'wire controller_reset_n=raw_reset_n&&pll_lock;'),
 'refwait': ('(d) wait 60000 USER cycles (~0.74ms @81MHz, >200 tREFI) after calibration instead of 256',
             'mem_top', 'mem_bist engine(user_clk,', 'mem_bist #(.CALIBRATION_SETTLE_CYCLES(60000)) engine(user_clk,'),
}

def build(vid):
    desc, fname, old, new = VARIANTS[vid]
    out = root / f'build/mem-variant-{vid}/rtl'
    out.mkdir(parents=True, exist_ok=True)
    rec = {'id': vid, 'description': desc, 'files': {}}
    for n in names:
        text = (rtl / f'{n}.v').read_bytes().decode()
        if n == fname:
            assert text.count(old) == 1, (vid, old, text.count(old))
            text = text.replace(old, new)
            if vid == 'cs0':
                # drive the pin constant low; the IP output is no longer connected
                anchor = '// USER state is only an LED observation here'
                assert text.count(anchor) == 1
                text = text.replace(anchor, "assign ddr_cs=1'b0;\n" + anchor)
        (out / f'{n}.v').write_bytes(text.encode())
        rec['files'][n] = hashlib.sha256(text.encode()).hexdigest()
    (out.parent / 'variant.json').write_text(json.dumps(rec, indent=2) + '\n')
    print('prepared', vid, '-', desc)

ids = list(VARIANTS) if sys.argv[1:] == ['all'] else sys.argv[1:]
assert ids and all(i in VARIANTS for i in ids), 'usage: prepare_variant.py base|cs0|rst|refwait|all'
for i in ids: build(i)
