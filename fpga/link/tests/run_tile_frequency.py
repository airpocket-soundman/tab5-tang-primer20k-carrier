"""Digital-only27MHz frontend response timing sweep; no device/wire measurement."""
import argparse
import json
import hashlib
import subprocess as process_info
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp')
    p.add_argument('--output',type=Path,default=ROOT/'validation/tile-frequency-model-2026-11-03.json')
    args=p.parse_args()
    if not shutil.which(args.iverilog) or not shutil.which(args.vvp):p.error('existing Icarus/vvp required')
    cases=[]
    sources=['link/rtl/link_bringup.v','gfx/rtl/gfx_bench.v','gfx/rtl/triangle_tile.v','gfx/rtl/triangle_fragment.v',
             'gfx/rtl/triangle_coverage.v','gfx/rtl/triangle_depth.v','link/tests/tb_tile_frequency.v']
    with tempfile.TemporaryDirectory(prefix='response-frequency-') as td:
        for delay in (0,5,10):
            exe=Path(td)/f'model-{delay}.vvp'
            subprocess.run([args.iverilog,'-g2012','-s','tb_tile_frequency',f'-Ptb_tile_frequency.ONE_WAY_DELAY_PS={delay*1000}',
                            '-o',str(exe),*[str(ROOT/s) for s in sources]],check=True)
            result=subprocess.run([args.vvp,str(exe)],text=True,capture_output=True,check=True,timeout=180)
            for line in result.stdout.splitlines():
                if not line.startswith('SWEEP,'):continue
                freq,phase,wire,kind,passed,first_bad,ready=map(int,line.split(',')[1:])
                cases.append(dict(response_clock_hz=freq,phase_ns=phase,assumed_one_way_delay_ns=wire,
                                  response=('tagged_ID16' if kind==0 else ('tagged_ROW82' if kind==1 else 'tagged_TILE2066')),passed=bool(passed),
                                  first_mismatched_byte=first_bad,ready_after=bool(ready)))
    reference=[c for c in cases if c['response_clock_hz']==5000000]
    assert len(cases)==72 and len(reference)==72
    reference_ok=all(c['passed'] for c in reference)
    by_frequency={str(freq):{'passed':sum(c['passed'] for c in cases if c['response_clock_hz']==freq),'cases':sum(c['response_clock_hz']==freq for c in cases)}
                  for freq in (5000000,)}
    report={'date':'2026-11-03','hardware_access':False,'scope':'digital RTL frontend model only, not cable/PCB electrical limit',
            'assumptions':{'system_clock_nominal_hz':27000000,'system_clock_period_ps':37037,
                           'safe_request_setup_high_low_ns':1000,'host_response_sample':'old byte immediately before physical CLK rising edge',
                           'one_way_delays_ns':[0,5,10],'delay_definition':'assumed equal fixed outgoing clock/DIR/data and returning data/READY delays, no analog rise/fall/noise/jitter model',
                           'phase_offsets_ns':[0,5,10,15,20,25,30,35]},'reference5MHz_all_passed':reference_ok,
            'by_response_frequency':by_frequency,'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},
            'base_commit':process_info.check_output(['git','rev-parse','HEAD'],cwd=ROOT.parent,text=True).strip(),'cases':cases}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(by_frequency));print('5MHz reference',reference_ok,'; no physical speed claim')
    if not reference_ok:raise SystemExit('digital5MHz reference failed')
if __name__=='__main__':main()
