"""Generate single-variable DDR3 isolation variants from the paired-write candidate.

Each variant changes exactly ONE item against the baseline be42c604 sources
(PAIRED_WRITE=1, settle 256, PLL 324MHz, IP-driven ddr_cs, reset hold 27000).
Output: fpga/build/mem-variant-<id>/rtl/*.v (copies with a single textual edit).
No hardware access. Every substitution must match exactly once or the script fails.

  python fpga/mem/tests/prepare_variant.py base|cs0|rst|refwait|pace|norst|readfirst|clk400|clk400_notap|clk400_asyncsdc|clk400dp|sampleip|sampleip_map|sampleip_map_t1|sampleip_map_t2|sampleip_map_t3|sampleip_map_t4|sampleip_map_t4_bw|sampleip_map_t4_bw2|clk400x_scoped|clk400x_dp000|clk400x_dp1116|clk400x_drvhigh|all
"""
import sys, hashlib, json
from pathlib import Path
root = Path(__file__).resolve().parents[2]
rtl = root / 'mem/rtl'
names = ['mem_deep_monitor', 'mem_pll', 'mem_bist', 'mem_bw', 'mem_bw_port', 'mem_mailbox', 'mem_link', 'mem_top']

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
 'sampleip': ('(i) bisect: OUR user logic (mem_bist/mailbox/link, 398/100 MHz reporting, PLL 398.25MHz) on the Sipeed sample IP (GowinSynthesis 1.9.8.05 DDR3_Memory_Interface_Top, 400MHz, 14-bit row); cs fixed 0 like the sample; no scheduler taps (deep_taps tied 0). DIAGNOSTIC: blanket-async clock groups like the sample SDC',
           'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'clk400_notap': ('(a2) clk400 on the UNTAPPED regenerated MemDDR3.vo: scheduler observation (024f deep words: FIFO pointers, send_wr, pre_info_valid, issue_*) is NOT available (taps tied 0) because issue_write/issue_read net names do not follow in the new netlist; native BIST counters and calibration flags remain',
           'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'clk400_asyncsdc': ('(a3) clk400_notap RTL/IP unchanged, but with the sample-style blanket-async SDC (mem_bist_sampleip.sdc) instead of the guarded SDC: tests whether calibration failure comes from constraint-driven placement/routing rather than the IP/PLL. Tap-less like clk400_notap',
           'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'clk400dp': ('(a4) clk400_notap RTL with the IP regenerated with Debug_Parameter_Enable (P1 101 = DLL CODESCAL, P2 6 = DQ IODELAY, P3/P4 40): reproduces the sample netlist CODESCAL/DQ-IODELAY, not its cmd/addr/CK IODELAY(40) nor SCAL_EN. Needs MEM_IP_TAG=clk400dp. Tap-less',
           'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'sampleip_map': ('(i2) sampleip with the BIST address placed for the sample IP row14 layout {bank3,row14(MSB 0),col10} (APP_ROW_PAD=1), so bank/row/capacity tests address the right bank bits; everything else as sampleip',
          'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'sampleip_map_t1': ('(i3) sampleip_map with the timing-oriented BIST (PIPELINE=1: registered START inputs and range check, 3-stage read compare). Same behaviour, START takes effect one cycle later, DONE after the last beat is accounted. Targets the -0.53ns setup violations at USER 99.5625MHz; the sample IP internal path is untouched',
          'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'sampleip_map_t2': ('(i4) sampleip_map_t1 plus PIPELINE=2: no reset_n term in the native-enable gating (busy is asynchronously cleared) and a registered copy of calibrated for fault/settle/start decisions (calibration loss detected one cycle later; enables still use the raw input)',
          'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'sampleip_map_t3': ('(i5) sampleip_map_t2 plus PIPELINE=3: registered calibrated also in the native-enable gating and both timeout comparators (wait, 64-bit total) registered one cycle ahead with identical firing cycle',
          'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'sampleip_map_t4_bw': ('(i7) sampleip_map_t4 plus the DDR3 bandwidth engine: mem_top BW_ENABLE=1 (mem_bw_port, LINK opcodes 0x60..0x6F, native-bus sharing with the BIST), BW_ROW_PAD=1, app_burst_number driven by the engine (0 outside bandwidth jobs). DIAGNOSTIC measurement image; BIST behaviour must stay as in sampleip_map_t4',
          'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'sampleip_map_t4_bw2': ('(i8) sampleip_map_t4_bw with BW_EN_PIPE=1, BW_SHARED_GATE=1: the IP-facing cmd/write enables are 4-input functions of the IP ready flags and shared registered gates (BIST and bandwidth engine next-cycle gates, cancel folded in) instead of an OR of two combinational enable cones, to remove the wr_buf_rdy -> enable -> IP wr_fifo path (-1.256 ns in t4_bw); 64-bit statistics counters are split into 16-bit segments with registered carries. Cycle behaviour identical to t4_bw. DIAGNOSTIC measurement image',
          'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'clk400x_dp000': ('(a5) untapped clk400 IP regenerated with Debug P1=101 (DLL CODESCAL), P2=0 (DQ IODELAY 0) - the values the generator itself uses for the official 1:2/200MHz reference. Needs MEM_IP_TAG=xdp000', 'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'clk400x_dp1116': ('(a6) untapped clk400 IP with Debug P1=111, P2=6: the generator default CODESCAL with the sample DQ IODELAY. Needs MEM_IP_TAG=xdp1116', 'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'clk400x_drvhigh': ('(a7) untapped clk400 IP with OUTPUT_DRV HIGH (RZQ/7=34 ohm); IPUG281 suggests changing it when initialisation fails. Needs MEM_IP_TAG=xdrvhigh', 'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'sampleip_map_t4': ('(i6) sampleip_map_t3 plus PIPELINE=4: native enables are a 3-input AND of the IP ready flops, a registered want and !cancel (one idle cycle per beat), to remove the IP ready -> enable -> IP FIFO flag combinational path that stays at -0.164 ns in t3',
          'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'clk400x_scoped': ('(a8) clk400_notap RTL/IP with the guarded SDC plus the SCOPED exceptions E1-E4 proposed in docs/DDR3_clk400_SDC限定例外案_2026-11-04.md (IP-internal/reset sys27->user100 paths false-pathed for setup/recovery only, held_op given the held-bundle max-delay contract). Needs MEM_IP_TAG=clk400; verifies the proposal by an official STA run', 'mem_pll', 'pll.IDIV_SEL=0', 'pll.IDIV_SEL=3'),
 'refwait': ('(d) wait 60000 USER cycles (~0.74ms @81MHz, >200 tREFI) after calibration instead of 256',
             'mem_top', 'mem_bist engine(user_clk,', 'mem_bist #(.CALIBRATION_SETTLE_CYCLES(60000)) engine(user_clk,'),
}

def build(vid):
    if vid in ('sampleip', 'sampleip_map', 'sampleip_map_t1', 'sampleip_map_t2', 'sampleip_map_t3', 'sampleip_map_t4', 'sampleip_map_t4_bw', 'sampleip_map_t4_bw2'):
        # The pinned Sipeed IP is not in git: refuse to prepare unless the local copy exists and matches its SHA-256.
        import importlib.util
        spec = importlib.util.spec_from_file_location('fetch_sipeed_ddr_ip', root / 'tools/fetch_sipeed_ddr_ip.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        import os
        bad = mod.verify(build_only=os.environ.get('SIPEED_VERIFY_SCOPE') == 'build')  # build-only: offline, reference-only files absent (documented)
        if bad:
            raise SystemExit(f'{vid}: pinned Sipeed IP missing or modified: {bad}; see docs/DDR3_旧IP保管と再現手順_2026-11-04.md')
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
            if vid.startswith('clk400x_') or vid in ('clk400', 'sampleip', 'sampleip_map', 'sampleip_map_t1', 'sampleip_map_t2', 'sampleip_map_t3', 'sampleip_map_t4', 'sampleip_map_t4_bw', 'sampleip_map_t4_bw2', 'clk400_notap', 'clk400_asyncsdc', 'clk400dp'):
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
        if vid in ('sampleip_map', 'sampleip_map_t1', 'sampleip_map_t2', 'sampleip_map_t3', 'sampleip_map_t4', 'sampleip_map_t4_bw', 'sampleip_map_t4_bw2') and n == 'mem_top':
            o = 'mem_bist engine('
            assert text.count(o) == 1
            pipe = '4' if vid in ('sampleip_map_t4_bw', 'sampleip_map_t4_bw2') else vid[-1]
            text = text.replace(o, 'mem_bist #(.APP_ROW_PAD(1)' + ('' if vid == 'sampleip_map' else ',.PIPELINE(' + pipe + ')') + ') engine(')
        if (vid.startswith('clk400x_') or vid in ('clk400', 'sampleip', 'sampleip_map', 'sampleip_map_t1', 'sampleip_map_t2', 'sampleip_map_t3', 'sampleip_map_t4', 'sampleip_map_t4_bw', 'sampleip_map_t4_bw2', 'clk400_notap', 'clk400_asyncsdc', 'clk400dp')) and n == 'mem_top':
            o = 'mem_mailbox control('
            assert text.count(o) == 1
            text = text.replace(o, "mem_mailbox #(.MEM_MHZ(16'd398),.USER_MHZ(16'd100)) control(")
            if vid in ('sampleip_map_t4_bw', 'sampleip_map_t4_bw2'):
                # bandwidth image: enable the engine (module-body parameters of mem_top), row-14 address layout, burst number to the IP
                for po, pn in (('parameter BW_ENABLE=0;', 'parameter BW_ENABLE=1;'), ('parameter BW_ROW_PAD=0;', 'parameter BW_ROW_PAD=1;')) +                         ((('parameter BW_EN_PIPE=0;', 'parameter BW_EN_PIPE=1;'), ('parameter BW_SHARED_GATE=0;', 'parameter BW_SHARED_GATE=1;')) if vid == 'sampleip_map_t4_bw2' else ()):
                    assert text.count(po) == 1, po
                    text = text.replace(po, pn)
        if (vid.startswith('clk400x_') or vid in ('clk400_notap', 'clk400_asyncsdc', 'clk400dp')) and n == 'mem_top':
            o = '.deep_taps(deep_taps),'
            assert text.count(o) == 1
            text = text.replace(o, '')
            a = '// USER state is only an LED observation here'
            assert text.count(a) == 1
            text = text.replace(a, "assign deep_taps=64'b0;" + (chr(13) + chr(10) if chr(13) in text else chr(10)) + a)
        if vid in ('sampleip', 'sampleip_map', 'sampleip_map_t1', 'sampleip_map_t2', 'sampleip_map_t3', 'sampleip_map_t4', 'sampleip_map_t4_bw', 'sampleip_map_t4_bw2') and n == 'mem_top':
            import re as _re
            m = _re.search('MemDDR3 controller' + chr(92) + '(.*?' + chr(92) + ');' + chr(13) + '?' + chr(10), text, _re.S)
            assert m and text.count('MemDDR3 controller(') == 1
            inst = '''wire[13:0] sample_ddr_addr;wire sample_cs_unused,sample_cmd_en_unused;
assign ddr_addr=sample_ddr_addr[12:0];assign ddr_cs=1'b0;assign deep_taps=64'b0;
DDR3_Memory_Interface_Top controller(.clk(sys_clk),.memory_clk(memory_clk),.pll_lock(pll_lock),.rst_n(controller_reset_n),
.app_burst_number(6'd0),.cmd(cmd),.cmd_en(cmd_en),.addr({1'b0,address}),.cmd_ready(cmd_ready),
.wr_data(wr_data),.wr_data_en(wr_en),.wr_data_end(wr_end),.wr_data_mask(mask),.wr_data_rdy(wr_ready),
.rd_data(rd_data),.rd_data_valid(rd_valid),.rd_data_end(rd_end),.sr_req(1'b0),.ref_req(1'b0),.burst(1'b1),
.clk_out(user_clk),.ddr_rst(ip_user_reset),.init_calib_complete(calibrated),.sr_ack(),.ref_ack(),
.O_ddr_addr(sample_ddr_addr),.O_ddr_ba(ddr_bank),.O_ddr_cs_n(sample_cs_unused),.O_ddr_ras_n(ddr_ras),.O_ddr_cas_n(ddr_cas),
.O_ddr_we_n(ddr_we),.O_ddr_clk(ddr_ck),.O_ddr_clk_n(ddr_ck_n),.O_ddr_cke(ddr_cke),.O_ddr_odt(ddr_odt),
.O_ddr_reset_n(ddr_reset_n),.O_ddr_dqm(ddr_dm),.IO_ddr_dq(ddr_dq),.IO_ddr_dqs(ddr_dqs),.IO_ddr_dqs_n(ddr_dqs_n));
'''
            if vid in ('sampleip_map_t4_bw', 'sampleip_map_t4_bw2'):
                assert inst.count(".app_burst_number(6'd0)") == 1
                inst = inst.replace(".app_burst_number(6'd0)", '.app_burst_number(burst_number)')
            text = text[:m.start()] + inst.replace(chr(10), chr(13) + chr(10) if chr(13) in text else chr(10)) + text[m.end():]
        if vid == 'sampleip_map_t4_bw2' and n in ('mem_bist', 'mem_mailbox', 'mem_top'):
            # shared enable stage: enables the `ifdef BW_GATES code (gate exports of the BIST/mailbox, shared gates in mem_top)
            text = '`define BW_GATES' + (chr(13) + chr(10) if chr(13) in text else chr(10)) + text
        (out / f'{n}.v').write_bytes(text.encode())
        rec['files'][n] = hashlib.sha256(text.encode()).hexdigest()
    if vid == 'clk400x_scoped':
        base = (root / 'build/mem-scheduler-diag-input-clk400/mem_bist.sdc').read_text()
        prop = (root / 'mem/config/mem_bist_clk400_scoped.sdc.proposal').read_text(encoding='utf-8')
        i = prop.index('// ---- E1')
        extra = chr(10).join([
            '// ---- E5/E6 (added after the first official STA run left 5 setup + 3 recovery paths) ----',
            '// E5: IP-internal sys27-launched reset/load synchronisers -> DQS RLOADN/WLOADN and the command FIFO memory DI pins',
            'set_false_path -setup -from [get_regs {controller/gw3_top_u_ddr_phy_top_ddr_rsti_reg* controller/gw3_top_u_ddr_phy_top_ddr_sync_* controller/gw3_top_u_ddr_phy_top_wloadn_*}] -to [get_pins {controller/*u_dqs/RLOADN controller/*u_dqs/WLOADN controller/gw3_top_u_gwmc_top_gw_cmd0_mem_mem_*_s/DI*}]',
            '// E6: IP reset synchroniser (ddr_rst source) -> our async-assert/sync-release user_reset_sync CLEAR (recovery only)',
            'set_false_path -setup -from [get_regs {controller/gw3_top_u_ddr_phy_top_ddr_rsti_reg*}] -to [get_pins {user_reset_sync_0_s0/CLEAR user_reset_sync_1_s0/CLEAR user_reset_sync_2_s0/CLEAR}]'])
        (out.parent / 'mem_bist.sdc').write_text(base.rstrip() + chr(10) + prop[i:] + chr(10) + extra + chr(10), encoding='utf-8')
        rec['sdc'] = 'guarded clk400 SDC + proposal exceptions E1-E4 + extended reports'
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
assert ids and all(i in VARIANTS for i in ids), 'usage: prepare_variant.py base|cs0|rst|refwait|pace|norst|readfirst|clk400|clk400_notap|clk400_asyncsdc|clk400dp|sampleip|sampleip_map|sampleip_map_t1|sampleip_map_t2|sampleip_map_t3|sampleip_map_t4|sampleip_map_t4_bw|sampleip_map_t4_bw2|clk400x_scoped|clk400x_dp000|clk400x_dp1116|clk400x_drvhigh|all'
for i in ids: build(i)
