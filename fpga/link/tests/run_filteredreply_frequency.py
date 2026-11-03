"""Full CRC/payload model of conditioned reply clock; records expected failures."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog',required=True);p.add_argument('--vvp',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--quick',action='store_true');p.add_argument('--aperture',action='store_true')
    p.add_argument('--vendor-primitive-lib',type=Path);p.add_argument('--pipeline-coverage',action='store_true');p.add_argument('--low-rates',action='store_true');a=p.parse_args()
    files=['link/rtl/reply_clock_filter.v','link/rtl/link_reply_raw.v','link/rtl/link_bringup_filtered.v',
           'gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v',
           'gfx/rtl/triangle_depth.v','link/tests/tb_filteredreply_frequency.v']
    if a.aperture:files[-1]='link/tests/tb_filteredreply_aperture.v'
    if a.pipeline_coverage:files[files.index('gfx/rtl/triangle_coverage.v')]='gfx/rtl/triangle_coverage_pipeline.v'
    if a.vendor_primitive_lib:
        if not a.aperture:p.error('Vendor fixture uses --aperture')
        files[files.index('gfx/rtl/triangle_tile.v')]='gfx/rtl/triangle_tile_vendor.v'
        files[-1]='link/tests/tb_filteredreply_vendor.v';files +=['gfx/rtl/tile_dpram_vendor.v']
    files +=['link/rtl/triangle_batch.v']
    frozen={f:(ROOT/f).read_bytes()for f in files}
    if a.vendor_primitive_lib:frozen['installed_prim_sim.v']=a.vendor_primitive_lib.read_bytes()
    cases=[]
    configs=[(phase,wire,tco)for phase in (0,1)for wire in ((0,)if a.quick else (0,2,5))for tco in ((0,)if a.quick else (0,2))]
    with tempfile.TemporaryDirectory(prefix='filter-full-')as td:
        snapshot=[]
        for name,data in frozen.items():
            path=Path(td)/'sources'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);snapshot.append(path)
        for phase,wire,tco in configs:
            exe=Path(td)/'model.vvp'
            params=dict(EXTENDED_MODE=1,CLOCK_PATTERN=1,SAMPLE_INVERTED=phase,ONE_WAY_DELAY_PS=wire*1000,FPGA_TCO_PS=tco*1000)
            if a.low_rates:params['LOW_RATES_ONLY']=1
            subprocess.run([a.iverilog,'-g2012','-s','tb_filteredreply_frequency',*[f'-Ptb_filteredreply_frequency.{k}={v}'for k,v in params.items()],'-o',str(exe),*map(str,snapshot)],check=True,capture_output=True)
            r=subprocess.run([a.vvp,str(exe)],text=True,capture_output=True,check=True,timeout=240)
            count=0
            for line in r.stdout.splitlines():
                if not line.startswith('SWEEP,'):continue
                values=list(map(int,line.split(',')[1:]));frequency,offset_phase,delay,kind,passed,offset,ready=values[:7];count+=1
                cases.append(dict(configured_hz=frequency,sys_phase_ns=offset_phase,sample_phase='inverted_input_only'if phase else'legacy',
                                  one_way_wire_assumed_ns=wire,fpga_Tco_assumed_ns=tco,full_body_exact=bool(passed),
                                  unique_complete_header_payload_crc_offset=offset,ready_after=bool(ready)))
                if a.aperture:cases[-1].update(conditional_setup_hold_passed=bool(values[7]),minimum_observed_setup_ps=values[8],minimum_observed_hold_ps=values[9])
            assert count==(9 if a.low_rates else 39)
            print(f'phase={phase} wire={wire} Tco={tco} cases={count}',flush=True)
    d=dict(schema=1,hardware_access=False,scope='fulladdress-varied2048byteTILE color/depth plusheader/boundCRC digital model; not physical sampled pad waveform or timing closure',
           sample_clock_period_ps=4630,core_clock_period_ps=18518,minimum_host_setup_not_yet_enforced=not a.aperture,
           assumed_host_setup_hold_ps=2000 if a.aperture else None,
           vendor_memory=bool(a.vendor_primitive_lib),coverage_pipeline=a.pipeline_coverage,
           clock_pattern='assumed160MHz divider floorHIGH; fractionalN/N+1; actualP4 ordering unmeasured',
           no_repair='only unique complete exact original header,payload,boundCRC accepted at an observed offset; no bytes shifted or fabricated',
           cases=cases,source_sha256={f:hashlib.sha256(data).hexdigest()for f,data in frozen.items()},source_snapshot_before_compile=True)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(d,indent=2)+'\n')
    print('complete',len(cases),sum(c['full_body_exact']for c in cases),flush=True)
if __name__=='__main__':main()
