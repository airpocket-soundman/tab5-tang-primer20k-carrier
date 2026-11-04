"""Generate single-variable DDR3 isolation variants from the paired-write candidate.

Each variant changes exactly ONE item against the baseline be42c604 sources
(PAIRED_WRITE=1, settle 256, PLL 324MHz, IP-driven ddr_cs, reset hold 27000).
Output: fpga/build/mem-variant-<id>/rtl/*.v (copies with a single textual edit).
No hardware access. Every substitution must match exactly once or the script fails.

  python fpga/mem/tests/prepare_variant.py base|cs0|rst|refwait|pace|norst|readfirst|clk400|all
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
 'pace': ('(e) sample-like pacing: commands/write data issued only when a free-running 8-bit counter is 0 (one per 256 USER cycles), as the Sipeed tester does with work_counter==0',
          'mem_bist', 'assign app_cmd_en=app_cmd_ready && active &&', 'assign app_cmd_en=app_cmd_ready && active && pace_ok &&'),
 'norst': ('(g) IP ddr_rst output left open like the Sipeed sample (ip_user_reset tied 0); the IP no longer resets the USER logic',
          'mem_top', '.ddr_rst(ip_user_reset)', '.ddr_rst()'),
 'readfirst': ('(h) BIST starts with the verify (read) phase instead of the fill (write) phase: tests whether the scheduler serves READ commands (mismatch errors are expected and irrelevant)',
          'mem_bist', 'else begin busy<=1;phase<=1;base_latched<=base_byte;', 'else begin busy<=1;phase<=2;base_latched<=base_byte;'),
 'clk400': ('(a) memory clock 324->398.25MHz (27*59/4; IP Memory_Clock 400, as the Sipeed sample); USER 81->99.5625MHz; SYSQUERY reports 398/100. Needs MEM_IP_TAG=clk400 IP/taps/guarded flow',
           'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
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
            if vid == 'pace':
                a1 = '    assign app_write_en=app_write_ready && active && writing && !data_sent &&'
                assert text.count(a1) == 1
                text = text.replace(a1, a1 + ' pace_ok &&')
                a2 = '    wire writing=phase==1 || phase==3;'
                assert text.count(a2) == 1
                ins = ("    reg [7:0] pace_counter; wire pace_ok=pace_counter==8'd0;" + chr(10)
                       + "    always @(posedge clk or negedge reset_n) if(!reset_n) pace_counter<=0; else pace_counter<=pace_counter+1'b1;" + chr(10))
                text = text.replace(a2, ins + a2)
            if vid == 'clk400':
                t2 = text
                for o, n2 in [('pll.FBDIV_SEL=11', 'pll.FBDIV_SEL=58'), ('27*(11+1)/(0+1)=324MHz; ODIV2 gives648MHz VCO.', '27*(58+1)/(3+1)=398.25MHz; ODIV2 gives796.5MHz VCO.')]:
                    assert t2.count(o) == 1, o
                    t2 = t2.replace(o, n2)
                text = t2
            if vid == 'norst':
                anchor = '// USER state is only an LED observation here'
                assert text.count(anchor) == 1
                text = text.replace(anchor, "assign ip_user_reset=1'b0;" + chr(10) + anchor)
            if vid == 'cs0':
                # drive the pin constant low; the IP output is no longer connected
                anchor = '// USER state is only an LED observation here'
                assert text.count(anchor) == 1
                text = text.replace(anchor, "assign ddr_cs=1'b0;\n" + anchor)
        if vid == 'clk400' and n == 'mem_top':
            o = 'mem_mailbox control('
            assert text.count(o) == 1
            text = text.replace(o, "mem_mailbox #(.MEM_MHZ(16'd398),.USER_MHZ(16'd100)) control(")
        (out / f'{n}.v').write_bytes(text.encode())
        rec['files'][n] = hashlib.sha256(text.encode()).hexdigest()
    if vid == 'cs0':
        # With O_ddr_cs_n unconnected, synthesis removes the cmd-lane OSER8 that drove it
        # (cmd_oserdes_gen[0]); the guarded SDC's recovery exception on its RESET pin then
        # has no object (TA2003). Drop exactly the exceptions on that removed cell.
        src = root / 'build/mem-scheduler-diag-input/mem_bist.sdc'
        lines = src.read_text().splitlines()
        drop = [l for l in lines if 'cmd_oserdes_gen[0].u_cmd_gen/' in l]
        assert len(drop) >= 1, 'prepare_guarded.py must run first'
        (out.parent / 'mem_bist.sdc').write_text(chr(10).join(l for l in lines if l not in drop) + chr(10))
        rec['sdc_lines_dropped'] = drop
    (out.parent / 'variant.json').write_text(json.dumps(rec, indent=2) + '\n')
    print('prepared', vid, '-', desc)

ids = list(VARIANTS) if sys.argv[1:] == ['all'] else sys.argv[1:]
assert ids and all(i in VARIANTS for i in ids), 'usage: prepare_variant.py base|cs0|rst|refwait|pace|norst|readfirst|clk400|all'
for i in ids: build(i)
