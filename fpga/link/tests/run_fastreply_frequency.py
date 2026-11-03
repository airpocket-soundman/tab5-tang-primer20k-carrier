"""RAW tagged serializer: bounded digital models, not cable or pad measurements."""
import argparse,hashlib,json,math,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp')
 p.add_argument('--output',type=Path,default=ROOT/'validation/fastreply-frequency-model-2026-11-03.json');p.add_argument('--ideal-only',action='store_true');a=p.parse_args()
 if not shutil.which(a.iverilog) or not shutil.which(a.vvp):p.error('existing Icarus/vvp required')
 sources=['link/rtl/link_reply_raw.v','link/rtl/link_bringup.v','gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v','gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v','link/tests/tb_fastreply_frequency.v']
 configs=[(wire,0,0,0) for wire in (0,5,10)]
 if not a.ideal_only:configs += [(wire,tco,1,pattern) for wire in (0,5,10) for tco in (2,5) for pattern in (1,2)]
 cases=[]
 with tempfile.TemporaryDirectory(prefix='raw-frequency-') as td:
  for wire,tco,extended,pattern in configs:
   exe=Path(td)/f'model-{wire}-{tco}-{extended}-{pattern}.vvp'
   params={'ONE_WAY_DELAY_PS':wire*1000,'FPGA_TCO_PS':tco*1000,'EXTENDED_MODE':extended,'CLOCK_PATTERN':pattern}
   subprocess.run([a.iverilog,'-g2012','-s','tb_fastreply_frequency',*[f'-Ptb_fastreply_frequency.{k}={v}' for k,v in params.items()],'-o',str(exe),*[str(ROOT/s) for s in sources]],check=True)
   r=subprocess.run([a.vvp,str(exe)],text=True,capture_output=True,check=True,timeout=180)
   count=0
   for line in r.stdout.splitlines():
    if not line.startswith('SWEEP,'):continue
    freq,phase,delay,kind,functional,bad,ready=map(int,line.split(',')[1:]);count+=1
    minimum_period_ps=6250*(160000000//freq) if extended else round(1e12/freq)
    available_ps=minimum_period_ps-2*wire*1000-tco*1000
    cases.append({'response_clock_hz':freq,'phase_ns':phase,'assumed_one_way_delay_ns':delay,'assumed_fpga_clock_to_data_ns':tco,
                  'clock_model':('160MHz_N_or_Nplus1_periods_short_HIGH' if pattern==1 else '160MHz_N_or_Nplus1_periods_long_HIGH') if extended else 'ideal50percent',
                  'response':('tagged_ID16','tagged_ROW82','tagged_TILE2066')[kind],'functional_passed':bool(functional),
                  'assumed_host_setup_ps':2000,'minimum_period_ps':minimum_period_ps,'nominal_available_setup_ps':available_ps,
                  'passed':bool(functional) and available_ps>2000,'first_mismatched_byte':bad,'ready_after':bool(ready)})
   assert count==(39 if extended else 243)
   print(f'model wire={wire}ns Tco={tco}ns pattern={pattern} cases={count}',flush=True)
 assert len(cases)==(729 if a.ideal_only else 1197)
 reference=[c for c in cases if c['response_clock_hz']==5000000];assert len(reference)==81 and all(c['passed'] for c in reference)
 base=[c for c in cases if c['clock_model']=='ideal50percent']
 by_frequency={str(f):{'passed':sum(c['passed'] for c in base if c['response_clock_hz']==f),'cases':sum(c['response_clock_hz']==f for c in base)} for f in sorted({c['response_clock_hz'] for c in base})}
 report={'date':'2026-11-03','hardware_access':False,'scope':'digital RAW serializer model; not cable/PCB limit or measured FPGA/P4 pad waveform',
         'assumptions':{'system_clock_nominal_hz':54000000,'system_clock_period_ps':18518,'safe_request_setup_high_low_ns':1000,
          'base_phase_offsets_ns':list(range(0,17,2)),'extended_phase_offsets_ns':[0,8,16],'one_way_delay_ns':[0,5,10],
          'clock_to_data_ns':[0] if a.ideal_only else [0,2,5],'host_setup_budget_ps':2000,
          'extended_clock':'assumed160MHz divider N/N+1 period accumulator with floor/ceil half cycles; actual hardware duty/period ordering unmeasured',
          'delays':'fixed equal outgoing CLK/DIR/data and return data/READY; added Tco only on returned data; no analog noise/rise/fall/jitter',
          'fixture':'pseudo-random address-varying color/depth; independent expected sequence checks every byte'},
         'ideal50percent_by_frequency':by_frequency,'reference5MHz_all_passed':True,'cases':cases,
         'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},
         'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT.parent,text=True).strip()}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(by_frequency));print('PASS5MHz reference; higher-model failures retained; no physical speed claim')
if __name__=='__main__':main()
