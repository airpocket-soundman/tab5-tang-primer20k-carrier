"""Prepare the MEMV1 image inputs (offline). Copies the RTL to build/memv1/rtl, applies the established 398.25MHz PLL
setting (same text substitution as prepare_variant.py sampleip_map_t4) and checks the pinned Sipeed IP.
The Sipeed sample IP (Gowin encrypted, license unconfirmed) is NOT in git: pass --ip-src to copy it into the ignored
fpga/build/sipeed-ddr-test-e469df4c tree after its SHA-256 matched fpga/validation/sipeed-ddr-test-reference-2026-11-04.json."""
import argparse, hashlib, json, shutil
from pathlib import Path
root = Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser()
ap.add_argument('--ip-src', help='path of a verified ddr3_memory_interface.v to copy into the ignored build tree')
ap.add_argument('--fast-reply',action='store_true',help='Experimental conditioned response clock and 216MHz sampler PLL')
ap.add_argument('--reply-phase-ticks',type=int,choices=(0,3),default=0)
cli = ap.parse_args()
if cli.reply_phase_ticks and not cli.fast_reply:ap.error('--reply-phase-ticks requires --fast-reply')
ref = json.loads((root / 'validation/sipeed-ddr-test-reference-2026-11-04.json').read_text(encoding='utf-8'))['files']
rel = 'src/ddr3_memory_interface/ddr3_memory_interface.v'
dest = root / 'build/sipeed-ddr-test-e469df4c' / rel
if cli.ip_src:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cli.ip_src, dest)
data = dest.read_bytes() if dest.exists() else b''
sha = hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()
if sha != ref[rel]['sha256_lf_normalized']:
    raise SystemExit(f'pinned Sipeed IP missing or modified ({sha}); see docs/DDR3_旧IP保管と再現手順_2026-11-04.md')
out = root / (('build/memv1-fast-phase3/rtl' if cli.reply_phase_ticks else 'build/memv1-fast/rtl') if cli.fast_reply else 'build/memv1/rtl')
out.mkdir(parents=True, exist_ok=True)
names = ['memv1_crc32b', 'mem_pll', 'mem_bist', 'mem_mailbox', 'mem_adapter', 'memv1_bridge', 'memv1_sys', 'mem_v1_core', 'mem_v1_top']
rec = {'ip_sha256': sha, 'fast_reply':cli.fast_reply,'reply_phase_ticks':cli.reply_phase_ticks,'files': {}}
for n in names:
    text = (root / f'mem/rtl/{n}.v').read_bytes().decode()
    if n=='mem_v1_top' and cli.fast_reply:
        text=text.replace('parameter FAST_REPLY_ENABLE=0','parameter FAST_REPLY_ENABLE=1').replace('parameter REPLY_PHASE_TICKS=0',f'parameter REPLY_PHASE_TICKS={cli.reply_phase_ticks}')
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
if cli.fast_reply:
    for source in ('mem/rtl/memv1_reply_raw.v','link/rtl/reply_clock_filter.v','platform/dock/dock_pll216.v','link/rtl/reply_phase_delay.v'):
        p=root/source;shutil.copyfile(p,out/p.name);rec['files'][p.stem]=hashlib.sha256(p.read_bytes()).hexdigest()
