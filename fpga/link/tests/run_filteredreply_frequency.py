"""Full CRC/payload model of conditioned reply clock; records expected failures."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog',required=True);p.add_argument('--vvp',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--quick',action='store_true');a=p.parse_args()
    files=['link/rtl/reply_clock_filter.v','link/rtl/link_reply_raw.v','link/rtl/link_bringup_filtered.v',
           'gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v',
           'gfx/rtl/triangle_depth.v','link/tests/tb_filteredreply_frequency.v']
    cases=[]
    configs=[(phase,wire,tco)for phase in (0,1)for wire in ((0,)if a.quick else (0,2,5))for tco in ((0,)if a.quick else (0,2))]
    with tempfile.TemporaryDirectory(prefix='filter-full-')as td:
        for phase,wire,tco in configs:
            exe=Path(td)/'model.vvp'
            params=dict(EXTENDED_MODE=1,CLOCK_PATTERN=1,SAMPLE_INVERTED=phase,ONE_WAY_DELAY_PS=wire*1000,FPGA_TCO_PS=tco*1000)
            subprocess.run([a.iverilog,'-g2012','-s','tb_filteredreply_frequency',*[f'-Ptb_filteredreply_frequency.{k}={v}'for k,v in params.items()],'-o',str(exe),*[str(ROOT/f)for f in files]],check=True,capture_output=True)
            r=subprocess.run([a.vvp,str(exe)],text=True,capture_output=True,check=True,timeout=240)
            count=0
            for line in r.stdout.splitlines():
                if not line.startswith('SWEEP,'):continue
                frequency,offset_phase,delay,kind,passed,offset,ready=map(int,line.split(',')[1:]);count+=1
                cases.append(dict(configured_hz=frequency,sys_phase_ns=offset_phase,sample_phase='inverted_input_only'if phase else'legacy',
                                  one_way_wire_assumed_ns=wire,fpga_Tco_assumed_ns=tco,full_body_exact=bool(passed),
                                  unique_complete_header_payload_crc_offset=offset,ready_after=bool(ready)))
            assert count==39
            print(f'phase={phase} wire={wire} Tco={tco} cases={count}',flush=True)
    d=dict(schema=1,hardware_access=False,scope='fulladdress-varied2048byteTILE color/depth plusheader/boundCRC digital model; not physical sampled pad waveform or timing closure',
           sample_clock_period_ps=4630,core_clock_period_ps=18518,minimum_host_setup_not_yet_enforced=True,
           clock_pattern='assumed160MHz divider floorHIGH; fractionalN/N+1; actualP4 ordering unmeasured',
           no_repair='only unique complete exact original header,payload,boundCRC accepted at an observed offset; no bytes shifted or fabricated',
           cases=cases,source_sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest()for f in files})
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(d,indent=2)+'\n')
    print('complete',len(cases),sum(c['full_body_exact']for c in cases),flush=True)
if __name__=='__main__':main()