sdc = (root / 'mem/config/mem_bist_sampleip.sdc').read_text(encoding='utf-8')
# the mailbox instance is `control` in mem_top but `core/control` in mem_v1_top
assert sdc.count('control/') > 0
sdc = sdc.replace('control/', 'core/control/')
# deep_debug is tied to 0 in mem_v1_core (sample IP has no scheduler taps): the deep snapshot registers are optimized away
sdc = chr(10).join(l for l in sdc.splitlines() if 'deep_snapshot' not in l) + chr(10)
if cli.fast_reply:
    sdc=sdc.replace('set_clock_groups -asynchronous -group [get_clocks {sys27}] -group [get_clocks {memory398}] -group [get_clocks {user100}]','// Preserve legacy DDR diagnostic exclusions using explicit clock pairs.\n// Clock groups can otherwise exempt the newly introduced reply domains too.\nset_false_path -from [get_clocks {sys27}] -to [get_clocks {memory398 user100}]\nset_false_path -from [get_clocks {memory398 user100}] -to [get_clocks {sys27}]\nset_false_path -from [get_clocks {memory398}] -to [get_clocks {user100}]\nset_false_path -from [get_clocks {user100}] -to [get_clocks {memory398}]')
    sdc += """
// Experimental fast response clocks. No physical/STA qualification implied.
create_generated_clock -name reply216 -source [get_ports {sys_clk}] -multiply_by 8 [get_nets {reply_sample_clk}]
create_clock -name conditioned_reply -period 18.518519 [get_nets {core/link/phase_reply_clk}]
// Only the first SYS/host-to-sampler activity sampling stage is asynchronous.
set_false_path -to [get_pins {core/link/reply_active_sync_0_s0/D}]
// Return indications are CDC observations; only stage0 D is exempt.
set_false_path -to [get_pins {core/link/fast_done_sync_0_s0/D}]
set_false_path -to [get_pins {core/link/fast_started_sync_0_s0/D}]
set_false_path -to [get_pins {core/link/fast_progress_sync_0_s0/D}]
set_false_path -to [get_pins {core/link/fast_error_sync_0_s0/D}]
set_false_path -to [get_pins {core/link/filter_fault_sync_0_s0/D}]
// SYS metadata is captured >=2 SYS cycles before offer. Bound its physical
// arrival to 37ns; this is not a blanket exception between clock domains.
set_max_delay -from [get_regs {core/link/fast_header* core/link/fast_kind* core/link/fast_beats* core/link/fast_crc32* core/link/fast_prefix*}] -to [get_regs {core/link/fast_reply.serializer/*}] 37
set_false_path -hold -from [get_regs {core/link/fast_header* core/link/fast_kind* core/link/fast_beats* core/link/fast_crc32* core/link/fast_prefix*}] -to [get_regs {core/link/fast_reply.serializer/*}]
report_timing -setup -from [get_regs {core/link/fast_header* core/link/fast_kind* core/link/fast_beats* core/link/fast_crc32* core/link/fast_prefix*}] -to [get_regs {core/link/fast_reply.serializer/*}] -max_paths 1000
report_timing -setup -from [get_regs {core/link/fast_header*}] -to [get_regs {core/link/fast_reply.serializer/*}] -max_paths 1000
report_timing -setup -from [get_regs {core/link/fast_kind*}] -to [get_regs {core/link/fast_reply.serializer/*}] -max_paths 1000
report_timing -setup -from [get_regs {core/link/fast_beats*}] -to [get_regs {core/link/fast_reply.serializer/*}] -max_paths 1000
report_timing -setup -from [get_regs {core/link/fast_crc32*}] -to [get_regs {core/link/fast_reply.serializer/*}] -max_paths 1000
report_timing -setup -from [get_regs {core/link/fast_prefix*}] -to [get_regs {core/link/fast_reply.serializer/*}] -max_paths 1000
report_timing -setup -from [get_clocks {reply216}] -max_paths 100
report_timing -setup -from [get_clocks {conditioned_reply}] -max_paths 100
"""
if cli.fast_reply:
    reply_net='core/link/fast_reply.phase_shift.delay/reply_read_clk' if cli.reply_phase_ticks else 'core/link/fast_reply.conditioner/reply_read_clk'
    sdc=sdc.replace('core/link/phase_reply_clk',reply_net)
(out.parent / 'mem_v1.sdc').write_text(sdc, encoding='utf-8')
rec['sdc_sha256'] = hashlib.sha256(sdc.encode()).hexdigest()
(out.parent / 'prepared.json').write_text(json.dumps(rec, indent=2) + '\n')
print('prepared build/memv1/rtl; IP sha256', sha)
